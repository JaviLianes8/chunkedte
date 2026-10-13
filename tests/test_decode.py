from __future__ import annotations

import pytest

from chunkedte import ChunkedError, Decoder, decode


def _feed_all(decoder: Decoder, message: bytes, step: int) -> bytes:
    pieces: list[bytes] = []
    for start in range(0, len(message), step):
        pieces.extend(decoder.feed(message[start : start + step]))
    return b"".join(pieces)


def test_decode_complete_message() -> None:
    assert decode(b"5\r\nhello\r\n0\r\n\r\n") == b"hello"


def test_decode_multiple_chunks() -> None:
    assert decode(b"3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n") == b"abcde"


def test_decode_empty_body() -> None:
    assert decode(b"0\r\n\r\n") == b""


def test_decode_accepts_bytearray_and_memoryview() -> None:
    assert decode(bytearray(b"1\r\nx\r\n0\r\n\r\n")) == b"x"
    assert decode(memoryview(b"1\r\nx\r\n0\r\n\r\n")) == b"x"


def test_hex_digits_are_case_insensitive_and_may_have_leading_zeros() -> None:
    assert decode(b"000A\r\n0123456789\r\n0000\r\n\r\n") == b"0123456789"
    assert decode(b"a\r\n0123456789\r\n0\r\n\r\n") == b"0123456789"


@pytest.mark.parametrize("step", [1, 2, 3, 7, 64])
def test_any_split_gives_the_same_body(step: int) -> None:
    message = b"4\r\nwiki\r\n5;x=y\r\npedia\r\n0\r\nA: b\r\n\r\n"
    decoder = Decoder()
    assert _feed_all(decoder, message, step) == b"wikipedia"
    assert decoder.is_complete
    assert decoder.trailers == [("A", "b")]


def test_body_pieces_are_returned_as_soon_as_they_arrive() -> None:
    decoder = Decoder()
    assert decoder.feed(b"a\r\nhel") == [b"hel"]
    assert decoder.feed(b"lo") == [b"lo"]


def test_chunk_extensions_are_validated_and_ignored() -> None:
    message = b'5;name=value;flag ; q = "a \\" b"\r\nhello\r\n0;end\r\n\r\n'
    assert decode(message) == b"hello"


def test_trailers_are_kept_in_order_with_trimmed_values() -> None:
    message = b"3\r\nabc\r\n0\r\nX-Checksum:  42 \t\r\nX-Note:ok\r\nX-Empty:\r\n\r\n"
    decoder = Decoder()
    assert b"".join(decoder.feed(message)) == b"abc"
    assert decoder.trailers == [("X-Checksum", "42"), ("X-Note", "ok"), ("X-Empty", "")]


def test_trailer_values_keep_obs_text_as_latin_1() -> None:
    decoder = Decoder()
    decoder.feed(b"0\r\nX: caf\xe9 au lait\r\n\r\n")
    assert decoder.trailers == [("X", "caf\xe9 au lait")]


def test_trailers_returns_a_copy() -> None:
    decoder = Decoder()
    decoder.feed(b"0\r\nA: 1\r\n\r\n")
    decoder.trailers.clear()
    assert decoder.trailers == [("A", "1")]


def test_is_complete_is_false_until_the_final_crlf() -> None:
    decoder = Decoder()
    decoder.feed(b"3\r\nabc\r\n0\r\n")
    assert not decoder.is_complete
    decoder.feed(b"\r")
    assert not decoder.is_complete
    decoder.feed(b"\n")
    assert decoder.is_complete


def test_bytes_after_the_message_go_to_unused_data() -> None:
    decoder = Decoder()
    assert decoder.feed(b"1\r\nx\r\n0\r\n\r\nGET / HTTP/1.1") == [b"x"]
    assert decoder.unused_data == b"GET / HTTP/1.1"
    assert decoder.feed(b"\r\n") == []
    assert decoder.unused_data == b"GET / HTTP/1.1\r\n"


def test_unused_data_is_empty_before_completion() -> None:
    decoder = Decoder()
    decoder.feed(b"3\r\nabc\r\n0\r\nX: partial")
    assert decoder.unused_data == b""


def test_decode_rejects_bytes_after_the_message() -> None:
    with pytest.raises(ChunkedError, match="after the end"):
        decode(b"0\r\n\r\nGET / HTTP/1.1\r\n\r\n")


def test_decode_rejects_an_incomplete_message() -> None:
    with pytest.raises(ChunkedError, match="incomplete"):
        decode(b"5\r\nhello\r\n")


def test_a_failed_decoder_keeps_failing() -> None:
    decoder = Decoder()
    with pytest.raises(ChunkedError):
        decoder.feed(b"zz\r\n")
    with pytest.raises(ChunkedError, match="already failed"):
        decoder.feed(b"")


def test_feed_rejects_text() -> None:
    with pytest.raises(TypeError):
        Decoder().feed("5\r\nhello\r\n0\r\n\r\n")  # type: ignore[arg-type]
