"""Run the node:test unit tests in tests/js as part of the pytest suite."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS_DIR = ROOT / "tests" / "js"


def test_js_unit_tests():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    # List files explicitly: `node --test <dir>` is not supported on newer Node.
    files = sorted(str(p) for p in JS_DIR.glob("*.test.mjs"))
    assert files, "no JS test files found"
    proc = subprocess.run(
        [node, "--test", *files],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
