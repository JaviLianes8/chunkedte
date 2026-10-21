from __future__ import annotations

import io

import pytest

from chunkedte import ChunkedError, encode
from chunkedte._cli import main

SECRET = "sk-live-SUPERSECRET"


def _encode(argument: str) -> tuple[int, bytes, str]:
    out, err = io.BytesIO(), io.StringIO()
    code = main(["encode", "--trailer", argument], io.BytesIO(b""), out, err)
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize(
    ("argument", "message"),
    [
        (f"Authorization Bearer {SECRET}:part2", "invalid byte 0x20 at offset 13"),
        (f"Authorization=Basic {SECRET}:pw", "invalid byte 0x3d at offset 13"),
        (f"id {SECRET}:secret", "invalid byte 0x20 at offset 2"),
    ],
)
def test_a_trailer_argument_with_a_colon_inside_the_secret_is_never_echoed(
    argument: str, message: str
) -> None:
    expected = f"chunkedte: {message} in a trailer field name\n"
    assert _encode(argument) == (1, b"", expected)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        (f"Authorization Bearer {SECRET}", "invalid byte 0x20 at offset 13"),
        (f"X-Key\x00{SECRET}", "invalid byte 0x00 at offset 5"),
        (f"X-K\u00e9y {SECRET}", "non-ASCII character U+00E9 at offset 3"),
        (f"\u20ac{SECRET}", "non-ASCII character U+20AC at offset 0"),
    ],
)
def test_a_bad_trailer_name_gives_the_first_bad_character_and_never_the_rest(
    name: str, message: str
) -> None:
    with pytest.raises(ChunkedError) as caught:
        encode(b"x", trailers=[(name, "v")])
    assert str(caught.value) == f"{message} in a trailer field name"
    assert "SUPERSECRET" not in str(caught.value)


def test_an_empty_trailer_name_is_named_as_such() -> None:
    with pytest.raises(ChunkedError) as caught:
        encode(b"x", trailers=[("", "v")])
    assert str(caught.value) == "empty trailer field name"
    assert _encode(":v") == (1, b"", "chunkedte: empty trailer field name\n")


class _Bare(io.BytesIO):
    def read(self, size: int | None = -1) -> bytes:
        raise OSError


def test_an_error_with_an_empty_message_is_named_by_its_type() -> None:
    out, err = io.BytesIO(), io.StringIO()
    assert main(["encode"], _Bare(), out, err) == 1
    assert (out.getvalue(), err.getvalue()) == (b"", "chunkedte: OSError\n")


def test_a_trailer_argument_with_an_empty_value_sends_an_empty_field() -> None:
    assert _encode("X-E:") == (0, b"0\r\nX-E: \r\n\r\n", "")


@pytest.mark.parametrize(("argument", "offset"), [("X-A : 1", 3), (" X-A: 1", 0)])
def test_whitespace_around_a_trailer_argument_name_is_refused(argument: str, offset: int) -> None:
    expected = f"chunkedte: invalid byte 0x20 at offset {offset} in a trailer field name\n"
    assert _encode(argument) == (1, b"", expected)


@pytest.mark.parametrize(
    ("argument", "sent"),
    [
        ("X-A:\t1", b"X-A: 1"),
        ("X-A: 1 ", b"X-A: 1"),
        ("X-A: 1\t", b"X-A: 1"),
        ("X-A: \t 1 \t ", b"X-A: 1"),
        ("X-A: 1\xa0", b"X-A: 1\xa0"),
    ],
)
def test_a_trailer_argument_value_loses_only_spaces_and_tabs_at_its_ends(
    argument: str, sent: bytes
) -> None:
    assert _encode(argument) == (0, b"0\r\n" + sent + b"\r\n\r\n", "")


def test_a_form_feed_at_the_end_of_a_trailer_argument_value_is_refused() -> None:
    expected = "chunkedte: invalid byte 0x0c at offset 1 in the value of trailer field X-A\n"
    assert _encode("X-A: 1\x0c") == (1, b"", expected)
