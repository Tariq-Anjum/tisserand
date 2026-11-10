#!/usr/bin/env python3
"""Compatibility wrapper: regenerate every derived registry file.

All logic lives in `skillkit` (`python3 -m skillkit gen`); this file only
keeps the historical entry point working.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skillkit.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["gen"] + sys.argv[1:]))
