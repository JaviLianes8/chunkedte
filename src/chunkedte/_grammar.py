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
TOKEN_RE = re.compile(TOKEN)

# Fields needed before the content (framing, routing, connection control, authentication,
# request modifiers, response controls, content format: RFC 9110 section 6.5.1) cannot be
# sent as trailers, so the encoder refuses them.
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
        raise ChunkedError(f"malformed trailer field line: {quote(line)}")
    value = line[match.end() :].strip(b" \t")
    if not FIELD_VALUE.fullmatch(value):
        raise ChunkedError(f"invalid byte in trailer field value: {quote(line)}")
    return line[: match.end() - 1].decode("ascii"), value.decode("latin-1")


def format_field_line(name: str, value: str) -> bytes:
    """Validate one trailer field for sending and return ``name: value`` as bytes."""
    if not isinstance(name, str) or not isinstance(value, str):
        raise TypeError("trailer names and values must be str")
    try:
        raw_name, raw_value = name.encode("ascii"), value.encode("latin-1")
    except UnicodeEncodeError:
        raise ChunkedError(f"trailer field {quote(name)} is not latin-1 text") from None
    if not TOKEN_RE.fullmatch(raw_name):
        raise ChunkedError(f"trailer name is not a token: {quote(name)}")
    if name.lower() in FORBIDDEN_TRAILERS:
        raise ChunkedError(f"{name} cannot be sent as a trailer field")
    if not FIELD_VALUE.fullmatch(raw_value) or raw_value != raw_value.strip(b" \t"):
        shown = name if len(name) <= QUOTE_LIMIT else name[:QUOTE_LIMIT] + "..."
        raise ChunkedError(f"invalid trailer value for {shown}: {quote(value)}")
    return raw_name + b": " + raw_value
