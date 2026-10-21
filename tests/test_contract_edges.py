"""Edge promises: introspection, pickles, odd buffers, split invariance, safe messages."""

from __future__ import annotations

import array
import dataclasses
import doctest
import inspect
import pickle
import random
import sys
from collections.abc import Callable

import pytest

import chunkedte
from chunkedte import ChunkedError, Decoder, Encoder, LimitError, Limits, decode, encode, is_chunked

SECRET = "sk-live-SUPERSECRET-TOKEN-1234"


@pytest.mark.parametrize("name", chunkedte.__all__)
def test_the_source_of_every_public_name_can_be_shown(name: str) -> None:
    source = inspect.getsource(getattr(chunkedte, name))
    lines = source.splitlines()
    assert any(line.startswith((f"class {name}", f"def {name}")) for line in lines)


def test_pickles_of_limits_and_errors_name_only_the_package() -> None:
    for value in (Limits(max_body_size=5), ChunkedError("x"), LimitError("body exceeds")):
        data = pickle.dumps(value)
        assert b"chunkedte._" not in data
        restored = pickle.loads(data)
        assert type(restored) is type(value)
        assert repr(restored) == repr(value)


class AppError(ChunkedError):
    pass


@dataclasses.dataclass(frozen=True)
class StrictLimits(Limits):
    pass


def test_pickles_keep_notes_and_attributes_of_errors() -> None:
    for error in (ChunkedError("bad"), LimitError("body exceeds max_body_size")):
        if sys.version_info >= (3, 11):
            error.add_note("while reading request 7")
        error.request_id = 7  # type: ignore[attr-defined]
        restored = pickle.loads(pickle.dumps(error))
        assert vars(restored) == vars(error) and restored.request_id == 7
        assert getattr(restored, "__notes__", None) == getattr(error, "__notes__", None)


def test_pickles_keep_the_type_of_subclasses() -> None:
    error = pickle.loads(pickle.dumps(AppError("x")))
    assert (type(error), error.args) == (AppError, ("x",))
    limits = pickle.loads(pickle.dumps(StrictLimits(max_body_size=5)))
    assert (type(limits), limits) == (StrictLimits, StrictLimits(max_body_size=5))


def test_the_package_doctests_include_the_methods() -> None:
    found = [test for test in doctest.DocTestFinder().find(chunkedte) if test.examples]
    names = {test.name.rsplit(".", 2)[-2] + "." + test.name.rsplit(".", 1)[-1] for test in found}
    assert len(found) == 14
    assert {"Decoder.feed", "Encoder.write", "Encoder.finish", "Decoder.trailers"} <= names


@pytest.mark.parametrize("name", ["ñ", "X-€", "é"])
def test_a_non_ascii_trailer_name_is_not_a_token(name: str) -> None:
    with pytest.raises(ChunkedError, match="trailer name is not a token"):
        encode(b"x", trailers={name: "b"})


@pytest.mark.parametrize("request_", [None, "no", 0, 1])
def test_is_chunked_takes_only_a_bool_request(request_: object) -> None:
    with pytest.raises(TypeError, match="request must be a bool"):
        is_chunked("gzip", request=request_)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name", ["If-Match", "if-none-match", "If-Modified-Since", "If-Unmodified-Since", "If-Range"]
)
def test_conditional_request_fields_are_refused_as_trailers(name: str) -> None:
    with pytest.raises(ChunkedError, match="cannot be sent as a trailer"):
        encode(b"", trailers=[(name, '"x"')])


LEAKS: dict[str, Callable[[], object]] = {
    "encoder control byte": lambda: encode(b"", trailers=[("X-Api-Key", SECRET + "\n")]),
    "encoder edge space": lambda: encode(b"", trailers=[("X-Api-Key", SECRET + " ")]),
    "encoder non latin-1": lambda: encode(b"", trailers=[("X-Api-Key", SECRET + "€")]),
    "decoder control byte": lambda: decode(
        b"0\r\nAuthorization: Bearer " + SECRET.encode() + b"\x00\r\n\r\n"
    ),
    "decoder no colon": lambda: decode(b"0\r\nAuthorization " + SECRET.encode() + b"\r\n\r\n"),
    "decoder space before colon": lambda: decode(b"0\r\nKey : " + SECRET.encode() + b"\r\n\r\n"),
}


@pytest.mark.parametrize("case", sorted(LEAKS))
def test_error_messages_never_echo_a_trailer_value(case: str) -> None:
    with pytest.raises(ChunkedError) as caught:
        LEAKS[case]()
    assert "SUPERSECRET" not in str(caught.value)
    assert "offset" in str(caught.value) or "whitespace" in str(caught.value)


def test_a_bad_trailer_value_names_the_field_byte_and_offset() -> None:
    with pytest.raises(ChunkedError) as caught:
        encode(b"", trailers=[("X-Key", "ab\x01c")])
    assert str(caught.value) == "invalid byte 0x01 at offset 2 in the value of trailer field X-Key"
    with pytest.raises(ChunkedError) as caught:
        decode(b"0\r\nX-Key:  ab\x7fc\r\n\r\n")
    assert str(caught.value) == "invalid byte 0x7f at offset 2 in the value of trailer field X-Key"


def test_wide_and_strided_memoryviews_are_read_as_their_bytes() -> None:
    wide = memoryview(array.array("H", [0x4142, 0x4344]))
    framed = Encoder().write(wide) + b"0\r\n\r\n"
    assert framed[:3] == b"4\r\n" and decode(framed) == wide.tobytes()
    assert encode(wide, chunk_size=3)[:3] == b"3\r\n"
    message = b"4\r\nABCD\r\n0\r\n\r\n"
    assert decode(memoryview(message).cast("H")) == b"ABCD"
    assert Decoder().feed(memoryview(message).cast("H")) == [b"ABCD"]
    strided = memoryview(bytes(b for byte in message for b in (byte, 0)))[::2]
    assert not strided.contiguous
    assert decode(strided) == b"ABCD"
    assert encode(strided) == encode(message)
    assert Decoder().feed(strided) == [b"ABCD"]


def test_a_released_memoryview_raises_value_error_everywhere() -> None:
    view = memoryview(b"0\r\n\r\n")
    view.release()
    for call in (decode, encode, Decoder().feed, Encoder().write):
        with pytest.raises(ValueError, match="released") as caught:
            call(view)
        assert not isinstance(caught.value, ChunkedError)


def _error_class(data: bytes, limits: Limits, step: int) -> type[Exception] | None:
    decoder = Decoder(limits)
    try:
        for at in range(0, len(data), step):
            decoder.feed(data[at : at + step])
    except ChunkedError as error:
        return type(error)
    return None


def test_the_error_class_does_not_depend_on_how_the_input_is_split() -> None:
    assert _error_class(b"123456\n", Limits(max_line_size=4), 1) is LimitError
    assert _error_class(b"123456\n", Limits(max_line_size=4), 100) is LimitError
    trailer = b"0\r\nAbcdefgh: x\n"
    assert _error_class(trailer, Limits(max_trailer_size=6), 100) is LimitError
    rng = random.Random(7)
    alphabet = b"0123456789aZ;= \t\r\n:x\x00"
    for _ in range(20_000):
        data = bytes(rng.choice(alphabet) for _ in range(rng.randint(1, 24)))
        if rng.random() < 0.5:
            data = b"0\r\n" + data
        limits = Limits(max_line_size=rng.randint(0, 8), max_trailer_size=rng.randint(0, 12))
        whole = _error_class(data, limits, len(data))
        assert whole == _error_class(data, limits, 1) == _error_class(data, limits, 3), data
