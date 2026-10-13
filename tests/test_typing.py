"""The public API is typed: mypy infers results and rejects bad calls."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

api = pytest.importorskip("mypy.api")

SRC = Path(__file__).resolve().parents[1] / "src"

SNIPPET = """
import chunkedte as ct
reveal_type(ct.decode(b"0\\r\\n\\r\\n"))
reveal_type(ct.Decoder().feed(b""))
reveal_type(ct.Decoder().trailers)
reveal_type(ct.Decoder().unused_data)
reveal_type(ct.encode(b"x", trailers={"a": "b"}))
reveal_type(ct.is_chunked("chunked", None, request=False))
reveal_type(ct.Limits().max_body_size)
ct.decode("text")
ct.encode(b"x", 5)
ct.Limits(max_line_size="1")
ct.Encoder().finish({"a": 1})
ct.is_chunked(b"chunked")
ct.decode(bytearray(b"x"), limits=ct.Limits())
ct.Encoder().write(memoryview(b"x"))
ct.encode(b"x", trailers=[("a", "b")])
"""


@pytest.fixture(scope="module")
def mypy_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    folder = tmp_path_factory.mktemp("typing")
    target = folder / "snippet.py"
    target.write_text(SNIPPET, encoding="utf-8")
    config = folder / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(folder / "cache")
    out, err, _ = api.run(
        ["--strict", "--config-file", str(config), "--cache-dir", cache, str(target)]
    )
    return str(out) + str(err)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (3, r"builtins\.bytes"),
        (4, r"builtins\.list\[builtins\.bytes\]"),
        (5, r"builtins\.list\[tuple\[builtins\.str, builtins\.str\]\]"),
        (6, r"builtins\.bytes"),
        (7, r"builtins\.bytes"),
        (8, r"builtins\.bool"),
        (9, r"builtins\.int \| None"),
    ],
)
def test_results_are_typed(mypy_output: str, line: int, expected: str) -> None:
    # Older mypy releases print the builtins prefix, newer ones do not.
    pattern = expected.replace(r"builtins\.", r"(builtins\.)?")
    assert re.search(rf'snippet\.py:{line}: note: Revealed type is "{pattern}"', mypy_output), (
        mypy_output
    )


@pytest.mark.parametrize(
    ("line", "code"),
    [(10, "arg-type"), (11, "call-arg"), (12, "arg-type"), (13, "arg-type"), (14, "arg-type")],
)
def test_wrong_calls_are_rejected(mypy_output: str, line: int, code: str) -> None:
    assert re.search(rf"snippet\.py:{line}: error: .*\[{code}\]", mypy_output), mypy_output


def test_bytes_like_and_pair_calls_are_accepted(mypy_output: str) -> None:
    assert not re.search(r"snippet\.py:1[5-7]: error", mypy_output), mypy_output
