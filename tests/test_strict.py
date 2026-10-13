"""Strict framing: every leniency here is a request smuggling desync with some other parser."""

from __future__ import annotations

import pytest

from chunkedte import ChunkedError, Decoder, decode

TAIL = b"\r\nhello\r\n0\r\n\r\n"


@pytest.mark.parametrize(
    "size",
    [b"+5", b"-5", b"0x5", b"5_0", b" 5", b"5 ", b"\t5", b"5\t", b"", b"g", b"\xd9\xa5", b"5\x00"],
)
def test_a_size_that_is_not_hexdig_is_rejected(size: bytes) -> None:
    # GHSA-4f7p-27jc-3c36 (waitress): Python's int() accepted "+10" and "0x01" as sizes.
    with pytest.raises(ChunkedError, match="malformed chunk-size line"):
        decode(size + TAIL)


@pytest.mark.parametrize(
    "extension",
    [
        b";a=b",
        b"; a = b",
        b"\t;\ta\t=\tb",
        b" ;a",
        b";a;b;c=d",
        b';a=""',
        b';a="x;y=z"',
        b';a="\\""',
        b';a="tab\there"',
        b";!#$%&'*+-.^_`|~=09azAZ",
        b';a="\x80\xff"',
    ],
)
def test_extensions_matching_the_grammar_are_accepted(extension: bytes) -> None:
    assert decode(b"5" + extension + TAIL) == b"hello"


@pytest.mark.parametrize(
    "extension",
    [
        b";",
        b"; ",
        b";=b",
        b";a=",
        b";a b",
        b";a=b c",
        b";a=b;",
        b";a@b",
        b";a=(b)",
        b';a="b',
        b';a="b"c',
        b';a="\x7f"',
        b';a="\\\x00"',
        b";a=b\x00",
        b"x",
        b",a",
        b";a\x80",
    ],
)
def test_extensions_breaking_the_grammar_are_rejected(extension: bytes) -> None:
    with pytest.raises(ChunkedError, match="malformed chunk-size line"):
        decode(b"5" + extension + TAIL)


def test_a_bare_lf_inside_an_extension_is_rejected() -> None:
    # GHSA-fghv-69vj-qj49 (netty) and GHSA-8495-4g3g-x7pr (aiohttp): an LF in a chunk
    # extension ended the size line. Payload shape from the netty advisory.
    message = b"48;\n" + b"A" * 72 + b"\n0\r\n\r\n"
    with pytest.raises(ChunkedError, match="bare LF"):
        decode(message)


@pytest.mark.parametrize("message", [b"5\nhello\r\n0\r\n\r\n", b"5\r\nhello\r\n0\n\r\n"])
def test_a_bare_lf_ending_a_size_line_is_rejected(message: bytes) -> None:
    # GHSA-g9pc-8g42-g6vq (Go net/http): a bare LF accepted as the size line terminator.
    with pytest.raises(ChunkedError, match="bare LF"):
        decode(message)


@pytest.mark.parametrize("message", [b"\n5\r\nhello\r\n0\r\n\r\n", b"\n5\r"])
def test_a_bare_lf_as_the_first_byte_of_a_line_is_rejected(message: bytes) -> None:
    with pytest.raises(ChunkedError, match="bare LF"):
        Decoder().feed(message)


@pytest.mark.parametrize("message", [b"5\r\r\nhello\r\n0\r\n\r\n", b"5;a=b\rc\r\nhello"])
def test_a_bare_cr_in_a_size_line_is_rejected(message: bytes) -> None:
    # GHSA-cggh-pq45-6h9x (llhttp): a bare CR accepted as a line terminator.
    with pytest.raises(ChunkedError, match="bare CR"):
        decode(message)


def test_two_garbage_bytes_after_chunk_data_are_rejected() -> None:
    # GHSA-vqfr-h8mv-ghfj (h11): the advisory's payload, accepted as body "AAAAA45".
    with pytest.raises(ChunkedError, match="not followed by CRLF"):
        decode(b"5\r\nAAAAAXX2\r\n45\r\n0\r\n\r\n")


@pytest.mark.parametrize("after", [b"\n", b"X", b"\r\r", b"\rX", b" \r\n"])
def test_anything_but_crlf_after_chunk_data_is_rejected(after: bytes) -> None:
    with pytest.raises(ChunkedError, match="not followed by CRLF"):
        decode(b"5\r\nhello" + after + b"0\r\n\r\n")


def test_a_wrong_byte_after_chunk_data_fails_without_waiting_for_more() -> None:
    decoder = Decoder()
    decoder.feed(b"1\r\nx")
    with pytest.raises(ChunkedError, match="not followed by CRLF"):
        decoder.feed(b"X")


def test_a_cr_then_a_wrong_byte_after_chunk_data_is_rejected() -> None:
    decoder = Decoder()
    decoder.feed(b"1\r\nx\r")
    with pytest.raises(ChunkedError, match="not followed by CRLF"):
        decoder.feed(b"X")


@pytest.mark.parametrize(
    "line",
    [
        b" X: y",
        b"\tX: y",
        b"X : y",
        b"X\t: y",
        b"X",
        b": y",
        b"X y: z",
        b"X(y): z",
        b"X: a\x00b",
        b"X: a\x7fb",
        b"X: a\x0bb",
        b"\x80: y",
    ],
)
def test_malformed_trailer_lines_are_rejected(line: bytes) -> None:
    with pytest.raises(ChunkedError):
        decode(b"0\r\n" + line + b"\r\n\r\n")


def test_obs_fold_in_trailers_is_rejected_with_a_clear_message() -> None:
    with pytest.raises(ChunkedError, match="obsolete line folding"):
        decode(b"0\r\nX: a\r\n  b\r\n\r\n")


@pytest.mark.parametrize(
    "message",
    [b"0\r\nX: y\nZ: w\r\n\r\n", b"0\r\nX: y\r\n\n", b"0\r\n\n", b"0\r\nX: a\rb\r\n\r\n"],
)
def test_trailer_lines_end_only_at_crlf(message: bytes) -> None:
    with pytest.raises(ChunkedError, match="bare"):
        decode(message)


def test_the_closing_crlf_must_be_crlf() -> None:
    with pytest.raises(ChunkedError):
        decode(b"0\r\nX\r\n")
