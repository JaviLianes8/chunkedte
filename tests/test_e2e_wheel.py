"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with CHUNKEDTE_E2E=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("CHUNKEDTE_E2E") != "1", reason="set CHUNKEDTE_E2E=1 to build"
)

PROGRAM = r"""
import importlib.metadata, importlib.resources
import chunkedte as ct

assert "site-packages" in ct.__file__, ct.__file__
assert importlib.metadata.version("chunkedte") == ct.__version__
assert importlib.resources.files("chunkedte").joinpath("py.typed").is_file()
assert len(ct.__all__) == 8

message = ct.encode(b"hello world", chunk_size=4, trailers={"X-Sum": "1"})
assert message.startswith(b"4\r\nhell\r\n"), message
decoder = ct.Decoder(ct.Limits(max_body_size=11))
pieces = []
for i in range(0, len(message), 3):
    pieces.extend(decoder.feed(message[i : i + 3]))
assert b"".join(pieces) == b"hello world" and decoder.is_complete
assert decoder.trailers == [("X-Sum", "1")]
for bad in [b"+5\r\nhello\r\n0\r\n\r\n", b"5\r\nAAAAAXX2\r\n45\r\n0\r\n\r\n", b"5;\nx\r\n"]:
    try:
        ct.decode(bad)
    except ct.ChunkedError as error:
        assert isinstance(error, ValueError)
    else:
        raise AssertionError(bad)
try:
    ct.Decoder(ct.Limits(max_chunk_size=1)).feed(b"2\r\n")
except ct.LimitError:
    pass
else:
    raise AssertionError("limit not applied")
assert ct.is_chunked("gzip, chunked") and not ct.is_chunked("gzip", request=False)
print("e2e ok")
"""


def _run(*cmd: str | Path, cwd: Path | None = None, stdin: bytes | None = None) -> bytes:
    result = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, input=stdin, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    (wheel,) = dist.glob("chunkedte-*.whl")

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    _run(python, "-m", "pip", "install", "-q", wheel)

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    assert _run(python, "-I", "-c", PROGRAM, cwd=work).decode().splitlines() == ["e2e ok"]

    script = bindir / ("chunkedte.exe" if sys.platform == "win32" else "chunkedte")
    framed = _run(script, "encode", "--chunk-size", "2", cwd=work, stdin=b"abc")
    assert framed == b"2\r\nab\r\n1\r\nc\r\n0\r\n\r\n"
    decoded = _run(python, "-I", "-m", "chunkedte", "decode", cwd=work, stdin=framed)
    assert decoded == b"abc"
