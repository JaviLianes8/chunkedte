"""The PyPI release 0.2.0 as an oracle: 1.0.0 answers the same, except where documented.

Set CHUNKEDTE_V02 to a folder holding the 0.2.0 package (for example the unpacked wheel:
`pip download chunkedte==0.2.0 --no-deps` and unzip it); the tests skip otherwise.
"""

from __future__ import annotations

import array
import importlib.util
import itertools
import os
import random
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from generators import SEEDS, mutate, valid_message

import chunkedte


@pytest.fixture(scope="module")
def old() -> ModuleType:
    folder = os.environ.get("CHUNKEDTE_V02")
    if not folder:
        pytest.skip("set CHUNKEDTE_V02 to the unpacked 0.2.0 release")
    init = Path(folder) / "chunkedte" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "chunkedte_v02", init, submodule_search_locations=[str(init.parent)]
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["chunkedte_v02"] = module
    spec.loader.exec_module(module)
    assert module.__version__ == "0.2.0"
    return module


def _reworded(message: str) -> bool:
    # 1.0.0 no longer quotes trailer values or lines: it names the field, byte and offset.
    if message.endswith("cannot be sent as a trailer field"):
        return False
    return any(part in message for part in ("trailer field", "trailer value", "trailer name"))


def _outcome(call: Callable[[], Any]) -> object:
    try:
        return ("ok", call())
    except Exception as error:
        if _reworded(str(error)):
            return (type(error).__name__, "a trailer field message")
        # 1.0.0 marks a quote it cut; 0.2.0 cut the same 64 characters silently.
        return (type(error).__name__, str(error).removesuffix("..."))


def _feed_all(module: ModuleType, message: bytes, cuts: list[int]) -> object:
    decoder = module.Decoder()
    pieces: list[bytes] = []
    bounds = [0, *sorted(cuts), len(message)]
    for start, end in itertools.pairwise(bounds):
        outcome = _outcome(lambda: decoder.feed(message[start:end]))  # noqa: B023
        if outcome[0] != "ok":  # type: ignore[index]
            return outcome, pieces
        pieces.extend(outcome[1])  # type: ignore[index]
    return pieces, decoder.is_complete, decoder.trailers, decoder.unused_data


def test_decoding_is_unchanged_on_hostile_and_valid_input(old: ModuleType) -> None:
    rng = random.Random(20)
    pool = [*SEEDS, *(valid_message(rng) for _ in range(30))]
    cases = [mutate(rng, rng.choice(pool)) for _ in range(20_000)] + pool
    for message in cases:
        cuts = [rng.randint(0, len(message)) for _ in range(rng.randint(0, 3))]
        assert _feed_all(old, message, cuts) == _feed_all(chunkedte, message, cuts), message
        assert _outcome(lambda: old.decode(message)) == _outcome(  # noqa: B023
            lambda: chunkedte.decode(message)  # noqa: B023
        )


def test_encoding_and_is_chunked_are_unchanged(old: ModuleType) -> None:
    rng = random.Random(21)
    names = ["X-Sum", "Host", "a b", "€", "Te", "", "T"]
    values = ["1", " x", "a\x00", "\xe9", "", "a\tb"]
    for _ in range(5_000):
        body = rng.randbytes(rng.randint(0, 50))
        size = rng.choice([1, 3, 8192, 0, -1])
        trailers = [(rng.choice(names), rng.choice(values)) for _ in range(rng.randint(0, 2))]
        assert _outcome(lambda: old.encode(body, chunk_size=size, trailers=trailers)) == (  # noqa: B023
            _outcome(lambda: chunkedte.encode(body, chunk_size=size, trailers=trailers))  # noqa: B023
        )
    codings = ["chunked", "gzip", " ,", ";a=b", "CHUNKED", '; q="x"', "", "\x00"]
    for _ in range(5_000):
        te = rng.choice([None, ", ".join(rng.choice(codings) for _ in range(rng.randint(0, 3)))])
        cl = rng.choice([None, "12", ""])
        request = rng.random() < 0.5
        if te is not None and cl is None and not request and not te.strip(" \t,"):
            # 1.0.0 reads a response that lists no coding to close, as RFC 9112 6.3 says.
            assert chunkedte.is_chunked(te, cl, request=request) is False
            continue
        assert _outcome(lambda: old.is_chunked(te, cl, request=request)) == (  # noqa: B023
            _outcome(lambda: chunkedte.is_chunked(te, cl, request=request))  # noqa: B023
        ), (te, cl, request)


def test_the_documented_changes_and_nothing_else(old: ModuleType) -> None:
    changed: list[tuple[str, Callable[[ModuleType], Any]]] = [
        ("Decoder(5)", lambda m: m.Decoder(5).feed(b"0\r\n\r\n")),
        ("array feed", lambda m: m.Decoder().feed(array.array("B", b"0\r\n\r\n"))),
        ("bytes field", lambda m: m.is_chunked(b"chunked")),
        ("int length", lambda m: m.is_chunked("chunked", 5)),
        ("str pair", lambda m: m.encode(b"", trailers=["ab"])),
        ("long pair", lambda m: m.encode(b"", trailers=[("a", "b", "c")])),
        ("request None", lambda m: m.is_chunked("gzip", request=None)),
    ]
    for label, call in changed:
        before, after = _outcome(lambda: call(old)), _outcome(lambda: call(chunkedte))  # noqa: B023
        assert after[0] == "TypeError" and before != after, (label, before, after)  # type: ignore[index]
    long_value = {"A": "\x00" * 1000}
    messages = []
    for module in (old, chunkedte):
        with pytest.raises(module.ChunkedError) as caught:
            module.encode(b"", trailers=long_value)
        messages.append(str(caught.value))
    assert len(messages[1]) < 400 < len(messages[0])


def test_the_round_one_changes(old: ModuleType) -> None:
    strided = memoryview(b"1\x00\r\x00\n\x00a\x00\r\x00\n\x000\x00\r\x00\n\x00\r\x00\n\x00")[::2]
    cases: list[tuple[Callable[[ModuleType], Any], object, object]] = [
        (lambda m: m.is_chunked(" , ", request=False), "ChunkedError", ("ok", False)),
        (lambda m: m.encode(b"", trailers={"If-Match": "x"}), "ok", "ChunkedError"),
        (lambda m: m.decode(strided), "TypeError", ("ok", b"a")),
        (
            lambda m: m.Decoder(m.Limits(max_line_size=4)).feed(b"123456\n"),
            "ChunkedError",
            "LimitError",
        ),
    ]
    for call, before, after in cases:
        was, now = _outcome(lambda: call(old)), _outcome(lambda: call(chunkedte))  # noqa: B023
        assert was[0] == before, was  # type: ignore[index]
        assert (now if isinstance(after, tuple) else now[0]) == after, now  # type: ignore[index]
