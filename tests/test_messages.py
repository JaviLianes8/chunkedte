"""Error messages stay short and quote only the start of a hostile input."""

from __future__ import annotations

import io
from collections.abc import Callable

import pytest

from chunkedte import ChunkedError, Decoder, Encoder, Limits, decode, encode, is_chunked
from chunkedte._cli import main

BIG = 200_000
LOOSE = Limits(max_line_size=10 * BIG, max_trailer_size=10 * BIG, max_extensions_size=10 * BIG)

CASES: dict[str, Callable[[], object]] = {
    "size line": lambda: decode(b"x" * BIG + b"\r\n", limits=LOOSE),
    "size line, digits": lambda: decode(b"1" * BIG + b";\r\n", limits=LOOSE),
    "trailer line": lambda: decode(b"0\r\n" + b"x" * BIG + b"\r\n\r\n", limits=LOOSE),
    "trailer value": lambda: decode(b"0\r\nA: " + b"\x00" * BIG + b"\r\n\r\n", limits=LOOSE),
    "encoder name": lambda: encode(b"", trailers={"(" * BIG: "v"}),
    "encoder value": lambda: encode(b"", trailers={"A": "\x00" * BIG}),
    "encoder value, huge name": lambda: encode(b"", trailers={"X" * BIG: "a\x00"}),
    "decoder value, huge name": lambda: decode(
        b"0\r\n" + b"X" * BIG + b": a\x00\r\n\r\n", limits=LOOSE
    ),
    "encoder edge whitespace": lambda: Encoder().finish({"A": " " * BIG}),
    "encoder non latin-1 name": lambda: encode(b"", trailers={"€" * BIG: "v"}),
    "transfer-encoding": lambda: is_chunked("x" * BIG + "\x00"),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_messages_quote_at_most_64_characters(name: str) -> None:
    with pytest.raises(ChunkedError) as caught:
        CASES[name]()
    message = str(caught.value)
    # 64 quoted characters take at most 4 * 64 once escaped, plus the explanation.
    assert len(message) < 400, (name, len(message))


def test_a_cut_quote_is_marked_and_a_short_one_is_not() -> None:
    with pytest.raises(ChunkedError) as caught:
        decode(b"g" * 65 + b"\r\n")
    assert str(caught.value) == f"malformed chunk-size line: b'{'g' * 64}'..."
    with pytest.raises(ChunkedError) as caught:
        decode(b"g" * 64 + b"\r\n")
    assert str(caught.value) == f"malformed chunk-size line: b'{'g' * 64}'"


def test_a_failed_decoder_repeats_the_short_message() -> None:
    decoder = Decoder()
    with pytest.raises(ChunkedError):
        decoder.feed(b"x" * 1000 + b"\r\n")
    with pytest.raises(ChunkedError) as caught:
        decoder.feed(b"")
    assert len(str(caught.value)) < 200


def test_the_command_line_quotes_a_bad_trailer_argument_briefly() -> None:
    err = io.StringIO()
    code = main(["encode", "--trailer", "x" * BIG], io.BytesIO(b""), io.BytesIO(), err)
    assert code == 1
    assert 0 < len(err.getvalue()) < 200


SECRET = "sk-live-SUPERSECRET-TOKEN-1234"


@pytest.mark.parametrize("argument", [SECRET, f"Authorization={SECRET}", f"X-Key {SECRET}"])
def test_a_trailer_argument_without_a_colon_is_never_echoed(argument: str) -> None:
    err = io.StringIO()
    code = main(["encode", "--trailer", argument], io.BytesIO(b""), io.BytesIO(), err)
    assert (code, err.getvalue()) == (1, "chunkedte: --trailer needs NAME:VALUE (no colon found)\n")
    assert SECRET not in err.getvalue()


class _NoMemory(io.BytesIO):
    def read(self, size: int | None = -1) -> bytes:
        raise MemoryError


@pytest.mark.parametrize("command", ["encode", "decode"])
def test_running_out_of_memory_names_the_error_and_exits_1(command: str) -> None:
    out, err = io.BytesIO(), io.StringIO()
    assert main([command], _NoMemory(), out, err) == 1
    assert (out.getvalue(), err.getvalue()) == (b"", "chunkedte: MemoryError\n")


def test_a_huge_non_integer_chunk_size_is_quoted_briefly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["encode", "--chunk-size", "x" * BIG], io.BytesIO(b""), io.BytesIO(), io.StringIO())
    err = capsys.readouterr().err
    assert caught.value.code == 2
    assert f"argument --chunk-size: not an integer: '{'x' * 64}'...\n" in err
    assert len(err) < 400


@pytest.mark.parametrize(
    ("line", "message"),
    [
        (b"NoColonHere", "trailer field line has no colon"),
        (b": v", "empty trailer field name"),
        (b"Bad Name: x", "invalid byte 0x20 at offset 3 in a trailer field name"),
        (b"\x00X: v", "invalid byte 0x00 at offset 0 in a trailer field name"),
    ],
)
def test_a_malformed_trailer_field_line_gets_its_exact_message(line: bytes, message: str) -> None:
    with pytest.raises(ChunkedError) as caught:
        decode(b"0\r\n" + line + b"\r\n\r\n")
    assert str(caught.value) == message


def test_a_non_latin_1_trailer_value_names_the_character_offset() -> None:
    with pytest.raises(ChunkedError) as caught:
        encode(b"", trailers={"X-Key": "ab\u20accd"})
    expected = "character at offset 2 in the value of trailer field X-Key is not latin-1"
    assert str(caught.value) == expected
