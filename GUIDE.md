# chunkedte guide

The behaviour of every public name in detail. Each Python block below runs as a test: the
comment lines at its end hold what it prints.

## Decoding a stream: `Decoder`

`Decoder(limits=None)` reads one chunked message. `feed(data)` takes `bytes`, `bytearray`
or `memoryview` in any split, down to one byte at a time, and returns the body pieces that
became available, in order; the list can be empty. A piece is never held back waiting for
the rest of its chunk.

- `is_complete` turns `True` once the last chunk (`0`, or several zeros) and the trailer
  section, ending with an empty line, have been read.
- `trailers` lists the trailer fields as `(name, value)` pairs in arrival order. Names
  keep their case, values lose the spaces and tabs around them and are decoded as
  latin-1, so every byte survives. They are not merged into the header section (RFC 9110
  section 6.5.2 says not to): a `Content-Length` trailer must never reach your framing.
- `unused_data` holds the bytes after the message, for example a pipelined request. Bytes
  fed after completion are added there and nothing else happens.
- A size line or trailer line that breaks the grammar raises `ChunkedError` once the line
  is complete (its CRLF has arrived); the CRLF after chunk data is checked byte by byte.
  A bound raises `LimitError` as soon as it is certain to be passed, so a line is never
  buffered past its limit. The error class is the same whatever split the bytes arrive
  in. The pieces decoded during that call are dropped with it, and every later `feed`
  raises `ChunkedError` again, so a broken stream cannot be resumed by accident.

```python
from chunkedte import ChunkedError, Decoder

decoder = Decoder()
print(decoder.feed(b"6\r\nchun"), decoder.feed(b'ks\r\n0\r\nETag: "v1"\r\n\r\nNEXT'))
print(decoder.is_complete, decoder.trailers, decoder.unused_data)
broken = Decoder()
for part in (b"2\r\nab", b"XY", b"\r\n"):
    try:
        print(broken.feed(part))
    except ChunkedError as error:
        print(error)
# [b'chun'] [b'ks']
# True [('ETag', '"v1"')] b'NEXT'
# [b'ab']
# chunk data not followed by CRLF
# the decoder already failed: chunk data not followed by CRLF
```

## Decoding in one call: `decode`

`decode(data, *, limits=None)` feeds a whole message to a `Decoder` and returns the body.
It raises `ChunkedError` when the message is malformed, when it stops before its end, and
when bytes follow it; trailer fields are checked and dropped.

```python
from chunkedte import ChunkedError, decode

print(decode(b'3;name="quoted value"\r\nabc\r\n0\r\nX-Sum: 1\r\n\r\n'))
for message in (b"3\r\nabc\r\n", b"0\r\n\r\nGET /", b"3\r\nabc\r\n0\r\n\n"):
    try:
        decode(message)
    except ChunkedError as error:
        print(error)
# b'abc'
# incomplete chunked message
# bytes after the end of the chunked message
# bare LF in the trailer section
```

## The grammar it enforces

RFC 9112 section 7.1, byte for byte, with only CRLF ending a line:

- `chunk-size` is one or more hex digits, any case, leading zeros allowed. Nothing else:
  no sign, no `0x`, no underscore, no whitespace before or after.
- `chunk-ext` is `;` and a token, optionally `=` and a token or a quoted string. Spaces and
  tabs (BWS) may surround `;` and `=`, as the grammar allows. Extensions are checked and
  then ignored.
- Exactly CRLF follows the chunk data; the decoder fails on the first wrong byte instead
  of skipping two bytes.
- A trailer line is `name:value` with a token name, no space before the colon, and a value
  of visible characters, spaces, tabs and bytes 0x80 to 0xFF. A line starting with a space
  or tab (obs-fold) is refused.
- A bare LF, or a CR not followed by LF, anywhere a line is read is an error.

```python
from chunkedte import ChunkedError, decode

print(decode(b'0005 ; a = b ; c="d\\"e"\r\nhello\r\n000\r\n\r\n'))
for size_line in (b"+5", b"0x5", b"5 ", b"5;", b"5;a=", b"5;a b"):
    try:
        decode(size_line + b"\r\nhello\r\n0\r\n\r\n")
    except ChunkedError as error:
        print(error)
# b'hello'
# malformed chunk-size line: b'+5'
# malformed chunk-size line: b'0x5'
# malformed chunk-size line: b'5 '
# malformed chunk-size line: b'5;'
# malformed chunk-size line: b'5;a='
# malformed chunk-size line: b'5;a b'
```

