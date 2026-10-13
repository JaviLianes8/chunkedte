from __future__ import annotations

import pytest

from chunkedte import ChunkedError, Decoder, Encoder, decode, encode


def test_encode_frames_a_single_chunk() -> None:
    assert encode(b"hello") == b"5\r\nhello\r\n0\r\n\r\n"


def test_encode_splits_into_chunk_size_pieces() -> None:
    assert encode(b"abcde", chunk_size=2) == b"2\r\nab\r\n2\r\ncd\r\n1\r\ne\r\n0\r\n\r\n"


def test_encode_default_chunk_size_is_8192() -> None:
    assert encode(b"x" * 8193).startswith(b"2000\r\n")


def test_encode_empty_body_is_just_the_last_chunk() -> None:
    assert encode(b"") == b"0\r\n\r\n"


def test_encode_uses_lowercase_hex_size() -> None:
    assert encode(b"a" * 255, chunk_size=255).startswith(b"ff\r\n")


@pytest.mark.parametrize("size", [0, -1])
def test_encode_rejects_non_positive_chunk_size(size: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        encode(b"data", chunk_size=size)


@pytest.mark.parametrize("size", [True, 2.0, "2"])
def test_encode_rejects_non_int_chunk_size(size: object) -> None:
    with pytest.raises(TypeError):
        encode(b"data", chunk_size=size)  # type: ignore[arg-type]


@pytest.mark.parametrize("data", [5, "text", None])
def test_encode_rejects_non_bytes(data: object) -> None:
    with pytest.raises(TypeError):
        encode(data)  # type: ignore[arg-type]


def test_encode_accepts_bytearray_and_memoryview() -> None:
    assert encode(bytearray(b"ab")) == encode(memoryview(b"ab")) == b"2\r\nab\r\n0\r\n\r\n"


def test_encode_then_decode_round_trips() -> None:
    payload = bytes(range(256)) * 4
    assert decode(encode(payload, chunk_size=7)) == payload


def test_encode_writes_trailers_from_a_mapping_or_pairs() -> None:
    expected = b"1\r\nx\r\n0\r\nX-A: 1\r\nX-B: two words\r\n\r\n"
    assert encode(b"x", trailers={"X-A": "1", "X-B": "two words"}) == expected
    assert encode(b"x", trailers=[("X-A", "1"), ("X-B", "two words")]) == expected


def test_trailers_round_trip_through_the_decoder() -> None:
    decoder = Decoder()
    decoder.feed(encode(b"", trailers=[("Digest", "a=1"), ("X", ""), ("Y", "caf\xe9")]))
    assert decoder.trailers == [("Digest", "a=1"), ("X", ""), ("Y", "caf\xe9")]


@pytest.mark.parametrize(
    "name",
    [
        "Content-Length",
        "transfer-encoding",
        "Host",
        "TRAILER",
        "TE",
        "Connection",
        "Content-Type",
        "Content-Encoding",
        "Authorization",
        "Set-Cookie",
        "Cache-Control",
        "Max-Forwards",
    ],
)
def test_framing_and_routing_fields_are_refused_as_trailers(name: str) -> None:
    with pytest.raises(ChunkedError, match="cannot be sent as a trailer"):
        encode(b"", trailers={name: "1"})


@pytest.mark.parametrize("name", ["", "X Y", "X:", "X\r\n", "caf\xe9", "X(1)", "€"])
def test_trailer_names_must_be_tokens(name: str) -> None:
    with pytest.raises(ChunkedError):
        encode(b"", trailers={name: "1"})


@pytest.mark.parametrize("value", ["a\r\nX: y", "a\nb", "a\x00", " lead", "trail\t", "€"])
def test_trailer_values_must_be_clean_field_values(value: str) -> None:
    with pytest.raises(ChunkedError):
        encode(b"", trailers={"X": value})


@pytest.mark.parametrize("trailers", ["X: y", b"X: y", [("X", 1)], [(b"X", "y")]])
def test_badly_typed_trailers_raise_type_error(trailers: object) -> None:
    with pytest.raises(TypeError):
        encode(b"", trailers=trailers)  # type: ignore[arg-type]


def test_encoder_streams_chunks_then_finishes() -> None:
    encoder = Encoder()
    parts = [encoder.write(b"ab"), encoder.write(b""), encoder.write(memoryview(b"c"))]
    parts.append(encoder.finish({"X": "1"}))
    assert parts == [b"2\r\nab\r\n", b"", b"1\r\nc\r\n", b"0\r\nX: 1\r\n\r\n"]
    assert decode(b"".join(parts)) == b"abc"


def test_encoder_refuses_writes_after_finish() -> None:
    encoder = Encoder()
    encoder.finish()
    with pytest.raises(ChunkedError, match="after finish"):
        encoder.write(b"x")
    with pytest.raises(ChunkedError, match="twice"):
        encoder.finish()


def test_a_bad_trailer_leaves_the_encoder_open() -> None:
    encoder = Encoder()
    with pytest.raises(ChunkedError):
        encoder.finish({"Content-Length": "0"})
    assert encoder.finish() == b"0\r\n\r\n"


def test_encoder_write_rejects_non_bytes() -> None:
    with pytest.raises(TypeError):
        Encoder().write(3)  # type: ignore[arg-type]
