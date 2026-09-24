"""Unit tests for _paths.short_name_is_derived."""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _paths import short_name_is_derived  # noqa: E402

CASES = [
    ({}, True),
    ({"repo": None}, True),
    ({"repo": {}}, True),
    ({"repo": {"short_name": ""}}, True),
    ({"repo": {"short_name": "MH"}}, False),
]


def main() -> int:
    failures = 0
    for cfg, expected in CASES:
        actual = short_name_is_derived(cfg)
        if actual == expected:
            print(f"PASS: short_name_is_derived({cfg!r}) == {expected}")
        else:
            failures += 1
            print(f"FAIL: short_name_is_derived({cfg!r}) == {actual}, expected {expected}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
