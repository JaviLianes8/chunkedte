from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

import chunkedte
from chunkedte import encode
from chunkedte._cli import main


def _run(argv: list[str], data: bytes) -> tuple[int, bytes, str]:
    stdout, stderr = io.BytesIO(), io.StringIO()
    code = main(argv, stdin=io.BytesIO(data), stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_decode_prints_the_body_and_trailers_on_stderr() -> None:
    message = b"5\r\nhello\r\n0\r\nX-Sum: 1\r\n\r\n"
    assert _run(["decode"], message) == (0, b"hello", "X-Sum: 1\n")


def test_decode_escapes_trailer_bytes_for_an_ascii_terminal() -> None:
    raw = io.BytesIO()
    stderr = io.TextIOWrapper(raw, encoding="ascii", newline="")
    message = b"0\r\nA: caf\xe9\x9b\r\n\r\n"
    code = main(["decode"], stdin=io.BytesIO(message), stdout=io.BytesIO(), stderr=stderr)
    stderr.flush()
    assert code == 0
    assert raw.getvalue() == b"A: caf\\xe9\\x9b\n"


def test_decode_reads_large_input_in_blocks() -> None:
    body = bytes(range(256)) * 1000
    code, out, _ = _run(["decode"], encode(body, chunk_size=1000))
    assert (code, out) == (0, body)


@pytest.mark.parametrize(
    ("message", "error"),
    [
        (b"5\r\nhel", "incomplete"),
        (b"0\r\n\r\nmore", "after the end"),
        (b"+5\r\nhello\r\n0\r\n\r\n", "malformed chunk-size line"),
    ],
)
def test_decode_reports_bad_input_and_exits_1(message: bytes, error: str) -> None:
    code, _, err = _run(["decode"], message)
    assert code == 1
    assert err.startswith("chunkedte: ") and error in err


def test_decode_notices_bytes_after_the_end_in_a_later_block() -> None:
    message = b"0\r\n\r\n"

    class Slow(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            return super().read(min(size or 1, 5))

    stderr = io.StringIO()
    code = main(["decode"], stdin=Slow(message + b"X"), stdout=io.BytesIO(), stderr=stderr)
    assert code == 1 and "after the end" in stderr.getvalue()


def test_encode_frames_stdin() -> None:
    assert _run(["encode", "--chunk-size", "2"], b"abc") == (
        0,
        b"2\r\nab\r\n1\r\nc\r\n0\r\n\r\n",
        "",
    )


def test_encode_adds_trailers() -> None:
    code, out, _ = _run(["encode", "--trailer", "X-A: 1", "--trailer", "X-B:two"], b"x")
    assert (code, out) == (0, b"1\r\nx\r\n0\r\nX-A: 1\r\nX-B: two\r\n\r\n")


@pytest.mark.parametrize(
    ("argv", "error"),
    [
        (["encode", "--trailer", "novalue"], "NAME:VALUE"),
        (["encode", "--trailer", "Content-Length: 1"], "cannot be sent"),
    ],
)
def test_encode_reports_bad_options_before_any_output(argv: list[str], error: str) -> None:
    code, out, err = _run(argv, b"data")
    assert (code, out) == (1, b"")
    assert error in err


def test_files_are_read_by_path(tmp_path: Path) -> None:
    source = tmp_path / "body.bin"
    source.write_bytes(b"1\r\nz\r\n0\r\n\r\n")
    assert _run(["decode", str(source)], b"") == (0, b"z", "")


def test_a_missing_file_is_reported(tmp_path: Path) -> None:
    code, _, err = _run(["decode", str(tmp_path / "absent")], b"")
    assert code == 1 and err.startswith("chunkedte: ")


def test_python_dash_m_runs_the_tool() -> None:
    result = subprocess.run(
        [sys.executable, "-B", "-m", "chunkedte", "decode"],
        input=b"2\r\nok\r\n0\r\n\r\n",
        capture_output=True,
        check=False,
        # The folder holding the package: src in a checkout, site-packages when installed.
        cwd=Path(chunkedte.__file__).resolve().parents[1],
    )
    assert (result.returncode, result.stdout) == (0, b"ok")


@pytest.mark.parametrize("value", ["0", "-3", "x", "1.5"])
def test_a_chunk_size_that_is_not_a_positive_int_is_a_usage_error(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as caught:
        _run(["encode", "--chunk-size", value], b"data")
    assert caught.value.code == 2
    assert "--chunk-size" in capsys.readouterr().err


class _Counting(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.asked: list[int] = []
        self.reads: list[int] = []

    def read(self, size: int | None = -1) -> bytes:
        self.asked.append(-1 if size is None else size)
        block = super().read(size)
        self.reads.append(len(block))
        return block


@pytest.mark.parametrize("size", [str(10**30), str(2**63 - 1), "4000000000000"])
def test_a_huge_chunk_size_reads_in_bounded_blocks(size: str) -> None:
    source = _Counting(b"hello")
    out, err = io.BytesIO(), io.StringIO()
    assert main(["encode", "--chunk-size", size], source, out, err) == 0
    assert out.getvalue() == b"5\r\nhello\r\n0\r\n\r\n"
    assert all(0 < asked <= 65536 for asked in source.asked)


def test_encode_fills_each_chunk_from_short_reads() -> None:
    class Trickle(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            return super().read(min(size or 1, 2))

    out = io.BytesIO()
    assert main(["encode", "--chunk-size", "5"], Trickle(b"abcdefg"), out, io.StringIO()) == 0
    assert out.getvalue() == b"5\r\nabcde\r\n2\r\nfg\r\n0\r\n\r\n"


def test_encode_splits_a_trailer_argument_on_the_first_colon() -> None:
    code, out, _ = _run(["encode", "--trailer", "X-Time:12:30"], b"hi")
    assert (code, out) == (0, b"2\r\nhi\r\n0\r\nX-Time: 12:30\r\n\r\n")


def test_decode_stops_reading_once_the_message_is_complete() -> None:
    source = _Counting(b"1\r\na\r\n0\r\n\r\n" + b"z" * 5_000_000)
    code = main(["decode"], source, io.BytesIO(), io.StringIO())
    assert code == 1
    assert sum(source.reads) <= 65536 + 1


def test_decode_writes_a_tab_in_a_trailer_raw_and_escapes_bytes_above_0x7f() -> None:
    code, _, err = _run(["decode"], b"0\r\nX: a\tb\xe9\r\n\r\n")
    assert (code, err) == (0, "X: a\tb\\xe9\n")
