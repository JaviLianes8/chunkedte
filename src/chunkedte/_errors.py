"""Errors raised for malformed or oversized chunked messages."""

from __future__ import annotations


class ChunkedError(ValueError):
    """A chunked message or a framing field breaks RFC 9112 (answer with 400)."""


class LimitError(ChunkedError):
    """A configured :class:`Limits` bound was passed (answer with 413 or 431)."""
