import pytest

from chunkedte import decode, encode


def test_encode_frames_a_single_chunk() -> None:
    assert encode(b"hello") == b"5\r\nhello\r\n0\r\n\r\n"


def test_encode_splits_into_chunk_size_pieces() -> None:
    assert encode(b"abcd", chunk_size=2) == b"2\r\nab\r\n2\r\ncd\r\n0\r\n\r\n"


def test_encode_empty_body_is_just_the_terminator() -> None:
    assert encode(b"") == b"0\r\n\r\n"


def test_encode_uses_lowercase_hex_size() -> None:
    assert encode(b"a" * 255, chunk_size=255).startswith(b"ff\r\n")


def test_encode_rejects_non_positive_chunk_size() -> None:
    with pytest.raises(ValueError):
        encode(b"data", chunk_size=0)


def test_encode_then_decode_round_trips() -> None:
    payload = bytes(range(256)) * 4
    assert decode(encode(payload, chunk_size=7)) == payload
