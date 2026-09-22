#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "brotli>=1.2.0",
#     "fonttools>=4.63.0",
#     "numpy>=2.5.1",
#     "pillow>=12.3.0",
#     "pytest>=9.1.1",
#     "resvg-py==0.3.3",
# ]
# ///
"""Canonical test runner — runs the pytest suite with the render-test deps present.

The exporter CORE is pure-stdlib, but the PNG-render tests (test_emoji_rendering,
test_symbol_fallback) import resvg_py / Pillow / numpy and otherwise pytest.skip.
Running the suite through this uv script guarantees those deps are available, so the
render tests always RUN instead of silently skipping — and rotting: a render test once
sat broken (wrong resvg_py API) behind a skip and looked green. Font/build tests also
get fontTools + brotli here.

Run:  uv run run_tests.py             # full suite (all render tests execute)
      uv run run_tests.py -q -k foo   # extra args pass straight through to pytest

Bare `python -m pytest` still works but skips the resvg-gated render tests (graceful
degradation for environments without the rasterizer).
"""
import sys

import pytest

if __name__ == "__main__":
    raise SystemExit(pytest.main(sys.argv[1:]))
