"""Unit tests for _gh_issues._render_body_with_comments."""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _gh_issues import _render_body_with_comments  # noqa: E402


def main() -> int:
    errors = 0

    # 1. Empty comments list — body returned unchanged (exact equality).
    _result = _render_body_with_comments("hello world", [])
    if _result != "hello world":
        print("FAIL: render/empty-comments — body mutated", file=sys.stderr)
        errors += 1
    else:
        print("PASS: render/empty-comments — body unchanged")

    # 2. Single comment — starts with original body, has exactly one --- line,
    #    one header line, comment body verbatim.
    _single = [{"author": {"login": "alice"}, "createdAt": "2026-01-01T00:00:00Z", "body": "great idea"}]
    _result = _render_body_with_comments("base body", _single)
    if not _result.startswith("base body"):
        print("FAIL: render/single — does not start with original body", file=sys.stderr)
        errors += 1
    elif "---" not in _result.splitlines():
        print("FAIL: render/single — no horizontal rule line", file=sys.stderr)
        errors += 1
    elif _result.count("**Comment by ") != 1:
        print("FAIL: render/single — expected exactly 1 comment header", file=sys.stderr)
        errors += 1
    elif "great idea" not in _result:
        print("FAIL: render/single — comment body not present", file=sys.stderr)
        errors += 1
    else:
        print("PASS: render/single — body, rule, header, comment body present")

    # 3. Three comments with non-monotonic createdAt — ascending order.
    _three = [
        {"author": {"login": "a"}, "createdAt": "2026-03-01", "body": "third"},
        {"author": {"login": "b"}, "createdAt": "2026-01-01", "body": "first"},
        {"author": {"login": "c"}, "createdAt": "2026-02-01", "body": "second"},
    ]
    _result = _render_body_with_comments("body", _three)
    _idx_first = _result.index("first")
    _idx_second = _result.index("second")
    _idx_third = _result.index("third")
    if not (_idx_first < _idx_second < _idx_third):
        print("FAIL: render/ordering — comments not in ascending createdAt order", file=sys.stderr)
        errors += 1
    else:
        print("PASS: render/ordering — comments in ascending createdAt order")

    # 4. Exactly 10 comments — all 10 rendered, no truncation marker.
    _ten = [
        {"author": {"login": f"u{i}"}, "createdAt": f"2026-01-{i:02d}", "body": f"body{i}"}
        for i in range(1, 11)
    ]
    _result = _render_body_with_comments("base", _ten)
    if not all(f"body{i}" in _result for i in range(1, 11)):
        print("FAIL: render/exact-10 — not all 10 comment bodies present", file=sys.stderr)
        errors += 1
    elif "truncated" in _result:
        print("FAIL: render/exact-10 — truncation marker present unexpectedly", file=sys.stderr)
        errors += 1
    else:
        print("PASS: render/exact-10 — all 10 rendered, no truncation marker")

    # 5. 11 comments — first 10 rendered, 11th absent, marker exact.
    _eleven = [
        {"author": {"login": f"u{i}"}, "createdAt": f"2026-01-{i:02d}", "body": f"body{i}"}
        for i in range(1, 12)
    ]
    _result = _render_body_with_comments("base", _eleven)
    if "body11" in _result:
        print("FAIL: render/11-comments — 11th comment body should not appear", file=sys.stderr)
        errors += 1
    elif "*[1 more comments truncated]*" not in _result:
        print("FAIL: render/11-comments — expected marker '*[1 more comments truncated]*'", file=sys.stderr)
        errors += 1
    else:
        print("PASS: render/11-comments — 11th truncated, marker correct")

    # 6. 15 comments — first 10 rendered, marker reads *[5 more comments truncated]*.
    _fifteen = [
        {"author": {"login": f"u{i}"}, "createdAt": f"2026-01-{i:02d}", "body": f"body{i}"}
        for i in range(1, 16)
    ]
    _result = _render_body_with_comments("base", _fifteen)
    if not all(f"body{i}" in _result for i in range(1, 11)):
        print("FAIL: render/15-comments — first 10 bodies not all present", file=sys.stderr)
        errors += 1
    elif "*[5 more comments truncated]*" not in _result:
        print("FAIL: render/15-comments — expected marker '*[5 more comments truncated]*'", file=sys.stderr)
        errors += 1
    else:
        print("PASS: render/15-comments — first 10 rendered, marker correct")

    # 7. Single comment with author: None — header reads [deleted].
    _deleted = [{"author": None, "createdAt": "2026-01-01T00:00:00Z", "body": "anon body"}]
    _result = _render_body_with_comments("base", _deleted)
    if "**Comment by [deleted] (2026-01-01T00:00:00Z):**" not in _result:
        print("FAIL: render/deleted-author — expected '[deleted]' in header", file=sys.stderr)
        errors += 1
    else:
        print("PASS: render/deleted-author — header uses [deleted]")

    # 8. Single comment with body: "" — header present, body section is empty string.
    _empty_body = [{"author": {"login": "alice"}, "createdAt": "2026-01-01T00:00:00Z", "body": ""}]
    _result = _render_body_with_comments("base", _empty_body)
    _header = "**Comment by alice (2026-01-01T00:00:00Z):**"
    if _header not in _result:
        print("FAIL: render/empty-body — header not present", file=sys.stderr)
        errors += 1
    else:
        _header_end = _result.index(_header) + len(_header) + 1  # +1 for \n
        _trailing = _result[_header_end:]
        if _trailing != "":
            print(f"FAIL: render/empty-body — expected empty string after header newline, got {_trailing!r}", file=sys.stderr)
            errors += 1
        else:
            print("PASS: render/empty-body — header present, body section is empty string")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All gh-issues unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
