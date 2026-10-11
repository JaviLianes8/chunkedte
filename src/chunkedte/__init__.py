"""Incremental, typed, zero-dependency codec for HTTP/1.1 chunked transfer-encoding."""

from __future__ import annotations

from ._decode import Decoder, decode
from ._encode import encode
from ._errors import ChunkedError

__version__ = "0.1.0"

__all__ = ["ChunkedError", "Decoder", "decode", "encode"]
