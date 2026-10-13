"""Command line front end: ``chunkedte decode`` and ``chunkedte encode`` over files or stdio."""

from __future__ import annotations

import argparse
import sys
from typing import BinaryIO, TextIO

from ._decode import Decoder
from ._encode import DEFAULT_CHUNK_SIZE, Encoder, encode
from ._errors import ChunkedError

_BLOCK = 65536


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chunkedte", description="Decode or encode HTTP/1.1 chunked transfer coding."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    decode = commands.add_parser("decode", help="print the body; trailers go to stderr")
    decode.add_argument("file", nargs="?", help="input file (default: stdin)")
    encode = commands.add_parser("encode", help="frame the input as a chunked body")
    encode.add_argument("file", nargs="?", help="input file (default: stdin)")
    encode.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
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
    """Run the command line tool and return its exit status."""
    args = _parser().parse_args(argv)
    out = sys.stdout.buffer if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    source = (sys.stdin.buffer if stdin is None else stdin) if args.file is None else None
    try:
        if source is None:
            with open(args.file, "rb") as handle:
                return _run(args, handle, out, err)
        return _run(args, source, out, err)
    except (ChunkedError, ValueError, OSError) as error:
        print(f"chunkedte: {error}", file=err)
        return 1


def _run(args: argparse.Namespace, source: BinaryIO, out: BinaryIO, err: TextIO) -> int:
    if args.command == "decode":
        return _decode(source, out, err)
    if args.chunk_size <= 0:
        raise ValueError("--chunk-size must be positive")
    trailers = [_split_trailer(text) for text in args.trailer]
    closing = encode(b"", trailers=trailers)  # validates the trailers before any output
    encoder = Encoder()
    while block := source.read(args.chunk_size):
        out.write(encoder.write(block))
    out.write(closing)
    return 0


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
        raise ValueError(f"--trailer needs NAME:VALUE, got {text!r}")
    return name, value.strip(" \t")
