# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- `encode` frames a byte string as a chunked body split into fixed-size pieces.
- `Decoder` incrementally decodes chunked bytes fed in any split, ignoring chunk
  extensions and trailer fields (RFC 7230 section 4.1).
- `decode` decodes a complete message in one call.
- `ChunkedError` is raised on a malformed size line or broken framing.
