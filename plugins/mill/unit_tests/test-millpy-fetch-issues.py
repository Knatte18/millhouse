"""Unit tests for plugins/mill/scripts/millpy-fetch-issues.py."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Load millpy-fetch-issues.py via importlib (hyphenated name).
_SCRIPT = HUB / "plugins" / "mill" / "scripts" / "millpy-fetch-issues.py"
_spec = importlib.util.spec_from_file_location("mill_fetch_issues", _SCRIPT)
mill_fetch_issues = importlib.util.module_from_spec(_spec)
sys.modules["mill_fetch_issues"] = mill_fetch_issues
_spec.loader.exec_module(mill_fetch_issues)

from _gh_issues import GhError, _render_body_with_comments  # noqa: E402


def _make_git_repo(tmp: Path) -> Path:
    """Initialise a minimal git repo under ``tmp`` and return its path."""
    subprocess.run(
        ["git", "init", str(tmp)], check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return tmp


_FIXTURE_ISSUES = [
    {"number": 1, "title": "First issue", "body": "body1", "labels": [], "createdAt": "2026-01-01"},
    {"number": 2, "title": "Second issue", "body": "body2", "labels": [], "createdAt": "2026-01-02"},
]


def main() -> int:
    errors = 0

    # ------------------------------------------------------------------
    # Test: happy path -- subprocess-level mock exercises fetch() + rendering.
    # ------------------------------------------------------------------
    _GH_FIXTURE = [
        {
            "number": 1,
            "title": "First issue",
            "body": "body1",
            "labels": [],
            "createdAt": "2026-01-01",
            "comments": [
                {"author": {"login": "alice"}, "createdAt": "2026-01-02T10:00:00Z", "body": "first comment"},
                {"author": {"login": "bob"}, "createdAt": "2026-01-03T10:00:00Z", "body": "second comment"},
            ],
        },
        {
            "number": 2,
            "title": "Second issue",
            "body": "body2",
            "labels": [],
            "createdAt": "2026-01-02",
            "comments": [],
        },
    ]

    def _fake_subprocess_run(argv, **kwargs):
        if len(argv) >= 2 and argv[1] == "repo":
            return subprocess.CompletedProcess(argv, 0, stdout="owner/repo\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(_GH_FIXTURE), stderr="")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        printed_lines: list[str] = []

        def mock_print(*args, **kwargs):
            if not kwargs.get("file"):
                printed_lines.append(str(args[0]) if args else "")

        with (
            patch("mill_fetch_issues.resolve_git_root", return_value=root),
            patch("mill_fetch_issues.resolve_hub_path", return_value=root),
            patch("_gh_issues._subprocess_util.run", side_effect=_fake_subprocess_run),
            patch("builtins.print", side_effect=mock_print),
        ):
            rc = mill_fetch_issues.main([])

        if rc != 0:
            print(f"FAIL: happy path returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        else:
            default_out = root / ".scratch" / "issues.json"
            if not default_out.exists():
                print("FAIL: issues.json not written to default path", file=sys.stderr)
                errors += 1
            else:
                written = json.loads(default_out.read_text(encoding="utf-8"))
                issue1 = next(i for i in written if i["number"] == 1)
                issue2 = next(i for i in written if i["number"] == 2)
                _fail = False
                if not issue1["body"].startswith("body1"):
                    print("FAIL: happy path — issue1 body does not start with 'body1'", file=sys.stderr)
                    errors += 1
                    _fail = True
                if "---" not in issue1["body"]:
                    print("FAIL: happy path — issue1 body missing horizontal rule", file=sys.stderr)
                    errors += 1
                    _fail = True
                if "**Comment by " not in issue1["body"] or "first comment" not in issue1["body"]:
                    print("FAIL: happy path — issue1 body missing rendered comment", file=sys.stderr)
                    errors += 1
                    _fail = True
                if issue2["body"] != "body2":
                    print(f"FAIL: happy path — issue2 body not byte-identical; got {issue2['body']!r}", file=sys.stderr)
                    errors += 1
                    _fail = True
                if not printed_lines or str(default_out.resolve()) not in printed_lines[-1]:
                    print(
                        f"FAIL: path not printed as last stdout line; got {printed_lines!r}",
                        file=sys.stderr,
                    )
                    errors += 1
                    _fail = True
                if not _fail:
                    print("PASS: happy path -- issues written, path printed as last stdout line")

    # ------------------------------------------------------------------
    # Test: --out override writes to the specified path.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        custom_out = root / "custom" / "out.json"

        with (
            patch("mill_fetch_issues.resolve_git_root", return_value=root),
            patch("mill_fetch_issues._gh_issues.fetch", return_value=_FIXTURE_ISSUES),
        ):
            rc = mill_fetch_issues.main(["--out", str(custom_out)])

        if rc != 0:
            print(f"FAIL: --out override returned {rc}, expected 0", file=sys.stderr)
            errors += 1
        elif not custom_out.exists():
            print("FAIL: --out path not created", file=sys.stderr)
            errors += 1
        else:
            print("PASS: --out override writes to specified path")

    # ------------------------------------------------------------------
    # Test: GhError from fetch -> returns exit code 1.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _make_git_repo(root)

        with (
            patch("mill_fetch_issues.resolve_git_root", return_value=root),
            patch("mill_fetch_issues._gh_issues.fetch", side_effect=GhError("auth failure")),
        ):
            rc = mill_fetch_issues.main([])

        if rc != 1:
            print(f"FAIL: GhError path returned {rc}, expected 1", file=sys.stderr)
            errors += 1
        else:
            print("PASS: GhError from fetch -> exit code 1")

    # ------------------------------------------------------------------
    # Test: _render_body_with_comments
    # ------------------------------------------------------------------

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
    print("All mill-fetch-issues unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
