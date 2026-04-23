"""Unit tests for plugins/mill/scripts/_timestamp.py."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _timestamp import now_utc_compact, now_utc_iso  # noqa: E402


def main() -> int:
    try:
        compact = now_utc_compact()
        assert re.fullmatch(r"\d{8}-\d{6}", compact), f"bad compact form: {compact!r}"
        print(f"PASS: now_utc_compact() -> {compact}")

        iso = now_utc_iso()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", iso), f"bad iso: {iso!r}"
        print(f"PASS: now_utc_iso() -> {iso}")

        print("All _timestamp unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
