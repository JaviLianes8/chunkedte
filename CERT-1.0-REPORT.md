# chunkedte 1.0.0 certification report

The 1.0.0 certification bar (19 items) applied to chunkedte. PyPI has 0.2.0, whose modules
are byte for byte those of the `main` branch at cb5707c (the wheel unpacked and compared
with the tree), so every change listed here is a change against the PyPI release.

Progress:
- [x] Branch `release/1.0.0` created from `main` (cb5707c, same code as PyPI 0.2.0)
- [x] Baseline gates on 0.2.0
- [x] API review and 1.0.0 changes (item 1)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [ ] Ground truth: specifications fetched live, reference parsers run (item 7)
- [ ] Contract, fuzz and author mutation round (items 6, 9, 18)
- [ ] Docs: README, CHANGELOG (items 11, 12)
- [ ] Packaging, e2e and upgrade from PyPI 0.2.0, every Python (items 8, 10, 13, 14)
- [ ] Gates (item 15)
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)
- [ ] PR and trace guard CLEAN (item 17); merge and publish left to the maintainer

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
  collection would have hung on stdin).
- No public docstring had a runnable example.
