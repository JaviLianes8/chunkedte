"""The README examples run and print what they say; metadata agrees with the code."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

import chunkedte
from chunkedte._cli import main

ROOT = Path(__file__).resolve().parents[1]


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _blocks(name: str = "README.md") -> list[str]:
    text = (ROOT / name).read_text(encoding="utf-8")
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


def _comments(block: str) -> list[str]:
    return [line[2:] for line in block.splitlines() if line.startswith("# ")]


def test_the_readme_has_runnable_examples() -> None:
    assert len(_blocks()) == 5


@pytest.mark.parametrize("index", range(5))
def test_each_example_prints_what_its_comments_show(
    index: int, capsys: pytest.CaptureFixture[str]
) -> None:
    block = _blocks()[index]
    exec(compile(block, "README.md", "exec"), {"__name__": "readme"})
    printed = capsys.readouterr().out.splitlines()
    assert printed == _comments(block)
    assert printed


def test_the_guide_has_runnable_examples() -> None:
    assert len(_blocks("GUIDE.md")) == 6


@pytest.mark.parametrize("index", range(6))
def test_each_guide_example_prints_what_its_comments_show(
    index: int, capsys: pytest.CaptureFixture[str]
) -> None:
    block = _blocks("GUIDE.md")[index]
    exec(compile(block, "GUIDE.md", "exec"), {"__name__": "guide"})
    printed = capsys.readouterr().out.splitlines()
    assert printed == _comments(block)
    assert printed


def test_every_public_name_appears_in_the_guide() -> None:
    guide = (ROOT / "GUIDE.md").read_text(encoding="utf-8")
    for name in chunkedte.__all__:
        assert f"`{name}" in guide, name


def test_readme_links_are_absolute() -> None:
    for target in re.findall(r"\]\(([^)]+)\)", _readme()):
        assert target.startswith("https://"), target


def _od_c(lines: list[str]) -> bytes:
    # od -c: a 7-digit offset, then one byte per 4 columns, right-aligned.
    escapes = {"\\r": "\r", "\\n": "\n", "": " "}
    cells = [line[7 + at : 11 + at].strip() for line in lines for at in range(0, len(line) - 7, 4)]
    return "".join(escapes.get(cell, cell) for cell in cells).encode()


def test_the_command_line_example_prints_what_the_readme_shows() -> None:
    session = re.search(r"\n\$ printf '(.*?)' > message.bin\n(.*?)```", _readme(), re.DOTALL)
    assert session is not None
    message = session[1].replace("\\r", "\r").replace("\\n", "\n").encode()
    shown = session[2].splitlines()
    assert shown[0].endswith("decode message.bin 2>/dev/null; echo")
    assert shown[2].endswith("decode message.bin 2>&1 >/dev/null")
    assert shown[4].startswith("$ printf 'abc' | chunkedte encode --chunk-size 2 --trailer")
    out, err = io.BytesIO(), io.StringIO()
    assert main(["decode"], io.BytesIO(message), out, err) == 0
    assert (out.getvalue().decode(), err.getvalue()) == (shown[1], shown[3] + "\n")
    out = io.BytesIO()
    argv = ["encode", "--chunk-size", "2", "--trailer", "X-Sum: 1"]
    assert main(argv, io.BytesIO(b"abc"), out, io.StringIO()) == 0
    assert out.getvalue() == _od_c(shown[5:7])
    assert shown[7] == f"{len(out.getvalue()):07o}"


def test_every_public_name_appears_in_the_readme() -> None:
    for name in chunkedte.__all__:
        assert f"`{name}" in _readme(), name


def test_the_documented_default_limits_are_the_real_ones() -> None:
    limits = chunkedte.Limits()
    assert limits.max_line_size == 4 * 1024
    assert limits.max_extensions_size == limits.max_trailer_size == 16 * 1024
    assert "4 KiB" in _readme() and "16 KiB" in _readme()


def test_version_matches_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == chunkedte.__version__


def test_changelog_has_an_entry_for_this_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{chunkedte.__version__}]" in text


def test_no_em_dash_in_any_shipped_text() -> None:
    files = [*ROOT.glob("*.md"), *ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py")]
    for path in files:
        assert chr(0x2014) not in path.read_text(encoding="utf-8"), path


def test_every_source_file_stays_under_two_hundred_lines() -> None:
    for path in [*ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py"), *ROOT.glob("scripts/*")]:
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 200, path
