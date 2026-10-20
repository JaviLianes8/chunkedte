"""Strict, incremental, typed, zero-dependency codec for HTTP/1.1 chunked transfer coding."""

from ._decode import Decoder
from ._encode import Encoder, encode
from ._errors import ChunkedError, LimitError
from ._framing import is_chunked
from ._limits import Limits
from ._oneshot import decode

__version__ = "1.0.0"

# The public names show and pickle as chunkedte.<Name>, so a pickle never depends on the
# private module that defines them. Methods follow, so doctest finds their examples here.
for _public in (ChunkedError, Decoder, Encoder, LimitError, Limits, decode, encode, is_chunked):
    _public.__module__ = __name__
    for _member in vars(_public).values():
        if callable(_member) and str(getattr(_member, "__module__", "")).startswith(__name__):
            _member.__module__ = __name__
del _public, _member

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
