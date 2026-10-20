# chunkedte 1.0.0 certification report

The 1.0.0 certification bar (19 items) applied to chunkedte. PyPI has 0.2.0, whose modules
are byte for byte those of the `main` branch at cb5707c (the wheel unpacked and compared
with the tree), so every change listed here is a change against the PyPI release.

Progress:
- [x] Branch `release/1.0.0` created from `main` (cb5707c, same code as PyPI 0.2.0)
- [x] Baseline gates on 0.2.0
- [x] API review and 1.0.0 changes (item 1)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Ground truth: specifications fetched live, reference parsers run (item 7)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [ ] Packaging, e2e and upgrade from PyPI 0.2.0, every Python (items 8, 10, 13, 14)
- [ ] Gates (item 15)
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)
- [ ] PR and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Scorecard

| # | Item | Result |
| --- | --- | --- |
| 1 | Public API reviewed for stability | PASS: the eight names of 0.2.0, signatures, parameter names and defaults kept and pinned; every change in CHANGELOG |
| 2 | `__all__` exact, no private imports in docs | PASS: the package top holds exactly `__all__` (checked from the installed wheel too) |
| 3 | Docstrings with runnable examples, doctests | PASS: 14 doctests; README (5 blocks) and GUIDE (6 blocks) run as tests |
| 4 | Typed end to end | PASS: `mypy --strict src tests`, `py.typed`, typing checked from a consumer of the installed wheel |
| 5 | Typed, documented, bounded errors | PASS: `ChunkedError` (a `ValueError`), `LimitError`, `TypeError` for wrong types; messages quote at most 64 characters |
| 6 | Contract tests of every public name | PASS |
| 7 | Real ground truth | PASS: RFC 9112 and RFC 9110 fetched, llhttp test corpus fetched, llhttp (Node.js), h11 and http.client run live, PyPI 0.2.0 as an oracle |
| 8 | Real e2e from the wheel | see Packaging |
| 9 | Seeded fuzz, no crash, hang or blowup | PASS |
| 10 | Supported Pythons | see Packaging |
| 11 | README and `twine check` | PASS: `twine check --strict` in the e2e test, absolute links pinned by a test |
| 12 | Dated CHANGELOG section | PASS: 1.0.0, 2026-10-20 |
| 13 | pyproject 1.0.0, Production/Stable | PASS |
| 14 | sdist and wheel contents | PASS: pinned by `tests/test_e2e_wheel.py` |
| 15 | Gates each exit 0 | see Gates |
| 16 | Independent reviewer | pending |
| 17 | PR and trace guard | pending |
| 18 | Contracts bite (mutations) | PASS: author round 40 of 40 killed |
| 19 | Five independent QA lenses | pending |

## Baseline on 0.2.0 (before any change)

On this PC, CPython 3.13.2, at cb5707c: `ruff format --check .`, `ruff check .` and
`mypy --strict src tests` exit 0; `pytest` 282 passed, 1 skipped (the installed-wheel
test, which needs `CHUNKEDTE_E2E=1`); no doctests existed.

Defects found in 0.2.0 by reading and then reproducing:

- `Decoder(5)` was accepted and failed later, at the first `feed`, with `AttributeError`.
- `is_chunked(b"chunked")` raised a regular expression `TypeError`; `is_chunked("chunked", 5)`
  read the `int` as a present Content-Length.
- `encode(b"x", trailers=["ab"])` sent a trailer `a: b`; a three-item pair raised
  `ValueError` from unpacking instead of a `TypeError`.
- Error messages quoted a refused trailer value in full: a 200,000 character value gave a
  500,031 character `ChunkedError` message; the same for a non-token trailer name and a
  bad `--trailer` argument.
- The public classes reported private modules (`chunkedte._errors.ChunkedError`), so a
  pickle depended on them; `chunkedte/__main__.py` ran the tool when imported (doctest
  collection would have hung on stdin); the package top exposed a stray `annotations`.
- No public docstring had a runnable example; the README linked LICENSE relatively,
  which breaks on PyPI; there was no GUIDE.

## API review (item 1)

Kept: the eight public names of 0.2.0 with their signatures, parameter names and defaults
(pinned by `tests/test_contract_api.py`), the `Limits` fields and defaults, the error
hierarchy and the command line. Changed, all in the CHANGELOG: `TypeError` for a
non-`Limits` `limits`, for data other than `bytes`, `bytearray` and `memoryview`, for
`is_chunked` field values that are not `str` or `None`, and for trailer items that are not
two-item tuples or lists; messages quote at most 64 characters; public names report
`chunkedte` as their module; `python -m chunkedte` runs only when executed; no stray
`annotations`. Internal: line reading moved to `_lines.py` and `decode` to `_oneshot.py`
so every file stays under 200 lines with the new examples. Valid input decodes and
encodes exactly as in 0.2.0 (checked against the release, below).

## Ground truth (item 7)

Fetched by `scripts/fetch_upstream.py` into the ignored `tests/upstream` folder;
`tests/upstream/MANIFEST.json` records URL, revision, date, size, sha256 and licence and
the tests check the hash before reading. Nothing fetched is committed or shipped.