## Bounds: `Limits` and `LimitError`

`Limits` is a frozen dataclass; every field is a non-negative `int` (`max_body_size` may
also be `None`, for no bound). A wrong type raises `TypeError`, a negative value
`ValueError`.

| Field | Default | Bounds |
| --- | --- | --- |
| `max_line_size` | 4096 | one chunk-size line, size and extensions, without its CRLF |
| `max_extensions_size` | 16384 | the extension bytes of all size lines of the message |
| `max_chunk_size` | 2\*\*63 - 1 | the value of one chunk size |
| `max_body_size` | `None` | the decoded body; checked when a size line arrives |
| `max_trailer_size` | 16384 | the trailer field lines, CRLFs included |

A line that cannot fit is refused as soon as that is certain, before its LF arrives. A
chunk size with more than 16 significant hex digits is always refused, and the default
`max_chunk_size` keeps a forwarded size below what a signed 64-bit parser can hold. A size
line split over many reads is scanned once, so decoding stays linear in the input.

```python
from chunkedte import Decoder, LimitError, Limits

for limits, data in [
    (Limits(max_line_size=8), b"1;abcdefgh"),
    (Limits(max_body_size=10), b"b\r\n"),
    (Limits(max_trailer_size=10), b"0\r\nX-Long: 123\r\n"),
    (Limits(), b"8000000000000000\r\n"),
]:
    try:
        Decoder(limits).feed(data)
    except LimitError as error:
        print(error)
# chunk-size line exceeds its limit
# body exceeds max_body_size
# trailer section exceeds its limit
# chunk size exceeds max_chunk_size
```

## Encoding: `Encoder` and `encode`

`Encoder().write(data)` frames one piece as one chunk, with the size in lower-case hex; an
empty piece gives `b""`, since a zero-size chunk would end the message. `finish(trailers)`
writes the last chunk, the trailer fields in the order given and the closing CRLF. After
`finish`, `write` and a second `finish` raise `ChunkedError`; a `finish` that refused a
trailer leaves the encoder open.

`encode(data, *, chunk_size=8192, trailers=None)` frames a whole body in pieces of
`chunk_size` bytes. `chunk_size` must be an `int` of at least 1.

Trailers are a mapping or an iterable of `(name, value)` pairs of `str`. A name must be a
token, a value latin-1 text of visible characters, spaces and tabs without spaces or tabs
at its ends. Fields that RFC 9110 section 6.5.1 needs before the content are refused:
framing and routing (`Content-Length`, `Transfer-Encoding`, `Trailer`, `TE`, `Host`,
`Connection`, `Keep-Alive`, `Upgrade`, `Max-Forwards`), authentication (`Authorization`,
`Proxy-Authorization`, `WWW-Authenticate`, `Proxy-Authenticate`, `Cookie`, `Set-Cookie`),
request modifiers and response controls (`Expect`, `Range`, `Cache-Control`, and the
conditionals `If-Match`, `If-None-Match`, `If-Modified-Since`, `If-Unmodified-Since` and
`If-Range`) and content format (`Content-Type`, `Content-Encoding`, `Content-Range`),
compared without case. The list is fixed; any other field a recipient needs before the
content is for the caller to keep out.

```python
from chunkedte import ChunkedError, Encoder, encode

print(encode(b"hello world", chunk_size=6, trailers=[("Digest", "sha-256=:x:")]))
encoder = Encoder()
for trailers in ({"Content-Length": "5"}, {"Bad Name": "1"}, {"X": "a\r\nInjected: 1"}):
    try:
        encoder.finish(trailers)
    except ChunkedError as error:
        print(error)
print(encoder.write(b"still open") + encoder.finish())
# b'6\r\nhello \r\n5\r\nworld\r\n0\r\nDigest: sha-256=:x:\r\n\r\n'
# Content-Length cannot be sent as a trailer field
# invalid byte 0x20 at offset 3 in a trailer field name
# invalid byte 0x0d at offset 1 in the value of trailer field X
# b'a\r\nstill open\r\n0\r\n\r\n'
```

## Is the body chunked? `is_chunked`

