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
- [x] Packaging, e2e and upgrade from PyPI 0.2.0, every Python (items 8, 10, 13, 14)
- [x] Gates (item 15)
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
| 5 | Typed, documented, bounded errors | PASS: `ChunkedError` (a `ValueError`), `LimitError`, `TypeError` for wrong types; messages quote at most 64 characters and never a trailer value or line (QA round 1) nor a `--trailer` argument without a colon (QA round 2) |
| 6 | Contract tests of every public name | PASS |
| 7 | Real ground truth | PASS: RFC 9112 and RFC 9110 fetched, llhttp test corpus fetched, llhttp (Node.js), h11 and http.client run live, PyPI 0.2.0 as an oracle |
| 8 | Real e2e from the wheel | PASS: installed wheel and CLI driven from an empty folder, consumer type-checked, upgrade in place from PyPI 0.2.0 |
| 9 | Seeded fuzz, no crash, hang or blowup | PASS |
| 10 | Supported Pythons | PASS: CPython 3.10.22, 3.11.17, 3.12.15, 3.13.16, 3.14.8, 3.14.8t; 3.8 and 3.9 below `requires-python` |
| 11 | README and `twine check` | PASS: `twine check --strict` in the e2e test, absolute links pinned by a test |
| 12 | Dated CHANGELOG section | PASS: 1.0.0, 2026-10-20 |
| 13 | pyproject 1.0.0, Production/Stable | PASS |
| 14 | sdist and wheel contents | PASS: pinned by `tests/test_e2e_wheel.py` |
| 15 | Gates each exit 0 | PASS: see Gates |
| 16 | Independent reviewer | pending |
| 17 | PR and trace guard | PR #3 from `release/1.0.0`, trace guard CLEAN; merge and publish left to the maintainer |
| 18 | Contracts bite (mutations) | PASS: author round 40 of 40 killed (table in `CERT-1.0-MUTATIONS.md`); the non-equivalent survivors of lens e's rounds 1 to 4 (7, 11, 6 and 5) now killed |
| 19 | Five independent QA lenses | rounds 1 to 4 findings fixed (see QA lenses); re-verification of round 4 by lens e pending |

## Baseline on 0.2.0 (before any change)

On this PC, CPython 3.13.2, at cb5707c: `ruff format --check .`, `ruff check .` and
`mypy --strict src tests` exit 0; `pytest` 282 passed, 1 skipped (the installed-wheel
test, which needs `CHUNKEDTE_E2E=1`); no doctests existed.

Defects found in 0.2.0 by reading and then reproducing: `Decoder(5)` was accepted and
failed later with `AttributeError`; `is_chunked(b"chunked")` raised a regular expression
`TypeError` and `is_chunked("chunked", 5)` read the `int` as a present Content-Length;
`encode(b"x", trailers=["ab"])` sent a trailer `a: b`; a 200,000 character trailer value
gave a 500,031 character error message (also a non-token name and a bad `--trailer`);
public classes reported private modules, so pickles depended on them; importing
`chunkedte.__main__` ran the tool; the package top exposed a stray `annotations`; no
docstring had a runnable example, the README linked LICENSE relatively and there was no
GUIDE.

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

The table (mutation, module, the test that killed it) is in `CERT-1.0-MUTATIONS.md`.

## Packaging, e2e and Pythons (items 8, 10, 13, 14)

- Full suite on the laptop from a fresh clone at dafa892 (CPython 3.14.6) with the fetched
  sources, Node.js, h11, the 0.2.0 oracle, `CHUNKEDTE_E2E=1` and `CHUNKEDTE_E2E_PYPI=1`:
  408 passed, no skips. The e2e tests build the wheel and sdist, run
  `twine check --strict`, inspect both archives, install the wheel in a fresh venv and
  drive it from an empty folder with `-I`, run the `chunkedte` script and
  `python -m chunkedte` by subprocess (good input, bad input, exit codes), type-check a
  consumer with `mypy --strict` against the installed wheel, and install 0.2.0 from PyPI,
  then upgrade it in place to the built wheel and run the same program again.
