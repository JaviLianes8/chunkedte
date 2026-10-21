"""Decide from Transfer-Encoding and Content-Length whether a body is chunked."""

from __future__ import annotations

import re

from ._errors import ChunkedError, quote

_TOKEN = r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+"
_QUOTED = r'"(?:[\t \x21\x23-\x5b\x5d-\x7e\x80-\xff]|\\[\t \x21-\x7e\x80-\xff])*"'
# RFC 9110 section 10.1.4: transfer-coding = token *( OWS ";" OWS transfer-parameter ).
_CODING = re.compile(rf"({_TOKEN})((?:[ \t]*;[ \t]*{_TOKEN}[ \t]*=[ \t]*(?:{_TOKEN}|{_QUOTED}))*)")
# The trailing OWS sits inside the optional group: two adjacent OWS runs backtrack
# quadratically on a long run of spaces.
_MEMBER = re.compile(rf"[ \t]*(?:{_CODING.pattern}[ \t]*)?(?:,|\Z)")


def is_chunked(
    transfer_encoding: str | None,
    content_length: str | None = None,
    *,
    request: bool = True,
) -> bool:
    """Whether a message body is framed by the chunked coding (RFC 9112 sections 6.1, 6.3).

    Pass the field values as received, joining repeated lines with ``", "``, or ``None``
    when a field is absent. Returns ``False`` when there is no Transfer-Encoding, and for a
    response whose final coding is not chunked, or that lists no coding at all (it is read
    until the connection closes). Raises :class:`ChunkedError` when both fields are
    present, when chunked is applied twice or carries parameters, when a request's final
    coding is not chunked or it lists none, and when the field is not a valid list of
    transfer codings.

    The caller still applies the rest of RFC 9112 section 6.3: responses to HEAD, 1xx, 204,
    304 and 2xx to CONNECT have no body, and an HTTP/1.0 message with Transfer-Encoding has
    faulty framing (section 6.1). Field values that are not ``str`` or ``None``, and a
    ``request`` that is not a ``bool``, raise :class:`TypeError`.

    >>> from chunkedte import ChunkedError, is_chunked
    >>> is_chunked("gzip, chunked"), is_chunked(None, "12"), is_chunked("gzip", request=False)
    (True, False, False)
    >>> try:
    ...     is_chunked("chunked", "12")
    ... except ChunkedError as error:
    ...     print(error)
    both Transfer-Encoding and Content-Length are present
    """
    for field in (transfer_encoding, content_length):
        if field is not None and not isinstance(field, str):
            raise TypeError(f"field values must be str or None, got {type(field).__name__}")
    if not isinstance(request, bool):
        raise TypeError(f"request must be a bool, got {type(request).__name__}")
    if transfer_encoding is None:
        return False
    if content_length is not None:
        raise ChunkedError("both Transfer-Encoding and Content-Length are present")
    codings = _parse_codings(transfer_encoding)
    if not codings and request:
        raise ChunkedError("Transfer-Encoding lists no transfer coding")
    chunked = [index for index, (name, _) in enumerate(codings) if name == "chunked"]
    if len(chunked) > 1:
        raise ChunkedError("chunked is applied more than once")
    if chunked and codings[chunked[0]][1]:
        raise ChunkedError("the chunked coding does not take parameters")
    if chunked and chunked[0] == len(codings) - 1:
        return True
    if request:
        raise ChunkedError("chunked is not the final transfer coding of a request")
    return False


def _parse_codings(value: str) -> list[tuple[str, str]]:
    codings: list[tuple[str, str]] = []
    position = 0
    while position < len(value):
        match = _MEMBER.match(value, position)
        if match is None or match.end() == position:
            raise ChunkedError(f"malformed Transfer-Encoding: {quote(value)}")
        if match.group(1) is not None:
            codings.append((match.group(1).lower(), match.group(2)))
        position = match.end()
    return codings
