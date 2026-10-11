"""Encode a byte string into an HTTP/1.1 chunked transfer-encoding body."""

from __future__ import annotations

DEFAULT_CHUNK_SIZE = 8192


def encode(data: bytes, *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> bytes:
    """Frame ``data`` as a complete chunked body, split into ``chunk_size`` pieces.

    The result is a sequence of ``<hex-size>CRLF<data>CRLF`` chunks followed by the
    terminating ``0CRLFCRLF``. An empty ``data`` yields just the terminator.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    parts = [b"%x\r\n%s\r\n" % (len(piece), piece) for piece in _split(data, chunk_size)]
    parts.append(b"0\r\n\r\n")
    return b"".join(parts)


def _split(data: bytes, size: int) -> list[bytes]:
    return [data[start : start + size] for start in range(0, len(data), size)]
