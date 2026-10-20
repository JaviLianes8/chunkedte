"""Errors raised for malformed or oversized chunked messages."""

from __future__ import annotations

# Error messages quote at most this many characters of the offending input, so a hostile
# megabyte never ends up in a log line.
QUOTE_LIMIT = 64


class ChunkedError(ValueError):
    """A chunked message or a framing field breaks RFC 9112 (answer with 400).

    It is a :class:`ValueError`, and its message quotes at most 64 characters of the input.

    >>> from chunkedte import ChunkedError, decode
    >>> try:
    ...     decode(b"5\\nhello\\r\\n0\\r\\n\\r\\n")
    ... except ChunkedError as error:
    ...     print(error)
    bare LF in the chunk-size line
    """


class LimitError(ChunkedError):
    """A configured :class:`Limits` bound was passed (answer with 413 or 431).

    >>> from chunkedte import ChunkedError, LimitError, Limits, decode
    >>> try:
    ...     decode(b"5\\r\\nhello\\r\\n0\\r\\n\\r\\n", limits=Limits(max_body_size=4))
    ... except LimitError as error:
    ...     print(error, isinstance(error, ChunkedError))
    body exceeds max_body_size True
    """


def quote(value: str | bytes) -> str:
    """``repr`` of the first :data:`QUOTE_LIMIT` characters, marked when cut."""
    if len(value) <= QUOTE_LIMIT:
        return repr(value)
    return repr(value[:QUOTE_LIMIT]) + "..."


def require_bytes(data: object) -> None:
    """Refuse anything but ``bytes``, ``bytearray`` and ``memoryview`` with :class:`TypeError`."""
    # bytes(5) would build five NUL bytes and str would need an encoding guess.
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(f"expected a bytes-like object, got {type(data).__name__}")
