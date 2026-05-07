"""Unit tests for _autofix.slug_from_title."""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _autofix import slug_from_title  # noqa: E402


def main() -> int:
    errors = 0

    # 1. Standard title — all within 30 chars, no collision.
    _result = slug_from_title("Fix NPE in login flow", set(), 1)
    if _result != "fix-npe-in-login-flow":
        print(f"FAIL: slug/standard — expected 'fix-npe-in-login-flow', got {_result!r}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: slug/standard — 'fix-npe-in-login-flow'")

    # 2. Special chars — parens, colon, slash stripped and collapsed.
    _result = slug_from_title("Bug: crash (v2.0/alpha)", set(), 2)
    if _result != "bug-crash-v2-0-alpha":
        print(f"FAIL: slug/special-chars — expected 'bug-crash-v2-0-alpha', got {_result!r}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: slug/special-chars — 'bug-crash-v2-0-alpha'")

    # 3. Consecutive hyphens — double spaces and explicit hyphens collapsed.
    _result = slug_from_title("fix  -- double  space", set(), 3)
    if _result != "fix-double-space":
        print(f"FAIL: slug/collapse — expected 'fix-double-space', got {_result!r}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: slug/collapse — 'fix-double-space'")

    # 4. Truncation — slug > 30 chars truncated at last '-' boundary within 30.
    _result = slug_from_title("This is a really long title that should be truncated", set(), 4)
    if _result != "this-is-a-really-long-title":
        print(f"FAIL: slug/truncation — expected 'this-is-a-really-long-title', got {_result!r}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: slug/truncation — truncated at last '-' boundary within 30 chars")

    # 5. Collision — slug in existing_slugs appends '-<issue_number>'.
    _result = slug_from_title("Fix NPE in login flow", {"fix-npe-in-login-flow"}, 42)
    if _result != "fix-npe-in-login-flow-42":
        print(f"FAIL: slug/collision — expected 'fix-npe-in-login-flow-42', got {_result!r}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: slug/collision — appended '-42' on collision")

    # 6. Leading/trailing non-alpha chars — no leading or trailing hyphens.
    _result = slug_from_title("***Important Fix***", set(), 6)
    if _result.startswith("-") or _result.endswith("-"):
        print(f"FAIL: slug/strip — result has leading/trailing hyphen: {_result!r}", file=sys.stderr)
        errors += 1
    elif _result != "important-fix":
        print(f"FAIL: slug/strip — expected 'important-fix', got {_result!r}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: slug/strip — no leading or trailing hyphens")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All autofix unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