- RFC 9112 and RFC 9110 (https://www.rfc-editor.org/rfc/rfc9112.txt and rfc9110.txt,
  first fetched 2026-10-13, fetched again 2026-10-21 with the same sha256):
  `tests/test_upstream.py` reads the section 7.1 rules and the `tchar`, `qdtext`,
  `quoted-pair`, `OWS`/`BWS`, `field-vchar` and `obs-text` rules from the text and tries
  all 256 byte values at every position they govern.
- llhttp test corpus (https://raw.githubusercontent.com/nodejs/llhttp/v9.4.2/test/request/transfer-encoding.md
  and the `response` file, fetched 2026-10-21, tag v9.4.2, the llhttp of Node.js 24, MIT):
  `tests/test_llhttp_corpus.py` rebuilds every input the way llhttp's `test/md-test.ts`
  does and takes the 22 chunked bodies of the strict parser modes (7 complete, 10 errors,
  5 unfinished); the body and trailers expected are cut from the input at the offsets the
  log gives. All 22 get llhttp's verdict, body and trailers.
- llhttp run live (Node.js 24.18.0, llhttp 9.4.2, `tests/oracles/llhttp_oracle.js`, fed
  one byte at a time): 3,000 valid generated messages decode identically (body, trailer
  fields, message end); 24,000 mutated messages agree except in two documented ways, both
  checked case by case: llhttp refuses BWS around `;` and `=` in chunk extensions (allowed
  by RFC 9112), and lets through extension text the grammar forbids (an empty name, an
  empty value, a quote inside a token), which the hand-written RFC reading in
  `tests/reference.py` refuses too.
- h11 0.16.0 run live: on 24,000 mutated messages every message both accept is read the
  same way (body, trailers, message end); h11 refuses BWS before `;`, and the messages only
  h11 accepts are refused by the RFC reading as well. 3,000 valid messages agree.
- `http.client` (CPython 3.13.2) reads the same body from 3,000 valid messages; the README
  comparison of its leniencies and of h11's is pinned by tests.
- PyPI 0.2.0 as an oracle (`tests/test_upgrade.py`, `CHUNKEDTE_V02`): 20,030 messages fed
  in random splits, 5,000 `encode` calls and 5,000 `is_chunked` calls give the same
  results and the same errors (messages compared up to the new `...` mark); the documented
  changes are checked one by one.

## Fuzz and hostile input (item 9)

`tests/test_fuzz.py`: 4,000 seeded mutations against the hand-written RFC reading, with
random splits, every split point of one message, and 200 encode round trips.
`tests/test_hostile.py`: 18 hostile shapes timed at 50,000 and 200,000 units (tiny chunks
whole and byte by byte, extension lists, unclosed quoted pairs, BWS runs, leading zeros,
many trailers, long trailer values, data after the message, one big chunk byte by byte,
`is_chunked` lists, commas, spaces and parameters, `encode`); the ratio stays under 8
(linear is about 4). Three seeds of 3,000 random inputs through every entry point raise
nothing but the documented errors. `tests/test_messages.py`: 200,000 byte inputs in every
error path give messages under 400 characters.

## Author mutation round (item 18)

40 mutants over every module, each applied alone to a fresh clone of the pushed branch on
another machine (the laptop and Elena's PC, CPython 3.14), the full suite (fetched sources,
Node.js llhttp, h11 and the 0.2.0 oracle present) run with `-x` and a 300 s per-test
limit. All 40 killed. M18 and M22 were first killed only by the 0.2.0 oracle; direct
contracts were added for them (obs-fold starting with a tab, quoted pairs of obs-text,
tab and space) and kill both on their own.

