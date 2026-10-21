"""Seeded inputs shared by the fuzz and oracle tests, and this library's reading of them."""

from __future__ import annotations

import random

from chunkedte import ChunkedError, Decoder

SEEDS = [
    b"5\r\nhello\r\n0\r\n\r\n",
    b'3;a=b\r\nabc\r\n2 ; q = "x\\"y"\r\nde\r\n0;end\r\n\r\n',
    b"A\r\n0123456789\r\n0\r\nX-Sum: 42\r\nNote:  two words \r\n\r\n",
    b"1\r\n\r\r\n1\r\n\n\r\n00\r\n\r\nNEXT",
    b"0\r\nA:\r\nB:\x80\xff\r\n\r\n",
]
ALPHABET = [bytes([value]) for value in b'\r\n \t;="\\:0aAgx+_\x00\x7f\x80,'] + [b"\r\n"]
TOKEN = "abcXYZ019!#$%&'*+-.^_`|~"

Reading = tuple[bytes, list[tuple[str, str]], int]


def mutate(rng: random.Random, message: bytes) -> bytes:
    """Insert, delete or replace one to three bytes, drawn mostly from framing characters."""
    data = bytearray(message)
    for _ in range(rng.randint(1, 3)):
        at = rng.randint(0, len(data))
        operation = rng.randint(0, 2)
        if operation == 0:
            data[at:at] = rng.choice(ALPHABET)
        elif operation == 1 and at < len(data):
            del data[at]
        elif at < len(data):
            data[at : at + 1] = rng.choice(ALPHABET)
    return bytes(data)


def valid_message(rng: random.Random) -> bytes:
    """A valid chunked message without BWS: chunks, extensions, trailers, maybe more bytes."""
    parts = []
    for _ in range(rng.randint(0, 4)):
        data = rng.randbytes(rng.randint(1, 40))
        size = f"{len(data):x}".upper() if rng.random() < 0.5 else f"{len(data):x}"
        parts.append(b"0" * rng.randint(0, 2) + size.encode() + _extensions(rng) + b"\r\n")
        parts.append(data + b"\r\n")
    parts.append(b"0" * rng.randint(1, 3) + _extensions(rng) + b"\r\n")
    for _ in range(rng.randint(0, 3)):
        name = "".join(rng.choice(TOKEN) for _ in range(rng.randint(1, 8)))
        value = "".join(rng.choice('ab 7:;,\t"') for _ in range(rng.randint(0, 9)))
        parts.append(f"X{name}: {value.strip()}\r\n".encode())
    return b"".join(parts) + b"\r\n" + rng.choice([b"", b"GET / HTTP/1.1\r\n"])


def _extensions(rng: random.Random) -> bytes:
    out = b""
    for _ in range(rng.randint(0, 2)):
        out += b";" + "".join(rng.choice(TOKEN) for _ in range(rng.randint(1, 6))).encode()
        if rng.random() < 0.5:
            out += b'="a b\\"c"' if rng.random() < 0.5 else b"=tok"
    return out


def reading(case: bytes) -> Reading | None:
    """Body, trailers and bytes used for a complete message fed at once; ``None`` otherwise."""
    decoder = Decoder()
    try:
        body = b"".join(decoder.feed(case))
    except ChunkedError:
        return None
    if not decoder.is_complete:
        return None
    return body, decoder.trailers, len(case) - len(decoder.unused_data)
