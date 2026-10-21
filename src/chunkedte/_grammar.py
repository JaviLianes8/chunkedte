"""RFC 9112 and RFC 9110 grammar for size lines and field lines, as byte regexes."""

from __future__ import annotations

import re

from ._errors import QUOTE_LIMIT, ChunkedError, quote

# RFC 9110 section 5.6.2: tchar is any VCHAR except the delimiters.
TCHAR = rb"!#$%&'*+\-.^_`|~0-9A-Za-z"
TOKEN = rb"[" + TCHAR + rb"]+"
# RFC 9110 section 5.6.4: qdtext and quoted-pair; obs-text is %x80-FF.
QDTEXT = rb"[\t \x21\x23-\x5b\x5d-\x7e\x80-\xff]"
QUOTED_PAIR = rb"\\[\t \x21-\x7e\x80-\xff]"
QUOTED_STRING = rb'"(?:' + QDTEXT + rb"|" + QUOTED_PAIR + rb')*"'
BWS = rb"[ \t]*"
# RFC 9112 section 7.1.1: chunk-ext = *( BWS ";" BWS name [ BWS "=" BWS value ] ).
CHUNK_EXT = (
    rb"(?:" + BWS + rb";" + BWS + TOKEN
    + rb"(?:" + BWS + rb"=" + BWS + rb"(?:" + TOKEN + rb"|" + QUOTED_STRING + rb"))?)*"
)  # fmt: skip
SIZE_LINE = re.compile(rb"([0-9A-Fa-f]+)(" + CHUNK_EXT + rb")")
FIELD_NAME = re.compile(TOKEN + rb":")
# RFC 9110 section 5.5: field-vchar, SP and HTAB; the ends are checked by stripping OWS.
FIELD_VALUE = re.compile(rb"[\t \x21-\x7e\x80-\xff]*")
NOT_FIELD_VALUE = re.compile(rb"[^\t \x21-\x7e\x80-\xff]")
TOKEN_RE = re.compile(TOKEN)

# Fields needed before the content (framing, routing, connection control, authentication,
# request modifiers including the conditionals of RFC 9110 section 13, response controls,
# content format: RFC 9110 section 6.5.1) cannot be sent as trailers, so the encoder
# refuses them.
FORBIDDEN_TRAILERS = frozenset(
    {
        "authorization",
        "cache-control",
        "connection",
        "content-encoding",
        "content-length",
        "content-range",
        "content-type",
        "cookie",
        "expect",
        "host",
        "if-match",
        "if-modified-since",
        "if-none-match",
        "if-range",
        "if-unmodified-since",
        "keep-alive",
        "max-forwards",
        "proxy-authenticate",
        "proxy-authorization",
        "range",
        "set-cookie",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "www-authenticate",
    }
)


def parse_field_line(line: bytes) -> tuple[str, str]:
    """Split one trailer field line into its name and its OWS-trimmed value."""
    if line[:1] in (b" ", b"\t"):
        raise ChunkedError("obsolete line folding in the trailer section")
    match = FIELD_NAME.match(line)
    if match is None:
        # Never quote the line: a value, or a name and value without a colon, can be a secret.
        token = TOKEN_RE.match(line)
        at = token.end() if token else 0
        if at == len(line):
            raise ChunkedError("trailer field line has no colon")
        if at == 0 and line[:1] == b":":
            raise ChunkedError("empty trailer field name")
        raise ChunkedError(f"invalid byte 0x{line[at]:02x} at offset {at} in a trailer field name")
    name = line[: match.end() - 1].decode("ascii")
    value = line[match.end() :].strip(b" \t")
    _check_value(name, value)
    return name, value.decode("latin-1")


def format_field_line(name: str, value: str) -> bytes:
    """Validate one trailer field for sending and return ``name: value`` as bytes."""
    if not isinstance(name, str) or not isinstance(value, str):
        raise TypeError("trailer names and values must be str")
    if not name.isascii() or not TOKEN_RE.fullmatch(name.encode("ascii")):
        raise ChunkedError(f"trailer name is not a token: {quote(name)}")
    if name.lower() in FORBIDDEN_TRAILERS:
        raise ChunkedError(f"{name} cannot be sent as a trailer field")
    try:
        raw_value = value.encode("latin-1")
    except UnicodeEncodeError as error:
        where = f"offset {error.start} in the value of trailer field {_shown(name)}"
        raise ChunkedError(f"character at {where} is not latin-1") from None
    _check_value(name, raw_value)
    if raw_value != raw_value.strip(b" \t"):
        raise ChunkedError(
            f"whitespace at the start or end of the value of trailer field {_shown(name)}"
        )
    return name.encode("ascii") + b": " + raw_value


def _check_value(name: str, value: bytes) -> None:
    # Values can carry credentials, so the message gives the first bad byte, never the value.
    bad = NOT_FIELD_VALUE.search(value)
    if bad is not None:
        where = f"offset {bad.start()} in the value of trailer field {_shown(name)}"
        raise ChunkedError(f"invalid byte 0x{value[bad.start()]:02x} at {where}")


def _shown(name: str) -> str:
    return name if len(name) <= QUOTE_LIMIT else name[:QUOTE_LIMIT] + "..."
