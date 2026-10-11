"""Error type raised when a chunked message is malformed."""

from __future__ import annotations


class ChunkedError(ValueError):
    """A chunked message could not be parsed (bad size line or framing)."""
