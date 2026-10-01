# test_export.py — runs under uv or bare Python (test uses subprocess → no resvg_py import needed).
# Skips gracefully if uv is not on PATH.
import hashlib
import pathlib
import shutil
import subprocess
import sys

import pytest

# Skip the whole module when uv is not available (can't rasterise without it).
if shutil.which("uv") is None:
    pytest.skip("uv not on PATH — cannot run export.py", allow_module_level=True)

_HERE = pathlib.Path(__file__).parent


def _run(args):
    """Invoke export.py via uv so PEP-723 deps (resvg-py) are resolved."""
    return subprocess.run(
        ["uv", "run", "export.py", *args],
        capture_output=True,
        text=True,
        cwd=_HERE,
    )


def test_png_is_produced_and_deterministic(tmp_path):
    src = "tests/inputs/atomic/diamond.excalidraw"
    out1 = tmp_path / "a.png"
    out2 = tmp_path / "b.png"
    r1 = _run([src, "-o", str(out1), "--scale", "2"])
    r2 = _run([src, "-o", str(out2), "--scale", "2"])
    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr
    assert out1.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"          # PNG magic bytes
    assert hashlib.sha256(out1.read_bytes()).hexdigest() == \
           hashlib.sha256(out2.read_bytes()).hexdigest()            # byte-deterministic
