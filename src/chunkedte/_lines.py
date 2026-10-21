"""Cut CRLF-terminated lines off a growing buffer without rescanning what was already seen."""

from __future__ import annotations

from ._errors import ChunkedError, LimitError

_CR = 0x0D


def take_line(buffer: bytearray, scanned: int, limit: int, what: str) -> tuple[bytes | None, int]:
    """Remove one line from ``buffer`` and return it without its CRLF, or ``None``.

    ``scanned`` is how many bytes earlier calls already searched for a LF; the second
    value returned is the new count, so a line split over many reads is scanned once.
    Only CRLF ends a line: a bare LF or a bare CR raises :class:`ChunkedError`, and a line
    longer than ``limit`` raises :class:`LimitError` as soon as that is certain.
    """
    end = buffer.find(b"\n", scanned)
    if end == -1:
        # One byte of slack: the CR of a line that is exactly ``limit`` long.
        if len(buffer) > limit + 1:
            raise LimitError(f"{what} exceeds its limit")
        return None, len(buffer)
    # The length first, as in the branch above: a line fed byte by byte would have passed
    # the limit before its LF arrived, so the error must not depend on the split.
    if end > limit + 1:
        raise LimitError(f"{what} exceeds its limit")
    if end == 0 or buffer[end - 1] != _CR:
        raise ChunkedError(f"bare LF in the {what}")
    line = bytes(buffer[: end - 1])
    del buffer[: end + 1]
    if _CR in line:
        raise ChunkedError(f"bare CR in the {what}")
    return line, 0
