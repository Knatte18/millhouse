"""Unit tests for _gh_issues._render_body_with_comments, fetch label_filter, and detect_repo."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _gh_issues  # noqa: E402
from _gh_issues import _render_body_with_comments  # noqa: E402


def test_detect_repo_with_explicit_git_root() -> int:
    errors = 0
    _git_root = Path("/fake/hub")

    def _stub_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="https://github.com/Knatte18/millhouse.git\n", stderr="")

    with patch("_gh_issues._subprocess_util.run", side_effect=_stub_run) as mock_run:
        result = _gh_issues.detect_repo(git_root=_git_root)

    try:
        mock_run.assert_called_with(["git", "-C", str(_git_root), "remote", "get-url", "origin"])
    except AssertionError:
        print("FAIL: detect_repo/explicit-git-root — subprocess not called with expected git -C args", file=sys.stderr)
        errors += 1
    if result != "Knatte18/millhouse":
        print(f"FAIL: detect_repo/explicit-git-root — expected 'Knatte18/millhouse', got {result!r}", file=sys.stderr)
        errors += 1
    if errors == 0:
        print("PASS: detect_repo/explicit-git-root — https URL parsed via git -C")
    return errors


def test_detect_repo_with_explicit_git_root_ssh_url() -> int:
    errors = 0
    _git_root = Path("/fake/hub")

    def _stub_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="git@github.com:Knatte18/millhouse.git\n", stderr="")

    with patch("_gh_issues._subprocess_util.run", side_effect=_stub_run) as mock_run:
        result = _gh_issues.detect_repo(git_root=_git_root)

    try:
        mock_run.assert_called_with(["git", "-C", str(_git_root), "remote", "get-url", "origin"])
    except AssertionError:
        print("FAIL: detect_repo/explicit-git-root-ssh — subprocess not called with expected git -C args", file=sys.stderr)
        errors += 1
    if result != "Knatte18/millhouse":
        print(f"FAIL: detect_repo/explicit-git-root-ssh — expected 'Knatte18/millhouse', got {result!r}", file=sys.stderr)
        errors += 1
    if errors == 0:
        print("PASS: detect_repo/explicit-git-root-ssh — ssh URL parsed via git -C")
    return errors


def test_detect_repo_default_falls_back_to_resolve_git_root() -> int:
    errors = 0
    _fake_root = Path("/fake/cwd-root")

    def _stub_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="https://github.com/Knatte18/millhouse.git\n", stderr="")

    with patch("_gh_issues._paths.resolve_git_root", return_value=_fake_root):
        with patch("_gh_issues._subprocess_util.run", side_effect=_stub_run) as mock_run:
            _gh_issues.detect_repo()

    try:
        mock_run.assert_called_with(["git", "-C", str(_fake_root), "remote", "get-url", "origin"])
    except AssertionError:
        print("FAIL: detect_repo/default-fallback — subprocess not called with git -C from resolve_git_root", file=sys.stderr)
        errors += 1
    if errors == 0:
        print("PASS: detect_repo/default-fallback — default resolves git root from _paths")
    return errors


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

    # --- label_filter tests ---

    # Canned issue list for mocking gh issue list output.
    _CANNED_ISSUES = [
        {"number": 1, "title": "Bug 1", "body": "b1", "labels": [{"name": "bug"}], "createdAt": "2026-01-01T00:00:00Z", "comments": []},
        {"number": 2, "title": "Feature 1", "body": "b2", "labels": [{"name": "enhancement"}], "createdAt": "2026-01-02T00:00:00Z", "comments": []},
        {"number": 3, "title": "Both labels", "body": "b3", "labels": [{"name": "bug"}, {"name": "enhancement"}], "createdAt": "2026-01-03T00:00:00Z", "comments": []},
        {"number": 4, "title": "No labels", "body": "b4", "labels": [], "createdAt": "2026-01-04T00:00:00Z", "comments": []},
        {"number": 5, "title": "Bug 2", "body": "b5", "labels": [{"name": "bug"}], "createdAt": "2026-01-05T00:00:00Z", "comments": []},
    ]

    def _mock_run(cmd, **kwargs):
        if len(cmd) > 1 and cmd[1] == "repo":
            return SimpleNamespace(returncode=0, stdout="owner/repo\n", stderr="")
        if "rev-parse" in cmd:
            return SimpleNamespace(returncode=0, stdout="/fake/repo-root\n", stderr="")
        if "remote" in cmd and "get-url" in cmd:
            return SimpleNamespace(returncode=0, stdout="https://github.com/owner/repo.git\n", stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps(_CANNED_ISSUES), stderr="")

    # 9. label_filter=None -> all 5 issues returned.
    with patch("_gh_issues._subprocess_util.run", side_effect=_mock_run):
        _result = _gh_issues.fetch(label_filter=None)
    if len(_result) != 5:
        print(f"FAIL: label_filter/none — expected 5 issues, got {len(_result)}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: label_filter/none — all 5 issues returned")

    # 10. label_filter=["bug"] -> issues 1, 3, 5.
    with patch("_gh_issues._subprocess_util.run", side_effect=_mock_run):
        _result = _gh_issues.fetch(label_filter=["bug"])
    _expected_numbers = {1, 3, 5}
    _got_numbers = {i["number"] for i in _result}
    if _got_numbers != _expected_numbers:
        print(f"FAIL: label_filter/bug — expected {_expected_numbers}, got {_got_numbers}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: label_filter/bug — issues 1, 3, 5 returned")

    # 11. label_filter=["bug", "enhancement"] -> any-of: issues 1, 2, 3, 5.
    with patch("_gh_issues._subprocess_util.run", side_effect=_mock_run):
        _result = _gh_issues.fetch(label_filter=["bug", "enhancement"])
    _expected_numbers = {1, 2, 3, 5}
    _got_numbers = {i["number"] for i in _result}
    if _got_numbers != _expected_numbers:
        print(f"FAIL: label_filter/any-of — expected {_expected_numbers}, got {_got_numbers}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: label_filter/any-of — issues 1, 2, 3, 5 returned")

    # 12. label_filter=["nonexistent"] -> empty list.
    with patch("_gh_issues._subprocess_util.run", side_effect=_mock_run):
        _result = _gh_issues.fetch(label_filter=["nonexistent"])
    if _result != []:
        print(f"FAIL: label_filter/nonexistent — expected [], got {_result}", file=sys.stderr)
        errors += 1
    else:
        print("PASS: label_filter/nonexistent — empty list returned")

    # 13. Issue with labels: [] is excluded when label_filter is set.
    with patch("_gh_issues._subprocess_util.run", side_effect=_mock_run):
        _result = _gh_issues.fetch(label_filter=["bug"])
    _has_no_label_issue = any(i["number"] == 4 for i in _result)
    if _has_no_label_issue:
        print("FAIL: label_filter/empty-labels — issue with no labels should be excluded", file=sys.stderr)
        errors += 1
    else:
        print("PASS: label_filter/empty-labels — issue with no labels excluded")

    errors += test_detect_repo_with_explicit_git_root()
    errors += test_detect_repo_with_explicit_git_root_ssh_url()
    errors += test_detect_repo_default_falls_back_to_resolve_git_root()

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All gh-issues unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
