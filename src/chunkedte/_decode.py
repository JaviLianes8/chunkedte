"""Incremental, strict decoder for HTTP/1.1 chunked transfer coding (RFC 9112 section 7.1)."""

from __future__ import annotations

import enum

from ._errors import ChunkedError, LimitError, quote, require_bytes
from ._grammar import SIZE_LINE, parse_field_line
from ._limits import Limits
from ._lines import take_line

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
    fields are kept in :attr:`trailers` (keep them apart from the header section, RFC 9110
    section 6.5.2). Bytes after the final CRLF land in :attr:`unused_data`. When
    :meth:`feed` raises, the pieces decoded in that call are dropped, and every later
    :meth:`feed` raises again.

    >>> from chunkedte import Decoder
    >>> decoder = Decoder()
    >>> decoder.feed(b"5\\r\\nhel"), decoder.feed(b"lo\\r\\n0\\r\\n\\r\\n")
    ([b'hel'], [b'lo'])
    >>> decoder.is_complete
    True
    """

    def __init__(self, limits: Limits | None = None) -> None:
        if limits is not None and not isinstance(limits, Limits):
            raise TypeError(f"limits must be a Limits, got {type(limits).__name__}")
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
        """Whether the last chunk and the trailer section have been fully consumed.

        >>> from chunkedte import Decoder
        >>> decoder = Decoder()
        >>> _ = decoder.feed(b"0\\r\\n")
        >>> decoder.is_complete
        False
        >>> _ = decoder.feed(b"\\r\\n")
        >>> decoder.is_complete
        True
        """
        return self._state is _State.DONE

    @property
    def trailers(self) -> list[tuple[str, str]]:
        """Trailer fields received so far as ``(name, value)`` pairs, in arrival order.

        Names keep their case; values are OWS-trimmed and decoded as latin-1.

        >>> from chunkedte import Decoder
        >>> decoder = Decoder()
        >>> _ = decoder.feed(b"0\\r\\nDigest: x\\r\\nNote:  a b \\r\\n\\r\\n")
        >>> decoder.trailers
        [('Digest', 'x'), ('Note', 'a b')]
        """
        return list(self._trailers)

    @property
    def unused_data(self) -> bytes:
        """Bytes received after the end of the chunked message (for example the next request).

        Empty until the message is complete.

        >>> from chunkedte import Decoder
        >>> decoder = Decoder()
        >>> decoder.feed(b"1\\r\\na\\r\\n0\\r\\n\\r\\nGET / HTTP/1.1")
        [b'a']
        >>> decoder.unused_data
        b'GET / HTTP/1.1'
        """
        return bytes(self._buffer) if self._state is _State.DONE else b""

    def feed(self, data: bytes | bytearray | memoryview) -> list[bytes]:
        """Append ``data`` and return every decoded body piece now available.

        Raises :class:`ChunkedError` once a size or trailer line that breaks the grammar
        is complete (the CRLF after chunk data is checked byte by byte), and
        :class:`LimitError` as soon as a bound is certain to be passed; the error class
        never depends on how the input is split. Data that is not ``bytes``,
        ``bytearray`` or ``memoryview`` raises :class:`TypeError`.

        >>> from chunkedte import Decoder
        >>> Decoder().feed(b"3\\r\\nabc\\r\\n2\\r\\nde\\r\\n")
        [b'abc', b'de']
        """
        require_bytes(data)
        if self._error is not None:
            raise ChunkedError(f"the decoder already failed: {self._error}")
        if isinstance(data, memoryview) and not data.contiguous:  # ValueError when released
            data = data.tobytes()  # bytearray cannot append a strided view
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
        line, self._scanned = take_line(
            self._buffer, self._scanned, self._limits.max_line_size, "chunk-size line"
        )
        if line is None:
            return False
        match = SIZE_LINE.fullmatch(line)
        if match is None:
            raise ChunkedError(f"malformed chunk-size line: {quote(line)}")
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
        line, self._scanned = take_line(self._buffer, self._scanned, budget, "trailer section")
        if line is None:
            return False
        if not line:
            self._state = _State.DONE
            return False
        self._trailer_size += len(line) + 2
        self._trailers.append(parse_field_line(line))
        return True
