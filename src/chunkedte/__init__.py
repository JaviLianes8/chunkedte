"""Strict, incremental, typed, zero-dependency codec for HTTP/1.1 chunked transfer coding."""

from __future__ import annotations

from ._decode import Decoder, decode
from ._encode import Encoder, encode
from ._errors import ChunkedError, LimitError
from ._framing import is_chunked
from ._limits import Limits

__version__ = "0.2.0"

__all__ = [
    "ChunkedError",
    "Decoder",
    "Encoder",
    "LimitError",
    "Limits",
    "decode",
    "encode",
    "is_chunked",
]
