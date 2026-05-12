"""Regression guard: no U+2192 arrow character in any test-*.py file."""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELF = Path(__file__).name


def main() -> int:
    hits: list[str] = []
    for path in sorted(HERE.glob("test-*.py")):
        if path.name == SELF:
            continue
        text = path.read_text(encoding="utf-8")
        if "→" in text:
            hits.append(path.name)
    if hits:
        for name in hits:
            print(f"FAIL: U+2192 arrow found in {name}", file=sys.stderr)
        return 1
    print("PASS: no U+2192 arrow in any test-*.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
