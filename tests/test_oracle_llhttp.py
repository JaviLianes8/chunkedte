"""The decoder against llhttp, the HTTP/1.1 parser inside Node.js, run live on the same bytes.

llhttp is an independent, widely deployed implementation (Node.js 24 ships llhttp 9). The
oracle script feeds each body after a chunked request head, one byte at a time, and
reports the body, the trailer fields and where the message ended. Skips without `node`.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from generators import SEEDS, Reading, mutate, reading, valid_message
from reference import Rejected, parse

NODE = shutil.which("node")
SCRIPT = Path(__file__).resolve().parent / "oracles" / "llhttp_oracle.js"
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

# llhttp refuses BWS around ";" and "=" in a chunk extension, which RFC 9112 allows, with
# these two codes; it also lets through some extension text the grammar forbids. Those are
# the only disagreements (see the tests below).
BWS_CODES = {"HPE_INVALID_CHUNK_SIZE", "HPE_STRICT"}
SIZE_LINE_WITH_EXTENSION = re.compile(rb"(?:^|\r\n)[0-9A-Fa-f]+[ \t]*;[^\r\n]*")

Outcome = tuple[str, list[tuple[str, str | None]], int]


def _llhttp(cases: list[bytes]) -> list[dict[str, Any]]:
    assert NODE is not None
    lines = "".join(case.hex() + "\n" for case in cases)
    result = subprocess.run(
        [NODE, str(SCRIPT)], input=lines, capture_output=True, text=True, check=True
    )
    answers = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(answers) == len(cases)
    return answers


def _same(ours: Reading, theirs: dict[str, Any]) -> bool:
    # Node.js turns field values into strings its own way past ASCII, so those are not compared.
    def ascii_only(pairs: list[Any]) -> list[tuple[str, str | None]]:
        return [(name, value if value.isascii() else None) for name, value in pairs]

    body, trailers, used = ours
    mine: Outcome = (body.hex(), ascii_only(trailers), used)
    return mine == (theirs["body"], ascii_only(theirs["trailers"]), theirs["used"])


def test_valid_messages_without_bws_decode_identically() -> None:
    rng = random.Random(9112)
    cases = [valid_message(rng) for _ in range(3000)]
    for case, theirs in zip(cases, _llhttp(cases), strict=True):
        ours = reading(case)
        assert ours is not None and theirs["ok"], (case, theirs)
        assert _same(ours, theirs), (case, theirs)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_mutated_messages_differ_only_in_chunk_extension_syntax(seed: int) -> None:
    rng = random.Random(seed)
    pool = [*SEEDS, *(valid_message(rng) for _ in range(20))]
    cases = [mutate(rng, rng.choice(pool)) for _ in range(8000)]
    seen = {"both": 0, "neither": 0, "bws": 0, "lenient": 0}
    for case, theirs in zip(cases, _llhttp(cases), strict=True):
        ours = reading(case)
        if ours is not None and theirs["ok"]:
            assert _same(ours, theirs), (case, theirs)
            seen["both"] += 1
        elif ours is None and not theirs["ok"]:
            seen["neither"] += 1
        elif ours is not None:
            assert theirs["code"] in BWS_CODES, (case, theirs)
            lines = [m.group() for m in SIZE_LINE_WITH_EXTENSION.finditer(case)]
            assert any(b" " in line or b"\t" in line for line in lines), case
            seen["bws"] += 1
        else:
            # llhttp lets through extension text the ABNF forbids: the hand-written reading
            # of RFC 9112 refuses it too, and the message does carry an extension.
            with pytest.raises(Rejected):
                parse(case)
            assert re.search(rb"(?:^|\r\n)[0-9A-Fa-f]+;", case), case
            seen["lenient"] += 1
    assert min(seen.values()) > 5, seen


@pytest.mark.parametrize("line", [b"1 ;a", b"1\t;a", b"1; a", b"1;a =b", b"1;a= b", b'1 ; a = "b"'])
def test_bws_in_extensions_is_valid_here_and_refused_by_llhttp(line: bytes) -> None:
    case = line + b"\r\nx\r\n0\r\n\r\n"
    assert reading(case) == (b"x", [], len(case))
    (theirs,) = _llhttp([case])
    assert not theirs["ok"] and theirs["code"] in BWS_CODES


@pytest.mark.parametrize("line", [b"1;=tok", b"1;a=", b'1;a=b"c"'])
def test_extensions_outside_the_grammar_are_refused_here_and_let_through_by_llhttp(
    line: bytes,
) -> None:
    case = line + b"\r\nx\r\n0\r\n\r\n"
    assert reading(case) is None
    (theirs,) = _llhttp([case])
    assert theirs["ok"] and theirs["body"] == b"x".hex()
