"""Command line front end: ``chunkedte decode`` and ``chunkedte encode`` over files or stdio."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from typing import BinaryIO, TextIO

from ._decode import Decoder
from ._encode import DEFAULT_CHUNK_SIZE, Encoder, encode
from ._errors import ChunkedError, quote

_BLOCK = 65536


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {quote(text)}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chunkedte", description="Decode or encode HTTP/1.1 chunked transfer coding."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    decode = commands.add_parser("decode", help="print the body; trailers go to stderr")
    decode.add_argument("file", nargs="?", help="input file (default: stdin)")
    encode = commands.add_parser("encode", help="frame the input as a chunked body")
    encode.add_argument("file", nargs="?", help="input file (default: stdin)")
    encode.add_argument("--chunk-size", type=_positive_int, default=DEFAULT_CHUNK_SIZE)
    encode.add_argument(
        "--trailer", action="append", default=[], metavar="NAME:VALUE", help="repeatable"
    )
    return parser


def main(
    argv: list[str] | None = None,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the command line tool and return its exit status.

    A bad command line exits with status 2 through :class:`SystemExit`, as argparse does.
    """
    args = _parser().parse_args(argv)
    out = sys.stdout.buffer if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    source = (sys.stdin.buffer if stdin is None else stdin) if args.file is None else None
    try:
        if source is None:
            with open(args.file, "rb") as handle:
                return _run(args, handle, out, err)
        return _run(args, source, out, err)
    except (ChunkedError, ValueError, OSError, MemoryError) as error:
        print(f"chunkedte: {error or type(error).__name__}", file=err)
        return 1


def _run(args: argparse.Namespace, source: BinaryIO, out: BinaryIO, err: TextIO) -> int:
    if args.command == "decode":
        return _decode(source, out, err)
    trailers = [_split_trailer(text) for text in args.trailer]
    closing = encode(b"", trailers=trailers)  # validates the trailers before any output
    encoder = Encoder()
    for chunk in _chunks(source, args.chunk_size):
        out.write(encoder.write(chunk))
    out.write(closing)
    return 0


def _chunks(source: BinaryIO, size: int) -> Iterator[bytes]:
    # Bounded reads: a huge --chunk-size must not allocate that much up front.
    while True:
        parts: list[bytes] = []
        have = 0
        while have < size and (block := source.read(min(size - have, _BLOCK))):
            parts.append(block)
            have += len(block)
        if parts:
            yield b"".join(parts)
        if have < size:
            return


def _decode(source: BinaryIO, out: BinaryIO, err: TextIO) -> int:
    decoder = Decoder()
    while not decoder.is_complete and (block := source.read(_BLOCK)):
        for piece in decoder.feed(block):
            out.write(piece)
    if not decoder.is_complete:
        raise ChunkedError("incomplete chunked message")
    if decoder.unused_data or source.read(1):
        raise ChunkedError("bytes after the end of the chunked message")
    for name, value in decoder.trailers:
        # Escape obs-text and C1 bytes so any terminal encoding can print them.
        safe = value.encode("latin-1").decode("ascii", "backslashreplace")
        print(f"{name}: {safe}", file=err)
    return 0


def _split_trailer(text: str) -> tuple[str, str]:
    name, colon, value = text.partition(":")
    if not colon:
        raise ValueError(f"--trailer needs NAME:VALUE, got {quote(text)}")
    return name, value.strip(" \t")
