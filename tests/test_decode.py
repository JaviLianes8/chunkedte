import pytest

from chunkedte import ChunkedError, Decoder, decode


def test_decode_complete_message() -> None:
    assert decode(b"5\r\nhello\r\n0\r\n\r\n") == b"hello"


def test_decode_multiple_chunks() -> None:
    assert decode(b"3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n") == b"abcde"


def test_decode_empty_body() -> None:
    assert decode(b"0\r\n\r\n") == b""


def test_decode_fed_byte_by_byte() -> None:
    message = b"4\r\nwiki\r\n5\r\npedia\r\n0\r\n\r\n"
    decoder = Decoder()
    pieces: list[bytes] = []
    for byte in message:
        pieces.extend(decoder.feed(bytes([byte])))
    assert decoder.is_complete
    assert b"".join(pieces) == b"wikipedia"


def test_chunk_extensions_are_ignored() -> None:
    assert decode(b"5;name=value\r\nhello\r\n0\r\n\r\n") == b"hello"


def test_final_chunk_with_extension_is_detected() -> None:
    decoder = Decoder()
    decoder.feed(b"3\r\nabc\r\n0;done\r\n\r\n")
    assert decoder.is_complete


def test_trailers_are_consumed() -> None:
    message = b"3\r\nabc\r\n0\r\nX-Checksum: 42\r\nX-Note: ok\r\n\r\n"
    decoder = Decoder()
    assert b"".join(decoder.feed(message)) == b"abc"
    assert decoder.is_complete


def test_is_complete_is_false_until_terminator() -> None:
    decoder = Decoder()
    decoder.feed(b"3\r\nabc\r\n")
    assert not decoder.is_complete


def test_malformed_size_raises() -> None:
    with pytest.raises(ChunkedError):
        decode(b"zz\r\nhello\r\n0\r\n\r\n")


def test_missing_data_terminator_raises() -> None:
    with pytest.raises(ChunkedError):
        decode(b"5\r\nhelloXX0\r\n\r\n")


def test_incomplete_message_raises() -> None:
    with pytest.raises(ChunkedError):
        decode(b"5\r\nhello\r\n")


def test_feed_after_complete_raises() -> None:
    decoder = Decoder()
    decoder.feed(b"0\r\n\r\n")
    with pytest.raises(ChunkedError):
        decoder.feed(b"extra")
