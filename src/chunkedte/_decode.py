"""Incremental, strict decoder for HTTP/1.1 chunked transfer coding (RFC 9112 section 7.1)."""

from __future__ import annotations

import enum

from ._errors import ChunkedError, LimitError
from ._grammar import SIZE_LINE, parse_field_line
from ._limits import Limits

_CR = 0x0D
# Sixteen significant hex digits hold any value below 2**64; more is never a real size.
_MAX_SIZE_DIGITS = 16


class _State(enum.Enum):
    SIZE = enum.auto()
    DATA = enum.auto()
    DATA_CRLF = enum.auto()
    TRAILERS = enum.auto()
    DONE = enum.auto()


class Decoder:
    """Feed chunked bytes in any split and collect the decoded body pieces.

    Size lines, chunk extensions and trailer fields are checked against the RFC 9112
    grammar; only CRLF ends a line. Extensions are validated and then ignored, trailer
    fields are kept in :attr:`trailers`. Bytes after the final CRLF land in
    :attr:`unused_data`. After an error every later :meth:`feed` raises again.
    """

    def __init__(self, limits: Limits | None = None) -> None:
        self._limits = Limits() if limits is None else limits
        self._buffer = bytearray()
        self._scanned = 0
        self._state = _State.SIZE
        self._remaining = 0
        self._body_size = 0
        self._extensions_size = 0
        self._trailer_size = 0
        self._trailers: list[tuple[str, str]] = []
        self._error: ChunkedError | None = None

    @property
    def is_complete(self) -> bool:
        """Whether the last chunk and the trailer section have been fully consumed."""
        return self._state is _State.DONE

    @property
    def trailers(self) -> list[tuple[str, str]]:
        """Trailer fields received so far as ``(name, value)`` pairs, in arrival order."""
        return list(self._trailers)

    @property
    def unused_data(self) -> bytes:
        """Bytes received after the end of the chunked message (for example the next request)."""
        return bytes(self._buffer) if self._state is _State.DONE else b""

    def feed(self, data: bytes | bytearray | memoryview) -> list[bytes]:
        """Append ``data`` and return every decoded body piece now available."""
        if self._error is not None:
            raise ChunkedError(f"the decoder already failed: {self._error}")
        self._buffer += data
        out: list[bytes] = []
        try:
            while self._step(out):
                pass
        except ChunkedError as error:
            self._error = error
            raise
        return out

    def _step(self, out: list[bytes]) -> bool:
        if self._state is _State.SIZE:
            return self._read_size()
        if self._state is _State.DATA:
            return self._read_data(out)
        if self._state is _State.DATA_CRLF:
            return self._read_data_crlf()
        if self._state is _State.TRAILERS:
            return self._read_trailer()
        return False

    def _read_size(self) -> bool:
        line = self._take_line(self._limits.max_line_size, "chunk-size line")
        if line is None:
            return False
        match = SIZE_LINE.fullmatch(line)
        if match is None:
            raise ChunkedError(f"malformed chunk-size line: {line[:64]!r}")
        digits, extensions = match.group(1, 2)
        self._extensions_size += len(extensions)
        if self._extensions_size > self._limits.max_extensions_size:
            raise LimitError("chunk extensions exceed max_extensions_size")
        if len(digits.lstrip(b"0")) > _MAX_SIZE_DIGITS:
            raise LimitError("chunk size exceeds max_chunk_size")
        size = int(digits, 16)
        if size > self._limits.max_chunk_size:
            raise LimitError("chunk size exceeds max_chunk_size")
        cap = self._limits.max_body_size
        if cap is not None and self._body_size + size > cap:
            raise LimitError("body exceeds max_body_size")
        self._remaining = size
        self._state = _State.DATA if size else _State.TRAILERS
        return True

    def _read_data(self, out: list[bytes]) -> bool:
        if not self._buffer:
            return False
        take = min(self._remaining, len(self._buffer))
        out.append(bytes(self._buffer[:take]))
        del self._buffer[:take]
        self._remaining -= take
        self._body_size += take
        if self._remaining == 0:
            self._state = _State.DATA_CRLF
        return True

    def _read_data_crlf(self) -> bool:
        # Fail on the first wrong byte: any two bytes here is the h11 smuggling bug.
        head = bytes(self._buffer[:2])
        if not b"\r\n".startswith(head):
            raise ChunkedError("chunk data not followed by CRLF")
        if len(head) < 2:
            return False
        del self._buffer[:2]
        self._state = _State.SIZE
        return True

    def _read_trailer(self) -> bool:
        budget = max(self._limits.max_trailer_size - self._trailer_size - 2, 0)
        line = self._take_line(budget, "trailer section")
        if line is None:
            return False
        if not line:
            self._state = _State.DONE
            return False
        self._trailer_size += len(line) + 2
        self._trailers.append(parse_field_line(line))
        return True

    def _take_line(self, limit: int, what: str) -> bytes | None:
        """Cut one CRLF-terminated line off the buffer, scanning each byte only once."""
        end = self._buffer.find(b"\n", self._scanned)
        if end == -1:
            self._scanned = len(self._buffer)
            if self._scanned > limit + 1:
                raise LimitError(f"{what} exceeds its limit")
            return None
        self._scanned = 0
        if end == 0 or self._buffer[end - 1] != _CR:
            raise ChunkedError(f"bare LF in the {what}")
        if end - 1 > limit:
            raise LimitError(f"{what} exceeds its limit")
        line = bytes(self._buffer[: end - 1])
        del self._buffer[: end + 1]
        if _CR in line:
            raise ChunkedError(f"bare CR in the {what}")
        return line


def decode(data: bytes | bytearray | memoryview, *, limits: Limits | None = None) -> bytes:
    """Decode one complete chunked message and return the body.

    Raises :class:`ChunkedError` if the message is malformed, not terminated, or followed
    by more bytes.
    """
    decoder = Decoder(limits)
    pieces = decoder.feed(data)
    if not decoder.is_complete:
        raise ChunkedError("incomplete chunked message")
    if decoder.unused_data:
        raise ChunkedError("bytes after the end of the chunked message")
    return b"".join(pieces)