| Id | Module | Mutation | Caught by |
| --- | --- | --- | --- |
| M1 | `_lines.py` | bare LF at the start of the buffer not checked | `test_strict::test_a_bare_lf_as_the_first_byte_of_a_line_is_rejected` |
| M2 | `_lines.py` | unfinished line allowed one byte more | `test_docs::test_each_guide_example_prints_what_its_comments_show[3]` |
| M3 | `_lines.py` | a line exactly at the limit refused | `test_limits::test_a_size_line_at_the_limit_passes_and_one_byte_more_fails` |
| M4 | `_lines.py` | bare CR inside a line accepted | `test_strict::test_a_bare_cr_in_a_size_line_is_rejected` |
| M5 | `_decode.py` | bytes after chunk data checked only once two arrived | `test_strict::test_a_wrong_byte_after_chunk_data_fails_without_waiting_for_more` |
| M6 | `_decode.py` | leading zeros counted toward the 16 digit cap | `test_limits::test_leading_zeros_do_not_count_towards_the_size_cap` |
| M7 | `_decode.py` | `max_chunk_size` itself refused | `test_limits::test_chunk_size_is_capped` |
| M8 | `_decode.py` | body cap checked per chunk, not in total | `test_limits::test_body_size_is_capped_when_the_size_line_arrives` |
| M9 | `_decode.py` | extension bytes counted per line, not per message | `test_limits::test_extension_bytes_are_bounded_across_the_whole_message` |
| M10 | `_decode.py` | trailer budget without the line's CRLF | `test_limits::test_trailer_section_is_capped_including_crlfs` |
| M11 | `_decode.py` | `unused_data` returned before completion | `test_decode::test_unused_data_is_empty_before_completion` |
| M12 | `_decode.py` | a failed decoder not poisoned | `test_decode::test_a_failed_decoder_keeps_failing` |
| M13 | `_decode.py` | one byte too many taken from chunk data | the 300 s per-test timeout (the decoder loops forever) |
| M14 | `_decode.py` | a size of 1 read as the last chunk | doctest `Decoder.unused_data` |
| M15 | `_grammar.py` | `~` dropped from `tchar` | `test_oracle_llhttp::test_valid_messages_without_bws_decode_identically` |
| M16 | `_grammar.py` | `"` allowed as `qdtext` | `test_fuzz::test_mutated_messages_get_the_same_verdict[0]` |
| M17 | `_grammar.py` | tab dropped from BWS | `test_fuzz::test_mutated_messages_get_the_same_verdict[1]` |
| M18 | `_grammar.py` | obs-fold detected for a space only, not a tab | `test_upgrade` first; now `test_strict::test_obs_fold_in_trailers_is_rejected_with_a_clear_message[\tb]` |
| M19 | `_grammar.py` | `Host` allowed as a trailer | `test_encode::test_framing_and_routing_fields_are_refused_as_trailers[Host]` |
| M20 | `_grammar.py` | edge whitespace in a trailer value allowed | `test_encode::test_trailer_values_must_be_clean_field_values[ lead]` |
| M21 | `_grammar.py` | trailer values trimmed of spaces but not tabs | `test_decode::test_trailers_are_kept_in_order_with_trimmed_values` |
| M22 | `_grammar.py` | obs-text not allowed after a backslash | `test_upgrade` first; now `test_strict::test_quoted_pairs_escape_obs_text_and_whitespace` |
| M23 | `_encode.py` | chunk size written in decimal | doctest `Encoder.write` |
| M24 | `_encode.py` | empty piece written as a zero-size chunk | doctest `Encoder` |
| M25 | `_encode.py` | pieces of `chunk_size + 1` bytes | doctest `encode` |
| M26 | `_encode.py` | `finish` does not close the encoder | `test_contract_api::test_a_refused_trailer_leaves_the_encoder_open` |
| M27 | `_framing.py` | chunked applied twice allowed | `test_docs::test_each_example_prints_what_its_comments_show[4]` |
| M28 | `_framing.py` | request and response rules swapped | doctest `is_chunked` |
| M29 | `_framing.py` | Transfer-Encoding with Content-Length allowed | doctest `is_chunked` |
| M30 | `_framing.py` | coding names compared with case | `test_docs::test_each_guide_example_prints_what_its_comments_show[5]` |
| M31 | `_framing.py` | parameters on chunked allowed | `test_docs::test_each_guide_example_prints_what_its_comments_show[5]` |
| M32 | `_limits.py` | `-1` accepted as a bound | `test_limits::test_negative_limits_are_refused[max_line_size]` |
| M33 | `_errors.py` | a 64 character quote marked as cut | `test_messages::test_a_cut_quote_is_marked_and_a_short_one_is_not` |
| M34 | `_oneshot.py` | `decode` ignores bytes after the message | doctest `decode` |
| M35 | `_cli.py` | `decode` ignores bytes in a later block | `test_cli::test_decode_notices_bytes_after_the_end_in_a_later_block` |
| M36 | `_cli.py` | `--chunk-size 0` accepted | `test_cli::test_encode_reports_bad_options_before_any_output` |
| M37 | `_encode.py` | a two-character string taken as a pair | `test_contract_api::test_trailers_must_be_a_mapping_or_pairs` |
| M38 | `_errors.py` | only `str` refused as data | `test_contract_api::test_only_bytes_like_data_is_accepted[5]` |
| M39 | `_decode.py` | `limits` type not checked | `test_contract_api::test_decoder_refuses_anything_but_limits[5]` |
| M40 | `_cli.py` | trailer bytes printed without escaping | `test_cli::test_decode_escapes_trailer_bytes_for_an_ascii_terminal` |

## Packaging, e2e and Pythons (items 8, 10, 13, 14)

- Full suite on the laptop from a fresh clone at dafa892 (CPython 3.14.6) with the fetched
  sources, Node.js, h11, the 0.2.0 oracle, `CHUNKEDTE_E2E=1` and `CHUNKEDTE_E2E_PYPI=1`:
  408 passed, no skips. The e2e tests build the wheel and sdist, run
  `twine check --strict`, inspect both archives, install the wheel in a fresh venv and
  drive it from an empty folder with `-I`, run the `chunkedte` script and
  `python -m chunkedte` by subprocess (good input, bad input, exit codes), type-check a
  consumer with `mypy --strict` against the installed wheel, and install 0.2.0 from PyPI,
  then upgrade it in place to the built wheel and run the same program again.
- Interpreter matrix: pending.

## Gates (item 15)

Pending the final run.
