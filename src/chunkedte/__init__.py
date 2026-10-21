"""Strict, incremental, typed, zero-dependency codec for HTTP/1.1 chunked transfer coding."""

from collections.abc import Callable as _Callable

from ._decode import Decoder
from ._encode import Encoder, encode
from ._errors import ChunkedError, LimitError
from ._framing import is_chunked
from ._limits import Limits
from ._oneshot import decode

__version__ = "1.0.0"

# Classes keep the module that defines them, so inspect and IDEs find their source, and
# their pickles go through _restore. Functions and methods report the package, and the
# classes are listed in __test__, so doctest finds every example from here.
for _function in (decode, encode, is_chunked):
    _function.__module__ = __name__
for _member in [*vars(Decoder).values(), *vars(Encoder).values()]:
    if callable(_member) and str(getattr(_member, "__module__", "")).startswith(__name__):
        _member.__module__ = __name__
del _function, _member

__test__: dict[str, type] = {
    "ChunkedError": ChunkedError,
    "Decoder": Decoder,
    "Encoder": Encoder,
    "LimitError": LimitError,
    "Limits": Limits,
}

_PICKLED: dict[str, _Callable[..., object]] = {
    "ChunkedError": ChunkedError,
    "LimitError": LimitError,
    "Limits": Limits,
}


def _restore(name: str, args: tuple[object, ...]) -> object:
    # A pickle names this function and a public class, never a private module.
    return _PICKLED[name](*args)


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