`is_chunked(transfer_encoding, content_length=None, *, request=True)` takes the two field
values as received (repeated lines joined with `", "`), or `None` for an absent field, and
applies RFC 9112 sections 6.1 and 6.3:

- no Transfer-Encoding: `False`, the body is framed some other way;
- both fields present: `ChunkedError`, the classic smuggling combination;
- chunked twice, chunked with parameters, or a value that is not a list of transfer
  codings: `ChunkedError`;
- chunked last: `True`;
- chunked missing or not last, or no coding listed at all (an empty value or only
  commas, which the list grammar allows): `ChunkedError` for a request, `False` for a
  response, whose body then runs until the connection closes.

`request` must be a `bool`; anything else raises `TypeError`.

Coding names are compared without case. The rest of section 6.3 stays with the caller:
responses to HEAD, 1xx, 204, 304 and 2xx to CONNECT have no body, and an HTTP/1.0 message
with Transfer-Encoding has faulty framing.

```python
from chunkedte import ChunkedError, is_chunked

print(is_chunked("gzip, CHUNKED"), is_chunked(None, "10"), is_chunked("gzip", request=False))
print(is_chunked("", request=False), is_chunked(" , ", request=False))
for value in ("chunked, gzip", "chunked;q=1", "gzip,, chunked x", ""):
    try:
        is_chunked(value)
    except ChunkedError as error:
        print(error)
# True False False
# False False
# chunked is not the final transfer coding of a request
# the chunked coding does not take parameters
# malformed Transfer-Encoding: 'gzip,, chunked x'
# Transfer-Encoding lists no transfer coding
```

## Errors and types

- `ChunkedError` is a `ValueError`; `LimitError` is a `ChunkedError`. A server can answer
  400 for the first and 413 or 431 for the second.
- Messages quote at most 64 characters of the offending input, followed by `...` when
  cut. They never quote a trailer value or a whole trailer line, which can hold
  credentials: they name the field (cut to 64 characters), the first bad byte in hex and
  its offset, for example `invalid byte 0x00 at offset 7 in the value of trailer field
  Authorization`.
- Arguments of the wrong type raise `TypeError`: data that is not `bytes`, `bytearray` or
  `memoryview`, a `limits` that is not a `Limits`, a field value that is neither `str`
  nor `None`, a `request` that is not a `bool`, trailers that are not a mapping or pairs.
- A `memoryview` is read as its bytes whatever its format or strides; a released one
  raises `ValueError` (not a `ChunkedError`).
- The package ships `py.typed` and passes `mypy --strict`.

## Command line

`chunkedte decode [FILE]` writes the body to stdout as decoded, with no newline added,
and the trailer fields to stderr, one `name: value` line each; bytes 0x80 to 0xFF are
written as `\xNN` escapes and a tab stays a tab. It stops reading once the message ends
and then checks for one more byte. `chunkedte encode [FILE] [--chunk-size N] [--trailer
NAME:VALUE ...]` frames the input as chunks of `N` bytes (the last may be shorter),
reading at most 64 KiB at a time; a `--trailer` is split at its first colon. Both read
stdin without a file. Exit status: 0 on success; 1 with a `chunkedte: ...` message on bad
input, a refused trailer or an unreadable file; 2 with a usage message on a bad command
line, including a `--chunk-size` that is not an integer of at least 1. Body bytes decoded
before an error may already be on stdout. `python -m chunkedte` is the same tool.

## How other parsers differ

Checked in the test suite against the parsers themselves, run on the same bytes:

- llhttp, the parser inside Node.js (9.4.2 in Node.js 24), refuses BWS around `;` and
  `=` in chunk extensions, which RFC 9112 allows, and lets through some extensions the
  grammar forbids (an empty name, an empty value, a quote inside a token). On everything
  else, including all of its own chunked test corpus, it gives the same verdict and the
  same body, trailers and message end.
- `h11` 0.16.0 refuses BWS before `;`, and accepts unchecked extensions, bare LF line
  ends in the trailer section and obs-fold; where both accept, the readings are the same.
- `http.client` reads the size with Python's `int`, so it accepts what `int(text, 16)`
  accepts, and skips the two bytes after the chunk data without looking at them.

## Stability

From 1.0.0 the eight public names, their parameters and defaults, the default limits, the
error types and the command line follow Semantic Versioning. Error message wording may
improve in minor releases; match on the exception type, not the text.
