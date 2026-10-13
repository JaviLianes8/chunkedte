# chunkedte improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [x] Strict chunk-size line: HEXDIG only, chunk-ext grammar, CRLF only, size cap
- [x] Strict framing after chunk data and in the trailer section (field-line grammar, no obs-fold)
- [x] Limits (`Limits`, `LimitError`): line, total extensions, chunk size, body, trailer section
- [x] Linear time on hostile input (no rescans of buffered bytes)
- [x] Trailers exposed, bytes after the message kept apart (`unused_data`), `decode` rejects them
- [x] Encoder: incremental `Encoder`, trailers on `encode`, field validation
- [x] `is_chunked` for Transfer-Encoding and Content-Length (RFC 9112 section 6.1 and 6.3)
- [x] Command line tool (`python -m chunkedte`)
- [x] Contracts: fetched RFC grammar, advisory payloads, differential fuzz, typing, README, wheel e2e
- [x] Mutation run (guards removed one at a time, each must fail the suite)
- [x] Docs: README, CHANGELOG, docstrings, packaging metadata
- [x] Gates: ruff format, ruff check, mypy --strict, pytest
- [x] Independent review findings fixed with regression tests
- [x] Pull request opened (#2), guard clean

## Starting point

`0.1.0` (not on PyPI) ships `encode`, `decode`, `Decoder` and `ChunkedError`. Read as an
HTTP server or proxy author who feeds it attacker bytes, it has these gaps:

- The size is parsed with `int(token.strip(), 16)`. Python's `int` takes `+5`, `0x5`, `5_0`
  and surrounding whitespace, none of which is `1*HEXDIG`. This is the exact bug class of
  the waitress advisory below: two parsers that disagree on a chunk size disagree on where
  the next request starts.
- Everything after `;` is dropped unchecked, so a size line such as `5;\nxx` or `5;a b`
  passes. Lines are split on CRLF only, so a bare LF inside an extension is swallowed, the
  pattern of the aiohttp and netty advisories.
- Trailer lines are read but never checked: obs-fold, whitespace before the colon, a line
  without a colon and control bytes all pass. Trailers are thrown away, with no way to read
  them.
- No limits: an endless size line, endless extensions or an endless trailer section are
  buffered without bound (the Node.js advisory below), and the chunk size has no cap.
- A line split over many small feeds is searched from the start on every feed: quadratic.
- Bytes after the terminator stay in the buffer silently; `decode(b"0\r\n\r\nGET /")`
  returns `b""` with no error.
- The encoder cannot send trailers or stream; there is no help for the Transfer-Encoding
  and Content-Length decision that decides whether chunked applies at all.
- Packaging: no keywords or Python classifiers, README examples never run, no wheel test.

## Sources (fetched 2026-10-13)

- RFC 9112, https://www.rfc-editor.org/rfc/rfc9112.txt (sha256 `e4f426ba...`): section 7.1
  (chunked-body, chunk, chunk-size = 1*HEXDIG, last-chunk = 1*("0"), recipients must cope
  with large numerals), 7.1.1 (chunk-ext with BWS around `;` and `=`, token or quoted-string
  values, a server ought to limit the total extension length), 7.1.2 (trailer-section =
  *( field-line CRLF )), 7.1.3 (decoding pseudo-code), 2.2 (CRLF; a recipient MAY accept a
  bare LF, a bare CR is invalid), 5 and 5.1 (field-line, no whitespace before the colon),
  5.2 (obs-fold), 6.1 and 6.3 (Transfer-Encoding overrides Content-Length, both together
  ought to be an error, chunked must be the final coding of a request).
- RFC 9112 errata, https://www.rfc-editor.org/errata/rfc9112: two verified editorial errata
  (obs-text reference, a missing changes note), none on section 7. The page also lists
  RFC 9931 (March 2026) as updating RFC 9112; fetched from
  https://www.rfc-editor.org/rfc/rfc9931.txt, it covers optimistic protocol upgrades, not
  the chunked coding.
- RFC 9110, https://www.rfc-editor.org/rfc/rfc9110.txt (sha256 `21c1cdce...`): 5.5
  (field-value, field-vchar, obs-text), 5.6.2 (token, tchar), 5.6.3 (OWS, BWS), 5.6.4
  (quoted-string, qdtext, quoted-pair), 6.5 and 6.5.1 (trailer fields; fields for framing
  and routing cannot be sent as trailers).
- GHSA-4f7p-27jc-3c36 (waitress, CVE-2022-24761): `int()` accepted `+10` and `0x01` as
  sizes; extensions were dropped without validation.
- GHSA-vqfr-h8mv-ghfj (h11, CVE-2025-43859): any two bytes accepted after chunk data instead
  of CRLF; the advisory's payload `5\r\nAAAAAXX2\r\n45\r\n0\r\n\r\n` smuggles a request.
- GHSA-8495-4g3g-x7pr (aiohttp, CVE-2024-52304) and GHSA-fghv-69vj-qj49 (netty,
  CVE-2025-58056): a bare LF inside a chunk extension ended the size line.
- GHSA-g9pc-8g42-g6vq (Go net/http via RoadRunner, CVE-2025-22871): a bare LF accepted as the
  size line terminator.
- GHSA-prhj-8562-p8gj (Node.js, CVE-2024-22019): unbounded chunk extension bytes across a
  message exhausted CPU and bandwidth.
- GHSA-cggh-pq45-6h9x (llhttp, CVE-2023-30589): a bare CR accepted as a line terminator.

The RFC text is third-party: `scripts/fetch_upstream.py` fetches it into a gitignored
`tests/upstream/` folder checked against a tracked `MANIFEST.json` (URL, size, sha256,
licence); the tests that read it skip when it is absent. Advisory payloads are short test
vectors, cited with their URL next to them.

## Ranked brainstorm

1. **Strict size line** (correctness, smuggling). Size must fullmatch `1*HEXDIG`; extensions
   must match the RFC 9112 grammar exactly (BWS, token, quoted-string); the line ends only at
   CRLF; bare LF and bare CR are errors. No lenient switch: the advisories show that every
   leniency here is a desync with some other parser.
2. **Strict data terminator and trailer section.** Exactly CRLF after chunk data, failing on
   the first wrong byte. Trailer lines must be `token ":" OWS field-value OWS`; a line that
   starts with SP or HTAB (obs-fold) is rejected, as are control bytes.
3. **Limits** with safe defaults and a distinct `LimitError` (maps to 413/431 rather than
   400): one size line, total extension bytes per message, chunk size (default below
   2**63 so a value never wraps in a downstream 64-bit parser), body size, trailer section.
4. **Linear time.** Keep a scan offset so a line split over n feeds costs O(n), and fail as
   soon as the buffered line passes its limit instead of waiting for a CRLF.
5. **Trailers and pipelining.** `Decoder.trailers` returns the parsed fields in order;
   bytes after the final CRLF go to `Decoder.unused_data` (the next pipelined message), and
   `decode` raises if there are any.
6. **Encoder.** `Encoder.write` and `Encoder.finish(trailers)` for streaming; `encode` takes
   trailers. Names must be tokens, values field-values, and framing or routing fields
   (Content-Length, Transfer-Encoding, Trailer, Host) are refused as trailers.
7. **`is_chunked(transfer_encoding, content_length, request=True)`** applies RFC 9112 6.1
   and 6.3: both fields together is an error, chunked twice or not last in a request is an
   error, chunked with parameters is an error, a response with chunked not last is read to
   close (returns False).
8. **Typed API**: bytes-like input, `Limits` frozen dataclass, `py.typed`, mypy snippet test.
9. **CLI**: `python -m chunkedte decode|encode` over stdin and stdout, trailers on stderr.
10. **Contracts**: grammar classes checked against the fetched RFC ABNF, advisory payloads,
    a differential fuzz against an independent whole-message reference parser over random
    mutations and random splits, README examples executed, installed-wheel e2e, mutation run.
11. **Packaging**: keywords, classifiers, console script, CHANGELOG, version 0.2.0.

Out of scope: content codings (gzip inside chunked), HTTP header parsing beyond the two
framing fields, and any lenient mode.

## Mutation run

66 hand-written mutants (one guard, bound or grammar class changed at a time) over every
module, each run against the whole suite with bytecode writes off, `__pycache__` purged
and a per-mutant timeout; the suite was green before and after. 63 were killed at once.
Of the three survivors, one exposed a weak test (`unused_data` before completion was
checked with an empty buffer) and is now killed; one was a redundant type check in
`is_chunked` that the regex already enforces, now removed; the last (`\Z` to `$` in the
Transfer-Encoding list parser) is equivalent, because the zero-length-match guard rejects
the trailing newline either way.

## Independent review

One medium and eight low findings, all handled:

- `is_chunked` backtracked quadratically on long whitespace runs (two adjacent OWS runs in
  the list regex). Fixed by moving the trailing OWS inside the optional coding group;
  regression tests with 64 KiB of spaces and tabs.
- Transfer-Encoding errors echoed the whole field; now cut to 64 characters, with a test.
- The encoder refused only framing and routing trailers; it now refuses every RFC 9110
  section 6.5.1 category (authentication, request modifiers, response controls, content
  format), tested.
- The CLI failed on a latin-1 trailer with an ASCII terminal; trailer bytes outside ASCII
  are now escaped, tested.
- Documented: received trailers must stay apart from the header section, `feed` drops the
  pieces of the call that raises, the CLI may leave a truncated body on stdout on failure,
  and `is_chunked` leaves HEAD, 1xx, 204, 304, CONNECT and HTTP/1.0 to the caller.
- Kept on purpose: two wall-clock tests with generous bounds (they are the only way to
  catch a quadratic regression, and the mutation run showed they bite), CLI tests that use
  `tmp_path`, and Python 3.10 as the floor (the code uses `X | Y` type aliases).

