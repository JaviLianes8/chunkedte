"""Incremental decoder for HTTP/1.1 chunked transfer-encoding bodies."""

from __future__ import annotations

import enum

from ._errors import ChunkedError

_CRLF = b"\r\n"


class _State(enum.Enum):
    SIZE = enum.auto()
    DATA = enum.auto()
    DATA_CRLF = enum.auto()
    TRAILERS = enum.auto()
    DONE = enum.auto()


class Decoder:
    """Feed chunked bytes in any split; collect the decoded body pieces.

    Chunk extensions and trailer fields are consumed and ignored. The decoder is
    complete once the final zero-size chunk and the closing blank line are seen.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._state = _State.SIZE
        self._remaining = 0

    @property
    def is_complete(self) -> bool:
        """Whether the terminating zero-size chunk has been fully consumed."""
        return self._state is _State.DONE

    def feed(self, data: bytes) -> list[bytes]:
        """Append ``data`` and return every decoded body piece now available."""
        if self._state is _State.DONE:
            if data:
                raise ChunkedError("data fed after the message was complete")
            return []
        self._buffer += data
        out: list[bytes] = []
        while self._step(out):
            pass
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
        line = self._take_line()
        if line is None:
            return False
        self._remaining = _parse_size(line)
        self._state = _State.TRAILERS if self._remaining == 0 else _State.DATA
        return True

    def _read_data(self, out: list[bytes]) -> bool:
        if not self._buffer:
            return False
        take = min(self._remaining, len(self._buffer))
        out.append(bytes(self._buffer[:take]))
        del self._buffer[:take]
        self._remaining -= take
        if self._remaining == 0:
            self._state = _State.DATA_CRLF
        return True

    def _read_data_crlf(self) -> bool:
        if len(self._buffer) < 2:
            return False
        if self._buffer[:2] != _CRLF:
            raise ChunkedError("chunk data not terminated by CRLF")
        del self._buffer[:2]
        self._state = _State.SIZE
        return True

    def _read_trailer(self) -> bool:
        line = self._take_line()
        if line is None:
            return False
        if not line:
            self._state = _State.DONE
        return True

    def _take_line(self) -> bytes | None:
        index = self._buffer.find(_CRLF)
        if index == -1:
            return None
        line = bytes(self._buffer[:index])
        del self._buffer[: index + 2]
        return line


def _parse_size(line: bytes) -> int:
    token = line.split(b";", 1)[0].strip()
    try:
        size = int(token.decode("ascii"), 16)
    except (ValueError, UnicodeDecodeError):
        raise ChunkedError(f"malformed chunk size: {line!r}") from None
    if size < 0:
        raise ChunkedError(f"negative chunk size: {line!r}")
    return size


def decode(data: bytes) -> bytes:
    """Decode a complete chunked message in one call and return the body.

    Raises :class:`ChunkedError` if the message is not fully terminated.
    """
    decoder = Decoder()
    pieces = decoder.feed(data)
    if not decoder.is_complete:
        raise ChunkedError("incomplete chunked message")
    return b"".join(pieces)
