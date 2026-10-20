# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-20

The first stable release. The eight public names of 0.2.0 (`ChunkedError`, `Decoder`,
`Encoder`, `LimitError`, `Limits`, `decode`, `encode`, `is_chunked`), their signatures,
parameter names and defaults, the default limits and the command line are now stable and
follow Semantic Versioning. Everything 0.2.0 accepted and produced for valid input is
unchanged; the changes below only concern wrong argument types and error messages.

### Changed

- `Decoder(limits)` raises `TypeError` when `limits` is not a `Limits` (0.2.0 accepted
  anything and failed later with `AttributeError`).
- `Decoder.feed` and `decode` raise `TypeError` for anything but `bytes`, `bytearray` and
  `memoryview` (0.2.0 also took other buffer objects, such as `array.array`).
- `is_chunked` raises `TypeError` when a field value is neither `str` nor `None` (0.2.0
  raised a regular expression `TypeError` for `bytes` and treated any non-`None`
  Content-Length, such as an `int`, as present).
- `encode` and `Encoder.finish` raise `TypeError` for a trailer item that is not a
  two-item tuple or list (0.2.0 raised `ValueError` from unpacking, and split a
  two-character string into a name and a value).
- Error messages quote at most 64 characters of the input, followed by `...` when cut.
  0.2.0 quoted a refused trailer value or name, and a bad `--trailer` argument, in full.
- The public classes and functions report `chunkedte` as their module, so pickled
  `Limits` and errors do not depend on private module names.
- `python -m chunkedte` only runs the tool when executed, not when the module is imported.
- The package top holds only the public names (0.2.0 also exposed a stray `annotations`).

### Added

- Every public name, method and property has a docstring with an example that runs as a
  doctest.
- `GUIDE.md` describes every public name, the grammar, the limits and how other parsers
  differ; its examples run as tests.
- Tests against llhttp (the parser inside Node.js) and its own chunked test corpus, `h11`,
  `http.client` and the 0.2.0 release, run on the same bytes.

## [0.2.0]

### Added

- `Limits` and `LimitError`: bounds on one size line, all chunk extensions of a message,
  the chunk size (below 2**63 by default), the body and the trailer section.
- `Decoder.trailers` returns the trailer fields in arrival order; `Decoder.unused_data`
  holds the bytes after the message (a pipelined request, for example).
- `Encoder` streams chunks and closes the message with optional trailer fields; `encode`
  takes `trailers` too. Trailer names, values and framing fields are validated.
- `is_chunked` decides from Transfer-Encoding and Content-Length whether a body is chunked
  (RFC 9112 sections 6.1 and 6.3) and rejects the combinations used for smuggling.
- `chunkedte decode` and `chunkedte encode` on the command line, also `python -m chunkedte`.
- `decode`, `Decoder.feed` and `encode` accept `bytearray` and `memoryview`.

### Changed

- The decoder follows RFC 9112 section 7.1 strictly: the size is hex digits only (no `+`,
  `0x`, `_` or whitespace), extensions must match the grammar, only CRLF ends a line (bare
  LF and bare CR are errors), exactly CRLF must follow chunk data, and trailer lines must be
  valid field lines without obs-fold.
- `decode` raises when bytes follow the message; bytes fed to a finished `Decoder` go to
  `unused_data` instead of raising.
- A `Decoder` that raised keeps raising on every later `feed`.
- Lines split over many reads are scanned once, so decoding is linear in the input.
- `encode` rejects a non-int `chunk_size` and non bytes-like data with `TypeError`.

## [0.1.0]

- `encode` frames a byte string as a chunked body split into fixed-size pieces.
- `Decoder` incrementally decodes chunked bytes fed in any split, ignoring chunk
  extensions and trailer fields (RFC 7230 section 4.1).
- `decode` decodes a complete message in one call.
- `ChunkedError` is raised on a malformed size line or broken framing.
