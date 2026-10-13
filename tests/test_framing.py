from __future__ import annotations

import time

import pytest

from chunkedte import ChunkedError, is_chunked


def test_no_transfer_encoding_is_not_chunked() -> None:
    assert is_chunked(None) is False
    assert is_chunked(None, "10") is False


@pytest.mark.parametrize(
    "value",
    ["chunked", "Chunked", "CHUNKED", "gzip, chunked", "gzip,chunked", " , gzip ,, chunked , "],
)
def test_chunked_as_the_final_coding_is_chunked(value: str) -> None:
    assert is_chunked(value) is True
    assert is_chunked(value, request=False) is True


def test_parameters_on_other_codings_are_allowed() -> None:
    assert is_chunked('foo;a=1;b = "x, y", chunked') is True


def test_both_fields_together_are_an_error() -> None:
    # RFC 9112 section 6.3 rule 3: a likely smuggling attempt, handled as an error.
    with pytest.raises(ChunkedError, match="Content-Length"):
        is_chunked("chunked", "0")
    with pytest.raises(ChunkedError, match="Content-Length"):
        is_chunked("chunked", "", request=False)


@pytest.mark.parametrize("value", ["chunked, chunked", "chunked, gzip, chunked"])
def test_chunked_twice_is_an_error(value: str) -> None:
    with pytest.raises(ChunkedError, match="more than once"):
        is_chunked(value, request=False)


@pytest.mark.parametrize("value", ["chunked;q=1", "gzip, chunked ; a = b"])
def test_chunked_with_parameters_is_an_error(value: str) -> None:
    with pytest.raises(ChunkedError, match="parameters"):
        is_chunked(value, request=False)


@pytest.mark.parametrize("value", ["gzip", "chunked, gzip", "identity"])
def test_a_request_whose_final_coding_is_not_chunked_is_an_error(value: str) -> None:
    with pytest.raises(ChunkedError, match="final transfer coding"):
        is_chunked(value)


@pytest.mark.parametrize("value", ["gzip", "chunked, gzip"])
def test_a_response_whose_final_coding_is_not_chunked_is_read_to_close(value: str) -> None:
    assert is_chunked(value, request=False) is False


@pytest.mark.parametrize(
    "value",
    [
        "chunked gzip",
        "chunked\n",
        "\x0bchunked",
        "chunked;",
        "chunked;a",
        'gzip;a="b, chunked',
        "chun" + chr(0x212A) + "ed",
        "chunked\x00",
        "gzip;a=b c, chunked",
    ],
)
def test_malformed_field_values_are_errors(value: str) -> None:
    with pytest.raises(ChunkedError, match="malformed Transfer-Encoding"):
        is_chunked(value, request=False)


@pytest.mark.parametrize("value", ["", " ", ",", " , ,"])
def test_a_field_without_codings_is_an_error(value: str) -> None:
    with pytest.raises(ChunkedError, match="no transfer coding"):
        is_chunked(value, request=False)


def test_a_non_str_value_is_a_type_error() -> None:
    with pytest.raises(TypeError):
        is_chunked(b"chunked")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [" " * 65536 + "x y", "\t" * 65536 + ",", " " * 65536],
    ids=["spaces", "tabs", "blank"],
)
def test_long_whitespace_runs_are_parsed_in_linear_time(value: str) -> None:
    # Two adjacent OWS runs in the list regex once made this quadratic.
    started = time.perf_counter()
    with pytest.raises(ChunkedError):
        is_chunked(value)
    assert time.perf_counter() - started < 0.5


def test_error_messages_do_not_echo_a_huge_field() -> None:
    with pytest.raises(ChunkedError) as caught:
        is_chunked("x y" * 50_000)
    assert len(str(caught.value)) < 200
