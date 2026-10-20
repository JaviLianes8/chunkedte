"""Bounds that keep a decoder's memory and work proportional to what the caller allows."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Limits:
    """Upper bounds applied while decoding; passing one raises :class:`LimitError`.

    ``max_line_size`` bounds one chunk-size line (size plus extensions, CRLF excluded),
    ``max_extensions_size`` the extension bytes of the whole message, ``max_chunk_size`` the
    value of one chunk-size, ``max_body_size`` the decoded body (``None`` for no bound) and
    ``max_trailer_size`` the trailer field lines including their CRLFs. Every bound is a
    non-negative ``int`` (:class:`TypeError` or :class:`ValueError` otherwise). A size of
    more than 16 significant hex digits is refused whatever ``max_chunk_size`` says.

    >>> from chunkedte import Decoder, LimitError, Limits
    >>> limits = Limits(max_body_size=1024)
    >>> limits.max_body_size, limits.max_line_size
    (1024, 4096)
    >>> try:
    ...     Decoder(limits).feed(b"401\\r\\n")
    ... except LimitError as error:
    ...     print(error)
    body exceeds max_body_size
    """

    max_line_size: int = 4096
    max_extensions_size: int = 16384
    # Below 2**63 so a forwarded size never wraps in a downstream signed 64-bit parser.
    max_chunk_size: int = 2**63 - 1
    max_body_size: int | None = None
    max_trailer_size: int = 16384

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None and field.name == "max_body_size":
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{field.name} must be an int, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"{field.name} must not be negative")
