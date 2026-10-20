"""Encode bytes as an HTTP/1.1 chunked body, in one call or incrementally."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ._errors import ChunkedError, require_bytes
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

    >>> from chunkedte import Encoder
    >>> encoder = Encoder()
    >>> encoder.write(b"hello") + encoder.write(b"") + encoder.finish()
    b'5\\r\\nhello\\r\\n0\\r\\n\\r\\n'
    """

    def __init__(self) -> None:
        self._finished = False

    def write(self, data: bytes | bytearray | memoryview) -> bytes:
        """Return ``data`` framed as one chunk.

        Raises :class:`ChunkedError` after :meth:`finish` and :class:`TypeError` for data
        that is not ``bytes``, ``bytearray`` or ``memoryview``.

        >>> from chunkedte import Encoder
        >>> Encoder().write(b"0123456789abcdef")
        b'10\\r\\n0123456789abcdef\\r\\n'
        """
        if self._finished:
            raise ChunkedError("write after finish")
        require_bytes(data)
        piece = bytes(data)
        if not piece:
            return b""
        return b"%x\r\n%b\r\n" % (len(piece), piece)

    def finish(self, trailers: Trailers | None = None) -> bytes:
        """Return the last chunk, the trailer section and the closing CRLF.

        ``trailers`` is a mapping or an iterable of ``(name, value)`` pairs, written in
        order. A refused field raises :class:`ChunkedError` and leaves the encoder open, so
        :meth:`finish` can be called again; a second successful call raises.

        >>> from chunkedte import Encoder
        >>> Encoder().finish([("X-Checksum", "42"), ("X-Note", "done")])
        b'0\\r\\nX-Checksum: 42\\r\\nX-Note: done\\r\\n\\r\\n'
        """
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
    and the closing CRLF. An empty ``data`` yields just the last chunk. Raises
    :class:`TypeError` for a ``chunk_size`` that is not an ``int`` or data that is not
    bytes-like, :class:`ValueError` for a ``chunk_size`` below 1, and
    :class:`ChunkedError` for a trailer field :class:`Encoder` refuses.

    >>> from chunkedte import encode
    >>> encode(b"abcd", chunk_size=3, trailers={"X-Sum": "1"})
    b'3\\r\\nabc\\r\\n1\\r\\nd\\r\\n0\\r\\nX-Sum: 1\\r\\n\\r\\n'
    >>> encode(b"")
    b'0\\r\\n\\r\\n'
    """
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
        raise TypeError("chunk_size must be an int")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    require_bytes(data)
    body = bytes(data)
    encoder = Encoder()
    parts = [encoder.write(body[at : at + chunk_size]) for at in range(0, len(body), chunk_size)]
    parts.append(encoder.finish(trailers))
    return b"".join(parts)


def _pairs(trailers: Trailers | None) -> list[tuple[str, str]]:
    if trailers is None:
        return []
    if isinstance(trailers, (str, bytes, bytearray, memoryview)):
        raise TypeError("trailers must be a mapping or (name, value) pairs")
    if isinstance(trailers, Mapping):
        return list(trailers.items())
    pairs = []
    for pair in trailers:
        # A two-character str would unpack into a name and a value without complaint.
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise TypeError("trailers must be a mapping or (name, value) pairs")
        pairs.append((pair[0], pair[1]))
    return pairs