- Every CPython from `requires-python` up, at d12c212 on Elena's PC (the same minor
  versions this PC has, installed there by `uv` in a private folder): the wheel installed
  in a fresh venv and the sdist's own suite run with `src` removed (fetched sources,
  Node.js llhttp, h11 and the 0.2.0 oracle present), plus the 14 doctests from the
  installed package: CPython 3.10.22, 3.11.17, 3.12.15, 3.13.16, 3.14.8 and 3.14.8
  free-threaded all exit 0 (the three e2e tests need the source tree and run separately,
  above). 3.8 and 3.9 are below `requires-python`. This run found that
  `test_python_dash_m_runs_the_tool` assumed the source tree; it now runs from the folder
  holding the installed package.
- `scripts/release.ps1` refused any upload once the name existed on PyPI, so it could
  never have published 1.0.0; it now refuses a version already there and a dirty tree.

## Gates (item 15)

At 3c84ffb (the QA round 4 tests) on Elena's PC from a fresh clone (CPython 3.14), each
command on its own, with the fetched sources, Node.js llhttp, h11, the 0.2.0 oracle,
`CHUNKEDTE_E2E=1` and `CHUNKEDTE_E2E_PYPI=1`: `ruff format --check .`, `ruff check .`,
`mypy --strict src`, `mypy --strict src tests` and `pytest` (518 passed, no skips) all
exit 0. The same run gave 416 passed at c074fc3, 477 at 099ef17 (QA round 1 fixes),
490 at e644142 (QA round 2 fixes) and 508 at 4b6b48c (QA round 3 fixes). The interpreter
matrix (item 10) was last run at d12c212 and is not repeated here.

## QA lenses (item 19)

Round 1 ran against 5a8e4e2: lenses a, b, c and e reported 21 findings, all fixed in
099ef17, each behaviour fix with a contract test that failed on 5a8e4e2 first. The table
(finding, fix, test) is in `CERT-1.0-QA.md`.

Round 2 ran against 276f0e7: lens c reported N1 and lens e reported G1 to G7, all fixed
in e644142. The table is in `CERT-1.0-QA.md`.

Round 3 ran against 8061556: lens c reported N2 and lens e reported F1 to F4, all fixed in
4b6b48c. The table is in `CERT-1.0-QA.md`.

Round 4 ran against ee22527. Lens c confirmed N2 fixed and reported PASS. Lens e
confirmed its round 3 mutants (R01, R13, R20 to R23) and its round 2 mutants killed, ran
32 new mutants (Q01 to Q32) on the new `_check_name` and reported the 5 non-equivalent
survivors as E1 to E5 (Q04, Q06, Q21, Q24 and Q30 are equivalent). None is a behaviour
bug: each was a missing contract, so the code and the CHANGELOG are unchanged. All are
pinned in 3c84ffb by one parametrized test,
`test_cli_trailers::test_the_whole_trailer_name_is_checked_before_anything_else`, which
passes on ee22527. Each named mutant was re-applied alone to the tree at 3c84ffb and was
killed by that test.

| Finding | Contract added (exact message, `in a trailer field name`) | Mutant killed |
| --- | --- | --- |
| e-E1 a bad character after offset 63 | `"X" * 64 + " tail"`: `invalid byte 0x20 at offset 64`; `"X" * 70 + "\u00e9"`: `non-ASCII character U+00E9 at offset 70` | Q03 |
| e-E2 a blank name | `" "`: `invalid byte 0x20 at offset 0`; `"\t"`: `invalid byte 0x09 at offset 0` | Q07 |
| e-E3 a character outside the BMP | `"\U0001f600"`: `U+1F600 at offset 0`; `"X-\U00010000"`: `U+10000 at offset 2` | Q17 |
| e-E4 punctuation tchars before the bad byte | `X.Y Z` and `a!b c`: `0x20 at offset 3`; a name with eleven more punctuation tchars before a space: `0x20 at offset 23` | Q23 |
| e-E5 the name check runs before the forbidden list | Kelvin sign `\u212aeep-alive` (lower-cases to `keep-alive`): `non-ASCII character U+212A at offset 0`, not the forbidden message | Q32 |

Gates at 3c84ffb are under Gates. Re-verification of round 4 by lens e is pending.

### Disputed findings

None.

