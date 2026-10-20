"""Every chunked body in the llhttp test corpus, against the verdict llhttp's own log records.

The two corpus files are fetched by `scripts/fetch_upstream.py` (URL, tag and sha256 in
tests/upstream/MANIFEST.json); the tests skip until then. Inputs are rebuilt the way
llhttp's test/md-test.ts does; the expected body and trailer fields are cut from the input
at the offsets the log gives, so no escaping has to be guessed. Only the strict (default)
parser modes are used, never the lenient ones.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from conftest import read_upstream

from chunkedte import ChunkedError, Decoder

FILES = ["llhttp-request-transfer-encoding.md", "llhttp-response-transfer-encoding.md"]
CASE = re.compile(
    r"<!-- meta=(\{[^\n]*\}) -->\n```http\n(.*?)```\n\n```log\n(.*?)```", flags=re.DOTALL
)
SPAN = re.compile(r"off=(\d+) len=(\d+) span\[(body|header_field|header_value)\]")


@dataclass
class Case:
    title: str
    body: bytes
    verdict: str  # "complete", "error" or "incomplete"
    expected_body: bytes
    expected_trailers: list[tuple[str, str]]


def _input(text: str) -> bytes:
    """test/md-test.ts: the steps that apply to these files, outside Windows."""
    text = re.sub(r"\n\Z", "", text)  # JavaScript "$" without the m flag
    text = re.sub(r"\\(\r\n|\r|\n)", "", text)
    text = re.sub(r"\r\n|\r|\n", "\r\n", text)
    for escape, char in ((r"\r", "\r"), (r"\n", "\n"), (r"\t", "\t"), (r"\f", "\f")):
        text = text.replace(escape, char)
    text = re.sub(r"\\x([0-9a-fA-F]+)", lambda m: chr(int(m[1], 16)), text)
    text = re.sub(r"\\([0-7]{1,3})", lambda m: chr(int(m[1], 8)), text)
    return text.encode("latin-1")


def _cases() -> list[Case]:
    cases = []
    for name in FILES:
        text = read_upstream(name)
        for match in CASE.finditer(text):
            meta, source, log = json.loads(match[1]), _input(match[2]), match[3]
            head_end = source.find(b"\r\n\r\n") + 4
            head = source[:head_end].lower()
            chunked = re.search(rb"\r\ntransfer-encoding: *chunked *\r\n", head)
            if meta.get("type") not in ("request", "response") or not chunked:
                continue
            if b"content-length" in head or "headers complete" not in log:
                continue
            after = log.split("headers complete", 1)[1]
            done = after.split("message complete", 1)[0] if "message complete" in after else None
            verdict = "complete" if done is not None else "error" if "error" in after else ""
            spans = [(int(o), int(n), kind) for o, n, kind in SPAN.findall(done or "")]
            body = b"".join(source[o : o + n] for o, n, kind in spans if kind == "body")
            fields = [source[o : o + n].decode("latin-1") for o, n, k in spans if k != "body"]
            title = re.findall(r"^#+ (.*)$", text[: match.start()], flags=re.MULTILINE)[-1]
            pairs = list(zip(fields[::2], fields[1::2], strict=True))
            cases.append(Case(title, source[head_end:], verdict or "incomplete", body, pairs))
    return cases


def _decode(body: bytes) -> tuple[str, bytes, list[tuple[str, str]]]:
    decoder = Decoder()
    try:
        pieces = decoder.feed(body)
    except ChunkedError:
        return "error", b"", []
    if not decoder.is_complete:
        return "incomplete", b"".join(pieces), []
    return "complete", b"".join(pieces), decoder.trailers


def test_the_corpus_has_the_expected_cases() -> None:
    cases = _cases()
    assert len(cases) >= 20
    verdicts = {case.verdict for case in cases}
    assert verdicts == {"complete", "error", "incomplete"}, verdicts


def test_every_chunked_body_of_the_corpus_gets_llhttps_verdict() -> None:
    for case in _cases():
        verdict, body, trailers = _decode(case.body)
        if verdict == "complete" or case.verdict == "complete":
            assert (verdict, body, trailers) == (
                case.verdict,
                case.expected_body,
                case.expected_trailers,
            ), case
        else:
            assert verdict == case.verdict, case
