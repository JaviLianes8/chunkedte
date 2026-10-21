# chunkedte

[![Lianes8 Certified](https://lianes8studio.com/certified/lianes8-certified-badge.svg)](https://lianes8studio.com/certified)

Strict, incremental, typed, zero-dependency codec for HTTP/1.1 chunked transfer coding
(RFC 9112 section 7.1).

## Install

```
pip install chunkedte
```

Python 3.10 or newer. No dependencies.

## Usage

Decode a complete message in one call. `decode` raises `ChunkedError` if the message is
malformed, unfinished, or followed by more bytes:

```python
from chunkedte import ChunkedError, decode

print(decode(b"5\r\nhello\r\n0\r\n\r\n"))
try:
    decode(b"0x5\r\nhello\r\n0\r\n\r\n")
except ChunkedError as error:
    print(error)
# b'hello'
# malformed chunk-size line: b'0x5'
```

Decode incrementally as bytes arrive off a socket. `Decoder.feed` takes any split and
returns the body pieces available so far; trailer fields and whatever follows the message
(a pipelined request, say) are kept apart:

```python
from chunkedte import Decoder

decoder = Decoder()
body = b""
for part in [b"4\r\nwi", b"ki\r\n5;sig=ab\r\npedia\r\n0\r\nDigest: x\r\n", b"\r\nGET /"]:
    for piece in decoder.feed(part):
        body += piece
print(body, decoder.is_complete)
print(decoder.trailers, decoder.unused_data)
# b'wikipedia' True
# [('Digest', 'x')] b'GET /'
```

Bound what a peer can make you buffer. Passing a bound raises `LimitError`, a subclass of
`ChunkedError`, so a server can answer 413 or 431 instead of 400:

```python
from chunkedte import Decoder, LimitError, Limits

decoder = Decoder(Limits(max_body_size=1024, max_trailer_size=4096))
try:
    decoder.feed(b"10000\r\n")
except LimitError as error:
    print(error)
print(Limits())
# body exceeds max_body_size
# Limits(max_line_size=4096, max_extensions_size=16384, max_chunk_size=9223372036854775807, max_body_size=None, max_trailer_size=16384)
```

Encode in one call, or stream with `Encoder` and close with optional trailer fields:

```python
from chunkedte import Encoder, encode

print(encode(b"abcd", chunk_size=2))
encoder = Encoder()
print(encoder.write(b"hello") + encoder.finish({"X-Checksum": "42"}))
# b'2\r\nab\r\n2\r\ncd\r\n0\r\n\r\n'
# b'5\r\nhello\r\n0\r\nX-Checksum: 42\r\n\r\n'
```

Decide whether a message body is chunked at all from its Transfer-Encoding and
Content-Length values (`None` when absent). `is_chunked` applies RFC 9112 sections 6.1 and
6.3 and raises `ChunkedError` on the combinations used for request smuggling:

```python
from chunkedte import ChunkedError, is_chunked

print(is_chunked("gzip, chunked"), is_chunked(None, "12"))
print(is_chunked("gzip", request=False))
for te, cl in [("chunked", "12"), ("chunked, chunked", None), ("chunked, gzip", None)]:
    try:
        is_chunked(te, cl)
    except ChunkedError as error:
        print(error)
# True False
# False
# both Transfer-Encoding and Content-Length are present
# chunked is applied more than once
# chunked is not the final transfer coding of a request
```

### Command line

```
$ printf '5\r\nhello\r\n0\r\nX-Sum: 1\r\n\r\n' > message.bin
$ chunkedte decode message.bin 2>/dev/null; echo
hello
$ chunkedte decode message.bin 2>&1 >/dev/null
X-Sum: 1
$ printf 'abc' | chunkedte encode --chunk-size 2 --trailer "X-Sum: 1" | od -c
0000000   2  \r  \n   a   b  \r  \n   1  \r  \n   c  \r  \n   0  \r  \n
0000020   X   -   S   u   m   :       1  \r  \n  \r  \n
0000034
```

`decode` writes the body to stdout exactly as decoded (no newline is added) and the
trailer fields to stderr, one `name: value` line each, with bytes 0x80 to 0xFF written as
`\xNN` escapes (a tab stays a tab). `encode` frames stdin (or a file) as a chunked body.
Both exit with status 0 on success, 1 with a `chunkedte: ...` message on bad input, and 2
with a usage message on a bad command line (such as a `--chunk-size` below 1). Body bytes
decoded before an error may already be on stdout, so treat the output of a failed run as
truncated. `python -m chunkedte` works too.

## What "strict" means here

Every leniency in a chunked parser is a way for two HTTP processors to disagree on where a
message ends, which is how request smuggling works. So the decoder rejects:

- a chunk size that is not only hex digits (`+5`, `0x5`, `5_0`, ` 5`, `5 `);
- chunk extensions that do not follow the grammar (whitespace is allowed only around `;`
  and `=`, values are tokens or quoted strings);
- a bare LF or a bare CR anywhere a CRLF is expected, including inside an extension;
- anything other than CRLF right after the chunk data;
- trailer lines that are not `name: value`, with whitespace before the colon, with control
  bytes, or folded onto a continuation line (obs-fold).

Extensions are validated and then ignored, as RFC 9112 asks. The default `Limits` cap one
size line at 4 KiB, all extensions of a message at 16 KiB, the trailer section at 16 KiB and
a chunk size below 2**63 (so a forwarded size never wraps in a 64-bit parser); the body is
unbounded unless you set `max_body_size`. A line split over many small reads is scanned
once, so decoding stays linear in the input. When `feed` raises, the pieces decoded in that
call are dropped with it. Received trailers are returned as they came: RFC 9110 section
6.5.2 says not to merge them into the header section, so keep them apart (a `Content-Length`
trailer, say, must never reach your framing logic). The encoder refuses trailer names that
are not tokens, values with control bytes or edge whitespace, and the fields RFC 9110
section 6.5.1 needs before the content: framing and routing (Content-Length,
Transfer-Encoding, Trailer, TE, Host, Connection, Keep-Alive, Upgrade, Max-Forwards),
authentication (Authorization, Proxy-Authorization, WWW-Authenticate, Proxy-Authenticate,
Cookie, Set-Cookie), request modifiers and response controls (Expect, Range,
Cache-Control, and the conditionals If-Match, If-None-Match, If-Modified-Since,
If-Unmodified-Since and If-Range) and content format (Content-Type, Content-Encoding,
Content-Range). That is a fixed list: other fields a recipient needs before the content
are yours to keep out of the trailers.
`is_chunked` leaves the rest of RFC 9112 section 6.3 to you: responses to HEAD, 1xx, 204,
304 and 2xx to CONNECT carry no body, and an HTTP/1.0 message with Transfer-Encoding has
faulty framing. There is no lenient mode.

## API and guarantees

Eight names, stable since 1.0.0: `decode`, `Decoder`, `encode`, `Encoder`, `is_chunked`,
`Limits`, `ChunkedError` and `LimitError`. Wrong argument types raise `TypeError`, every
problem with the bytes or the fields raises `ChunkedError` (a `ValueError`), and a passed
bound raises its subclass `LimitError`, whatever split the bytes arrived in. Messages
quote at most 64 characters of the input and never quote a trailer value or a trailer
line, which can hold credentials: they name the field, the bad byte and its offset.
The [GUIDE](https://github.com/JaviLianes8/chunkedte/blob/main/GUIDE.md) describes each
name in detail and the [CHANGELOG](https://github.com/JaviLianes8/chunkedte/blob/main/CHANGELOG.md)
what changed between releases.

## Why

Chunked transfer coding is simple to frame and easy to get subtly wrong, and every
leniency is a way for two parsers to disagree on where a message ends. The chunked
decoders most Python code reaches today sit inside an HTTP stack and are lenient.
`http.client` in the standard library (checked on CPython 3.13) reads the chunk sizes
`+5`, `0x5`, `0_5` and ` 5`, ends a size line at a bare LF and skips whatever two bytes
follow the chunk data. `h11` (checked on 0.16.0) decodes chunks only inside its
connection object, does not check chunk extensions, accepts a bare LF at the end of the
trailer section and unfolds obs-fold trailer lines. `chunkedte` is a standalone, typed,
zero-dependency codec that accepts exactly the RFC 9112 grammar, bounds what a peer can
make you buffer, and gives you the trailers and the bytes after the message. It is tested
against the RFC text itself, the llhttp parser inside Node.js and its test corpus, `h11`,
`http.client` and the 0.2.0 release.

## Development

`python scripts/fetch_upstream.py` downloads RFC 9112, RFC 9110 and the llhttp test files
listed in `tests/upstream/MANIFEST.json` (they are not part of the repository; their tests
skip without them). With Node.js on the `PATH` the tests also run llhttp, and with `h11`
installed they compare against it. Set `CHUNKEDTE_V02` to an unpacked 0.2.0 wheel to
compare with that release. `scripts/check.ps1` runs format, lint, types and tests. Set
`CHUNKEDTE_E2E=1` to also build the wheel and sdist and test the installed package.

## License

MIT. See [LICENSE](https://github.com/JaviLianes8/chunkedte/blob/main/LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
