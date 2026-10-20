"""Decode a whole chunked message held in memory."""

from __future__ import annotations

from ._decode import Decoder
from ._errors import ChunkedError
from ._limits import Limits


def decode(data: bytes | bytearray | memoryview, *, limits: Limits | None = None) -> bytes:
    """Decode one complete chunked message and return the body.

    Raises :class:`ChunkedError` if the message is malformed, not terminated, or followed
    by more bytes, :class:`LimitError` when it passes ``limits`` (the defaults of
    :class:`Limits` when ``None``), and :class:`TypeError` for data that is not ``bytes``,
    ``bytearray`` or ``memoryview``. Trailer fields are checked and dropped; use
    :class:`Decoder` to read them.

    >>> from chunkedte import ChunkedError, decode
    >>> decode(b"4\\r\\nwiki\\r\\n5;ext=1\\r\\npedia\\r\\n0\\r\\nDigest: x\\r\\n\\r\\n")
    b'wikipedia'
    >>> try:
    ...     decode(b"5\\r\\nhello\\r\\n0\\r\\n\\r\\nGET /")
    ... except ChunkedError as error:
    ...     print(error)
    bytes after the end of the chunked message
    """
    decoder = Decoder(limits)
    pieces = decoder.feed(data)
    if not decoder.is_complete:
        raise ChunkedError("incomplete chunked message")
    if decoder.unused_data:
        raise ChunkedError("bytes after the end of the chunked message")
    return b"".join(pieces)
