"""Encode bytes as an HTTP/1.1 chunked body, in one call or incrementally."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ._errors import ChunkedError
from ._grammar import format_field_line

DEFAULT_CHUNK_SIZE = 8192

Trailers = Mapping[str, str] | Iterable[tuple[str, str]]


class Encoder:
    """Frame body pieces as chunks as they are produced, then close the message.

    :meth:`write` turns one piece into one chunk (an empty piece yields nothing, since a
    zero-size chunk would end the message); :meth:`finish` writes the last chunk and the
    optional trailer section. Trailer names must be tokens and values field-values, and
    fields that frame or route a message (Content-Length, Transfer-Encoding, Host, ...)
    are refused as trailers.
    """

    def __init__(self) -> None:
        self._finished = False

    def write(self, data: bytes | bytearray | memoryview) -> bytes:
        """Return ``data`` framed as one chunk."""
        if self._finished:
            raise ChunkedError("write after finish")
        piece = _as_bytes(data)
        if not piece:
            return b""
        return b"%x\r\n%b\r\n" % (len(piece), piece)

    def finish(self, trailers: Trailers | None = None) -> bytes:
        """Return the last chunk, the trailer section and the closing CRLF."""
        if self._finished:
            raise ChunkedError("finish called twice")
        lines = [format_field_line(name, value) + b"\r\n" for name, value in _pairs(trailers)]
        self._finished = True
        return b"0\r\n" + b"".join(lines) + b"\r\n"


def encode(
    data: bytes | bytearray | memoryview,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    trailers: Trailers | None = None,
) -> bytes:
    """Frame ``data`` as a complete chunked body split into ``chunk_size`` pieces.

    The result is ``<hex-size>CRLF<data>CRLF`` chunks, then ``0CRLF``, the trailer fields
    and the closing CRLF. An empty ``data`` yields just the last chunk.
    """
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
        raise TypeError("chunk_size must be an int")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    body = _as_bytes(data)
    encoder = Encoder()
    parts = [encoder.write(body[at : at + chunk_size]) for at in range(0, len(body), chunk_size)]
    parts.append(encoder.finish(trailers))
    return b"".join(parts)


def _as_bytes(data: bytes | bytearray | memoryview) -> bytes:
    # bytes(5) would silently build five NUL bytes.
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(f"expected a bytes-like object, got {type(data).__name__}")
    return bytes(data)


def _pairs(trailers: Trailers | None) -> list[tuple[str, str]]:
    if trailers is None:
        return []
    if isinstance(trailers, (str, bytes)):
        raise TypeError("trailers must be a mapping or (name, value) pairs")
    if isinstance(trailers, Mapping):
        return list(trailers.items())
    return [(name, value) for name, value in trailers]
