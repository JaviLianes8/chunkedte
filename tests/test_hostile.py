"""Hostile shapes cost time linear in their size: the work at 4n stays near four times n."""

from __future__ import annotations

import contextlib
import random
import time
from collections.abc import Callable

import pytest

from chunkedte import ChunkedError, Decoder, Limits, decode, encode, is_chunked

N = 50_000
OPEN = Limits(
    max_line_size=10**8, max_extensions_size=10**8, max_trailer_size=10**8, max_body_size=None
)


def _feed(message: bytes, step: int = 0) -> None:
    decoder = Decoder(OPEN)
    with contextlib.suppress(ChunkedError):
        for at in range(0, len(message), step or len(message) or 1):
            decoder.feed(message[at : at + (step or len(message))])


def _te(value: str) -> None:
    with contextlib.suppress(ChunkedError):
        is_chunked(value, request=False)


SHAPES: dict[str, Callable[[int], Callable[[], object]]] = {
    "tiny chunks": lambda n: lambda: _feed(b"1\r\na\r\n" * n + b"0\r\n\r\n"),
    "tiny chunks, byte by byte": lambda n: lambda: _feed(b"1\r\na\r\n" * (n // 8), 1),
    "extension list, bad end": lambda n: lambda: _feed(b"1" + b";a" * n + b'"\r\n'),
    "extension list, no lf": lambda n: lambda: _feed(b"1" + b";a=b" * n, 7),
    "quoted pairs, unclosed": lambda n: lambda: _feed(b'1;a="' + b"\\a" * n + b"\r\n"),
    "bws runs": lambda n: lambda: _feed(b"1" + b" " * n + b"x\r\n"),
    "zeros in a size": lambda n: lambda: _feed(b"0" * n + b"1\r\nx\r\n0\r\n\r\n"),
    "many trailers": lambda n: lambda: _feed(b"0\r\n" + b"a: b\r\n" * n + b"\r\n"),
    "long trailer value, bad end": lambda n: lambda: _feed(b"0\r\nA: " + b"v " * n + b"\x00"),
    "trailer by byte": lambda n: lambda: _feed(b"0\r\nA: " + b"v" * (n // 4) + b"\r\n\r\n", 1),
    "after the message": lambda n: lambda: _feed(b"0\r\n\r\n" + b"x" * n, 3),
    "one big chunk by byte": lambda n: lambda: _feed(b"%x\r\n" % n + b"a" * (n // 4), 1),
    "codings": lambda n: lambda: _te("gzip, " * n + "chunked"),
    "commas": lambda n: lambda: _te("," * n + "chunked"),
    "spaces then bad": lambda n: lambda: _te(" " * n + "\x00"),
    "parameters": lambda n: lambda: _te("gzip" + ";a=b" * n + ', chunked;q="'),
    "encode small pieces": lambda n: lambda: encode(b"a" * n, chunk_size=1),
    "decode encoded": lambda n: lambda: decode(encode(b"a" * n, chunk_size=3)),
}


def _seconds(call: Callable[[], object]) -> float:
    best = float("inf")
    for _ in range(3):
        started = time.perf_counter()
        call()
        best = min(best, time.perf_counter() - started)
    return best


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_hostile_shapes_scale_linearly(name: str) -> None:
    small = _seconds(SHAPES[name](N))
    large = _seconds(SHAPES[name](4 * N))
    # Linear work gives about 4; quadratic would give about 16. The floor absorbs timer noise.
    assert large < 8 * max(small, 0.002), (name, small, large)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_input_only_ever_raises_the_documented_errors(seed: int) -> None:
    rng = random.Random(seed)
    alphabet = b'0123456789abcdefABCDEFgx;=" \t\r\n:\\,\x00\x7f\x80\xff'
    for _ in range(3000):
        data = bytes(rng.choice(alphabet) for _ in range(rng.randint(0, 60)))
        decoder = Decoder(Limits(max_line_size=rng.randint(0, 20), max_body_size=40))
        with contextlib.suppress(ChunkedError):
            for at in range(0, len(data), rng.randint(1, 9)):
                decoder.feed(data[at : at + 9])
        with contextlib.suppress(ChunkedError):
            decode(data)
        text = data.decode("latin-1")
        with contextlib.suppress(ChunkedError):
            is_chunked(text, rng.choice([None, "1"]), request=rng.random() < 0.5)
        name, _, value = text.partition(":")
        with contextlib.suppress(ChunkedError):
            encode(data, chunk_size=rng.randint(1, 9), trailers=[(name, value)])
