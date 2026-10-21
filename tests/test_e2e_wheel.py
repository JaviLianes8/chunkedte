"""Build the wheel and sdist, install the wheel in a throwaway venv and drive the install.

Slow and needs the build backend, so it runs only with CHUNKEDTE_E2E=1. With
CHUNKEDTE_E2E_PYPI=1 it also installs 0.2.0 from PyPI and upgrades it in place.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("CHUNKEDTE_E2E") != "1", reason="set CHUNKEDTE_E2E=1 to build"
)

PROGRAM = r"""
import importlib.metadata, importlib.resources, pickle
import chunkedte as ct

assert "site-packages" in ct.__file__, ct.__file__
assert ct.__version__ == "1.0.0" == importlib.metadata.version("chunkedte")
assert importlib.resources.files("chunkedte").joinpath("py.typed").is_file()
public = sorted(name for name in dir(ct) if not name.startswith("_"))
assert sorted(ct.__all__) == public, public

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
except ct.LimitError as error:
    assert pickle.loads(pickle.dumps(error)).args == error.args
else:
    raise AssertionError("limit not applied")
try:
    ct.Decoder(5)
except TypeError:
    pass
else:
    raise AssertionError("Decoder took a non-Limits")
assert pickle.loads(pickle.dumps(ct.Limits(max_body_size=3))) == ct.Limits(max_body_size=3)
assert ct.is_chunked("gzip, chunked") and not ct.is_chunked("gzip", request=False)
print("e2e ok")
"""

CONSUMER = """
import chunkedte

body: bytes = chunkedte.decode(b"0\\r\\n\\r\\n")
pieces: list[bytes] = chunkedte.Decoder().feed(b"")
trailers: list[tuple[str, str]] = chunkedte.Decoder().trailers
"""


def _run(*cmd: str | Path, cwd: Path | None = None, stdin: bytes | None = None) -> bytes:
    result = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, input=stdin, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


def _venv(path: Path) -> tuple[Path, Path]:
    venv.create(path, with_pip=True)
    bindir = path / ("Scripts" if sys.platform == "win32" else "bin")
    return bindir / "python", bindir


@pytest.fixture(scope="module")
def dist(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("dist")
    _run(sys.executable, "-m", "build", "--outdir", out, ROOT)
    _run(sys.executable, "-m", "twine", "check", "--strict", *sorted(out.iterdir()))
    return out


def test_wheel_and_sdist_hold_what_they_should(dist: Path) -> None:
    (wheel,) = dist.glob("chunkedte-1.0.0-py3-none-any.whl")
    names = set(zipfile.ZipFile(wheel).namelist())
    modules = {n for n in names if n.startswith("chunkedte/")}
    private = ["cli", "decode", "encode", "errors", "framing", "grammar", "limits", "lines"]
    expected = ["__init__.py", "__main__.py", "py.typed", "_oneshot.py"]
    expected += [f"_{name}.py" for name in private]
    assert modules == {f"chunkedte/{name}" for name in expected}
    assert "chunkedte-1.0.0.dist-info/licenses/LICENSE" in names
    (sdist,) = dist.glob("chunkedte-1.0.0.tar.gz")
    with tarfile.open(sdist) as archive:
        members = {m.split("/", 1)[1] for m in archive.getnames() if "/" in m}
    assert {"LICENSE", "README.md", "GUIDE.md", "CHANGELOG.md", "pyproject.toml"} <= members
    assert "tests/upstream/MANIFEST.json" in members
    assert not [m for m in members if m.startswith("tests/upstream/") and "MANIFEST" not in m]
    assert not [m for m in members if "CERT-1.0" in m or "IMPROVEMENTS" in m]
    assert not [m for m in members if "__pycache__" in m or m.endswith(".pyc")]


def test_installed_wheel_end_to_end(dist: Path, tmp_path: Path) -> None:
    (wheel,) = dist.glob("chunkedte-*.whl")
    python, bindir = _venv(tmp_path / "venv")
    _run(python, "-m", "pip", "install", "-q", wheel)

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    assert _run(python, "-I", "-c", PROGRAM, cwd=work).decode().splitlines() == ["e2e ok"]

    script = bindir / ("chunkedte.exe" if sys.platform == "win32" else "chunkedte")
    framed = _run(
        script, "encode", "--chunk-size", "2", "--trailer", "X: 1", cwd=work, stdin=b"abc"
    )
    assert framed == b"2\r\nab\r\n1\r\nc\r\n0\r\nX: 1\r\n\r\n"
    decoded = _run(python, "-I", "-m", "chunkedte", "decode", cwd=work, stdin=framed)
    assert decoded == b"abc"
    bad = subprocess.run([script, "decode"], cwd=work, input=b"+1\r\n", capture_output=True)
    assert bad.returncode == 1 and b"malformed chunk-size line" in bad.stderr

    consumer = work / "consumer.py"
    consumer.write_text(CONSUMER, encoding="utf-8")
    _run(python, "-m", "pip", "install", "-q", "mypy")
    _run(python, "-m", "mypy", "--strict", "--no-incremental", consumer, cwd=work)


@pytest.mark.skipif(os.environ.get("CHUNKEDTE_E2E_PYPI") != "1", reason="needs PyPI access")
def test_upgrade_in_place_from_the_pypi_release(dist: Path, tmp_path: Path) -> None:
    (wheel,) = dist.glob("chunkedte-*.whl")
    python, _ = _venv(tmp_path / "venv")
    _run(python, "-m", "pip", "install", "-q", "chunkedte==0.2.0")
    probe = "import chunkedte as c; print(c.__version__, c.decode(b'1\\r\\na\\r\\n0\\r\\n\\r\\n'))"
    assert _run(python, "-I", "-c", probe).split() == [b"0.2.0", b"b'a'"]
    _run(python, "-m", "pip", "install", "-q", "--upgrade", wheel)
    assert _run(python, "-I", "-c", probe).split() == [b"1.0.0", b"b'a'"]
    work = tmp_path / "work"
    work.mkdir()
    assert _run(python, "-I", "-c", PROGRAM, cwd=work).decode().splitlines() == ["e2e ok"]
