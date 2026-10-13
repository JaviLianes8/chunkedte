from __future__ import annotations

import time

import pytest

from chunkedte import ChunkedError, Decoder, LimitError, Limits, decode


def test_defaults_are_documented_values() -> None:
    limits = Limits()
    assert limits.max_line_size == 4096
    assert limits.max_extensions_size == 16384
    assert limits.max_chunk_size == 2**63 - 1
    assert limits.max_body_size is None
    assert limits.max_trailer_size == 16384


@pytest.mark.parametrize("name", ["max_line_size", "max_chunk_size", "max_body_size"])
def test_negative_limits_are_refused(name: str) -> None:
    with pytest.raises(ValueError, match=name):
        Limits(**{name: -1})


@pytest.mark.parametrize("value", [True, 1.5, "10", None])
def test_non_int_limits_are_refused(value: object) -> None:
    with pytest.raises(TypeError, match="max_trailer_size"):
        Limits(max_trailer_size=value)  # type: ignore[arg-type]


def test_limits_are_frozen() -> None:
    with pytest.raises(AttributeError):
        Limits().max_line_size = 1  # type: ignore[misc]


def test_a_size_line_at_the_limit_passes_and_one_byte_more_fails() -> None:
    line = b"1;" + b"a" * 8
    assert decode(line + b"\r\nx\r\n0\r\n\r\n", limits=Limits(max_line_size=10)) == b"x"
    with pytest.raises(LimitError, match="chunk-size line"):
        decode(line + b"a\r\nx\r\n0\r\n\r\n", limits=Limits(max_line_size=10))


def test_an_endless_size_line_fails_before_any_lf_arrives() -> None:
    decoder = Decoder(Limits(max_line_size=10))
    decoder.feed(b"1;" + b"a" * 8 + b"\r")
    with pytest.raises(LimitError):
        decoder.feed(b"a")


def test_extension_bytes_are_bounded_across_the_whole_message() -> None:
    # GHSA-prhj-8562-p8gj (Node.js): unbounded extension bytes over many small chunks.
    chunk = b"1;" + b"e" * 99 + b"\r\nx\r\n"
    limits = Limits(max_extensions_size=1000)
    assert decode(chunk * 10 + b"0\r\n\r\n", limits=limits) == b"x" * 10
    with pytest.raises(LimitError, match="extensions"):
        decode(chunk * 10 + b"0;e\r\n\r\n", limits=limits)


def test_chunk_size_is_capped() -> None:
    limits = Limits(max_chunk_size=255)
    assert decode(b"ff\r\n" + b"x" * 255 + b"\r\n0\r\n\r\n", limits=limits) == b"x" * 255
    with pytest.raises(LimitError, match="max_chunk_size"):
        Decoder(limits).feed(b"100\r\n")


def test_the_default_cap_refuses_a_size_that_needs_64_bits() -> None:
    Decoder().feed(b"7fffffffffffffff\r\n")
    with pytest.raises(LimitError, match="max_chunk_size"):
        Decoder().feed(b"8000000000000000\r\n")


def test_huge_numerals_are_refused_without_building_them() -> None:
    with pytest.raises(LimitError, match="max_chunk_size"):
        Decoder(Limits(max_chunk_size=2**80)).feed(b"1" + b"0" * 16 + b"\r\n")


def test_leading_zeros_do_not_count_towards_the_size_cap() -> None:
    assert decode(b"0" * 100 + b"1\r\nx\r\n0\r\n\r\n") == b"x"


def test_body_size_is_capped_when_the_size_line_arrives() -> None:
    limits = Limits(max_body_size=5)
    assert decode(b"2\r\nab\r\n3\r\ncde\r\n0\r\n\r\n", limits=limits) == b"abcde"
    decoder = Decoder(limits)
    decoder.feed(b"2\r\nab\r\n")
    with pytest.raises(LimitError, match="max_body_size"):
        decoder.feed(b"4\r\n")


def test_trailer_section_is_capped_including_crlfs() -> None:
    trailer = b"A: 123\r\n"  # eight bytes with its CRLF
    message = b"0\r\n" + trailer * 2 + b"\r\n"
    assert decode(message, limits=Limits(max_trailer_size=16)) == b""
    with pytest.raises(LimitError, match="trailer section"):
        decode(message, limits=Limits(max_trailer_size=15))


def test_an_endless_trailer_line_fails_early() -> None:
    decoder = Decoder(Limits(max_trailer_size=10))
    decoder.feed(b"0\r\nA: 12345")
    with pytest.raises(LimitError):
        decoder.feed(b"6789")


def test_limit_errors_are_chunked_errors() -> None:
    with pytest.raises(ChunkedError):
        decode(b"1" * 5000 + b"\r\n")


def _feed_line_bytewise(length: int) -> float:
    limits = Limits(max_line_size=length + 10, max_extensions_size=length + 10)
    decoder = Decoder(limits)
    data = b"1;" + b"a" * length
    started = time.perf_counter()
    for index in range(len(data)):
        decoder.feed(data[index : index + 1])
    decoder.feed(b"\r\nx\r\n0\r\n\r\n")
    assert decoder.is_complete
    return time.perf_counter() - started


def test_a_line_fed_one_byte_at_a_time_costs_linear_time() -> None:
    small = min(_feed_line_bytewise(50_000) for _ in range(3))
    large = min(_feed_line_bytewise(400_000) for _ in range(2))
    # Eight times the input; a rescan from the line start each feed would be ~64 times.
    assert large < small * 20, (small, large)


@pytest.mark.parametrize(
    "line",
    [
        b"1" + b";a" * 2000 + b" x",
        b"1" + b" " * 4000 + b"x",
        b"1;a=" + b'"' + b"\\a" * 2000,
        b"1" + b";a=b" * 1000 + b";",
    ],
)
def test_hostile_size_lines_are_rejected_quickly(line: bytes) -> None:
    started = time.perf_counter()
    with pytest.raises(ChunkedError):
        decode(line + b"\r\n")
    assert time.perf_counter() - started < 0.5
