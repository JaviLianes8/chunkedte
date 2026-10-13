"""Check the decoder against the ABNF of RFC 9112 and RFC 9110, read from the pinned files.

The files are not committed (URL, size and sha256 in tests/upstream/MANIFEST.json); these
tests skip until `python scripts/fetch_upstream.py` has fetched them. Character classes
are read from the fetched rules and every one of the 256 byte values is tried.
"""

from __future__ import annotations

import re
import string
from collections.abc import Callable

import pytest

from chunkedte import ChunkedError, Decoder, is_chunked

# The rules of RFC 9112 section 7.1 the decoder implements, as printed in the section body
# of https://www.rfc-editor.org/rfc/rfc9112.txt (whitespace collapsed).
SECTION_7_1 = {
    "chunked-body": "*chunk last-chunk trailer-section CRLF",
    "chunk": "chunk-size [ chunk-ext ] CRLF chunk-data CRLF",
    "chunk-size": "1*HEXDIG",
    "last-chunk": '1*("0") [ chunk-ext ] CRLF',
    "chunk-data": "1*OCTET",
    "chunk-ext": '*( BWS ";" BWS chunk-ext-name [ BWS "=" BWS chunk-ext-val ] )',
    "chunk-ext-name": "token",
    "chunk-ext-val": "token / quoted-string",
    "trailer-section": "*( field-line CRLF )",
    "field-line": 'field-name ":" OWS field-value OWS',
}

# RFC 5234 Appendix B.1 core rules, written by hand (RFC 9110 section 1.2 cites them).
CORE = {
    "DIGIT": set(string.digits.encode()),
    "ALPHA": set(string.ascii_letters.encode()),
    "HTAB": {0x09},
    "SP": {0x20},
    "VCHAR": set(range(0x21, 0x7F)),
}


def _rule(text: str, name: str) -> str:
    """The first definition of ``name`` in a section body, continuation lines joined."""
    match = re.search(rf"^ {{5}}{re.escape(name)} +=(.*(?:\n {{9,}}\S.*)*)", text, re.M)
    assert match is not None, name
    # Drop ABNF comments (";" after whitespace, outside a quoted literal).
    lines = [re.sub(r"(^|\s);\s.*$", "", line) for line in match.group(1).splitlines()]
    return " ".join(" ".join(lines).split())


def _chars(rule: str, rfc9110: str) -> set[int]:
    """The octets an alternation of literals, ranges and named rules can match."""
    chars: set[int] = set()
    for item in re.findall(r'"[^"]+"|%x[0-9A-F]+(?:-[0-9A-F]+)?|[A-Za-z][\w-]*', rule):
        if item.startswith('"'):
            chars.add(ord(item[1]))
        elif item.startswith("%x"):
            low, _, high = item[2:].partition("-")
            chars.update(range(int(low, 16), int(high or low, 16) + 1))
        elif item == "obs-text":
            chars |= _chars(_rule(rfc9110, "obs-text"), rfc9110)
        else:
            chars |= CORE[item]
    return chars


def _accepted(build: Callable[[int], bytes]) -> set[int]:
    accepted = set()
    for value in range(256):
        try:
            Decoder().feed(build(value))
        except ChunkedError:
            continue
        accepted.add(value)
    return accepted


@pytest.mark.parametrize(("name", "expected"), SECTION_7_1.items())
def test_the_section_7_1_grammar_is_the_one_implemented(
    rfc9112: str, name: str, expected: str
) -> None:
    assert _rule(rfc9112, name) == expected


def test_chunk_size_digits_are_exactly_hexdig(rfc9112: str) -> None:
    described = re.search(r"HEXDIG \(hexadecimal ([^)]+)\)", rfc9112)
    assert described is not None and described.group(1) == "0-9/A-F/a-f"
    hexdig = set((string.digits + "ABCDEFabcdef").encode())
    assert _accepted(lambda b: bytes([b]) + b"\r\n") == hexdig


def test_extension_names_and_trailer_names_are_exactly_tchar(rfc9110: str) -> None:
    tchar = _chars(_rule(rfc9110, "tchar"), rfc9110)
    assert len(tchar) == 77
    assert _accepted(lambda b: b"1;" + bytes([b]) + b"\r\n") == tchar
    assert _accepted(lambda b: b"0\r\n" + bytes([b]) + b": v\r\n") == tchar


def test_transfer_coding_names_are_exactly_tchar(rfc9110: str) -> None:
    tchar = _chars(_rule(rfc9110, "tchar"), rfc9110)
    accepted = set()
    for value in range(256):
        try:
            is_chunked("a" + chr(value) + "b, chunked")
        except ChunkedError:
            continue
        accepted.add(value)
    # A comma only splits the coding in two list members.
    assert accepted == tchar | {ord(",")}


def test_quoted_string_octets_are_exactly_qdtext(rfc9110: str) -> None:
    qdtext = _chars(_rule(rfc9110, "qdtext"), rfc9110)
    assert _accepted(lambda b: b'1;a="' + bytes([b]) + b'"\r\n') == qdtext


def test_quoted_pair_octets_are_exactly_the_rfc_set(rfc9110: str) -> None:
    rule = _rule(rfc9110, "quoted-pair")
    assert rule.startswith('"\\" (')
    escaped = _chars(rule.split("(", 1)[1], rfc9110)
    assert _accepted(lambda b: b'1;a="\\' + bytes([b]) + b'"\r\n') == escaped


def test_whitespace_around_extension_delimiters_is_exactly_bws(rfc9110: str) -> None:
    ows = _chars(_rule(rfc9110, "OWS"), rfc9110)
    assert ows == {0x09, 0x20}
    assert _rule(rfc9110, "BWS") == "OWS"
    tchar = _chars(_rule(rfc9110, "tchar"), rfc9110)
    hexdig = set((string.digits + "ABCDEFabcdef").encode())
    # Next to a size or a token, a tchar or a hex digit only extends it.
    assert _accepted(lambda b: b"1" + bytes([b]) + b";a\r\n") == ows | hexdig
    assert _accepted(lambda b: b"1;" + bytes([b]) + b"a\r\n") == ows | tchar
    assert _accepted(lambda b: b"1;a" + bytes([b]) + b"=b\r\n") == ows | tchar
    assert _accepted(lambda b: b"1;a=" + bytes([b]) + b"b\r\n") == ows | tchar


def test_trailer_value_octets_are_exactly_field_vchar_sp_htab(rfc9110: str) -> None:
    vchar = _chars(_rule(rfc9110, "field-vchar"), rfc9110)
    allowed = vchar | CORE["SP"] | CORE["HTAB"]
    assert _accepted(lambda b: b"0\r\nX: a" + bytes([b]) + b"a\r\n") == allowed


def test_the_last_chunk_is_one_or_more_zeros(rfc9112: str) -> None:
    assert _rule(rfc9112, "last-chunk").startswith('1*("0")')
    for zeros in (1, 2, 5):
        decoder = Decoder()
        decoder.feed(b"0" * zeros + b"\r\n\r\n")
        assert decoder.is_complete


def test_the_decoding_pseudo_code_stops_at_the_empty_trailer_line(rfc9112: str) -> None:
    assert "while (trailer field is not empty)" in rfc9112
    decoder = Decoder()
    decoder.feed(b"0\r\nA: 1\r\n")
    assert not decoder.is_complete
    decoder.feed(b"\r\n")
    assert decoder.is_complete
