"""An independent, whole-message reading of the RFC 9112 section 7.1 grammar, for fuzzing.

Hand-written from the ABNF byte by byte, without regular expressions and without any code
from the library, so the differential test compares two separate readings of the RFC.
"""

from __future__ import annotations

import string

HEXDIG = frozenset((string.digits + "abcdefABCDEF").encode())
TCHAR = frozenset((string.ascii_letters + string.digits + "!#$%&'*+-.^_`|~").encode())
WS = frozenset(b" \t")
OBS_TEXT = frozenset(range(0x80, 0x100))
VCHAR = frozenset(range(0x21, 0x7F))
QDTEXT = (frozenset(b"\t !") | frozenset(range(0x23, 0x5C)) | frozenset(range(0x5D, 0x7F))) | (
    OBS_TEXT
)
PAIR_CHAR = WS | VCHAR | OBS_TEXT
FIELD_CHAR = WS | VCHAR | OBS_TEXT


class Rejected(Exception):
    """The bytes are not a complete, valid chunked message."""


Result = tuple[bytes, list[tuple[str, str]], bytes]


def parse(message: bytes) -> Result:
    """Return the body, the trailer fields and the bytes after the message."""
    body = bytearray()
    at = 0
    while True:
        start = at
        while at < len(message) and message[at] in HEXDIG:
            at += 1
        if at == start:
            raise Rejected("chunk-size")
        size = int(message[start:at], 16)
        at = _crlf(message, _extensions(message, at))
        if size == 0:
            break
        if at + size > len(message):
            raise Rejected("short chunk-data")
        body += message[at : at + size]
        at = _crlf(message, at + size)
    trailers: list[tuple[str, str]] = []
    while message[at : at + 2] != b"\r\n":
        end = message.find(b"\r\n", at)
        if end == -1:
            raise Rejected("unterminated trailer")
        trailers.append(_field(message[at:end]))
        at = end + 2
    return bytes(body), trailers, message[at + 2 :]


def _skip_ws(message: bytes, at: int) -> int:
    while at < len(message) and message[at] in WS:
        at += 1
    return at


def _token(message: bytes, at: int) -> int:
    start = at
    while at < len(message) and message[at] in TCHAR:
        at += 1
    if at == start:
        raise Rejected("token")
    return at


def _quoted(message: bytes, at: int) -> int:
    at += 1
    while at < len(message):
        byte = message[at]
        if byte == 0x22:
            return at + 1
        if byte == 0x5C and at + 1 < len(message) and message[at + 1] in PAIR_CHAR:
            at += 2
        elif byte in QDTEXT:
            at += 1
        else:
            break
    raise Rejected("quoted-string")


def _extensions(message: bytes, at: int) -> int:
    while True:
        probe = _skip_ws(message, at)
        if message[probe : probe + 1] != b";":
            return at
        at = _token(message, _skip_ws(message, probe + 1))
        probe = _skip_ws(message, at)
        if message[probe : probe + 1] == b"=":
            value = _skip_ws(message, probe + 1)
            if message[value : value + 1] == b'"':
                at = _quoted(message, value)
            else:
                at = _token(message, value)


def _crlf(message: bytes, at: int) -> int:
    if message[at : at + 2] != b"\r\n":
        raise Rejected("CRLF")
    return at + 2


def _field(line: bytes) -> tuple[str, str]:
    name_end = 0
    while name_end < len(line) and line[name_end] in TCHAR:
        name_end += 1
    if name_end == 0 or line[name_end : name_end + 1] != b":":
        raise Rejected("field-name")
    value = line[name_end + 1 :]
    if any(byte not in FIELD_CHAR for byte in value):
        raise Rejected("field-value")
    start, end = 0, len(value)
    while start < end and value[start] in WS:
        start += 1
    while end > start and value[end - 1] in WS:
        end -= 1
    return line[:name_end].decode("ascii"), value[start:end].decode("latin-1")
