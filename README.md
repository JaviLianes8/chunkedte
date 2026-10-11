# chunkedte

Incremental, typed, zero-dependency codec for HTTP/1.1 chunked transfer-encoding

## Install

```
pip install chunkedte
```

## Usage

Encode a byte string into a complete chunked body:

```python
from chunkedte import encode

encode(b"hello")
# b'5\r\nhello\r\n0\r\n\r\n'

encode(b"abcd", chunk_size=2)
# b'2\r\nab\r\n2\r\ncd\r\n0\r\n\r\n'
```

Decode a complete message in one call:

```python
from chunkedte import decode

decode(b"5\r\nhello\r\n0\r\n\r\n")
# b'hello'
```

Decode incrementally as bytes arrive off a socket. Feed any split, in any size,
and collect the body pieces as they become available:

```python
from chunkedte import Decoder

decoder = Decoder()
body = bytearray()
for part in stream:  # bytes in arbitrary splits
    for piece in decoder.feed(part):
        body += piece
assert decoder.is_complete
```

Chunk extensions (`5;name=value`) and trailer fields are consumed and ignored. A
size line that is not valid hexadecimal raises `ChunkedError`.

## Why

Chunked transfer-encoding is simple to frame and surprisingly easy to get wrong:
the terminating `0` chunk, the trailing blank line, chunk extensions and trailer
fields are routinely mishandled in hand-rolled parsers. The existing options are
either tied to one HTTP client (`lowhaio-chunked` is encode-only for lowhaio), a
server wrapper (`uwsgi-chunked` runs under uWSGI), or a full protocol state
machine (`h11`). This is a standalone, typed, zero-dependency codec: feed bytes,
get the body; give it bytes, get a chunked body. Reach for it when you move
chunked framing yourself and do not want to pull in an HTTP stack.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
