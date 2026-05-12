"""Unit tests for plugins/mill/scripts/_marker.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
for _p in (str(_SCRIPTS), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _marker  # noqa: E402
import _test_helpers  # noqa: E402


def test_slug_from_branch_happy_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_happy_path")


def test_slug_from_branch_empty_prefix() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="", phase="active"
        )
        cfg = {}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_empty_prefix")


def test_slug_from_branch_detached_head() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active"
        )
        sha = subprocess.run(
            ["git", "-C", str(worktree_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(worktree_path), "checkout", sha],
            capture_output=True,
            check=True,
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        try:
            _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        except _marker.MarkerError:
            pass
        else:
            raise AssertionError("expected MarkerError for detached HEAD")
    print("PASS: test_slug_from_branch_detached_head")


def test_slug_from_branch_unknown_slug() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # branch=hanf/bar, Home.md will only have 'foo'
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "bar", "Bar", branch_prefix="hanf/", phase="active"
        )
        (wiki_path / "Home.md").write_text(
            "## Foo Title\n[[foo]] [active]\n\n_body_\n", encoding="utf-8"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        try:
            _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        except _marker.MarkerError:
            pass
        else:
            raise AssertionError("expected MarkerError for unknown slug")
    print("PASS: test_slug_from_branch_unknown_slug")


def test_slug_from_branch_ready_to_merge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="ready-to-merge"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_ready_to_merge")


def test_slug_from_branch_pr_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="pr-pending"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_pr_pending")


def test_slug_from_branch_done() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="done"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_done")


def test_slug_from_branch_abandoned() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="abandoned"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_abandoned")


def test_slug_from_branch_none() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="none"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_none")


def test_slug_from_branch_prefix_mismatch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # branch is other/foo; cfg says prefix=hanf/
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="other/", phase="active"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        try:
            _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        except _marker.MarkerError:
            pass
        else:
            raise AssertionError("expected MarkerError for prefix mismatch")
    print("PASS: test_slug_from_branch_prefix_mismatch")


def test_task_data_happy_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        data = _marker.task_data(worktree_path, wiki_path, cfg)
        expected = {"slug": "foo", "branch": "hanf/foo", "task_title": "Foo Title"}
        if data != expected:
            raise AssertionError(f"expected {expected!r}, got {data!r}")
    print("PASS: test_task_data_happy_path")


def main() -> int:
    tests = [
        test_slug_from_branch_happy_path,
        test_slug_from_branch_empty_prefix,
        test_slug_from_branch_detached_head,
        test_slug_from_branch_unknown_slug,
        test_slug_from_branch_ready_to_merge,
        test_slug_from_branch_pr_pending,
        test_slug_from_branch_done,
        test_slug_from_branch_abandoned,
        test_slug_from_branch_none,
        test_slug_from_branch_prefix_mismatch,
        test_task_data_happy_path,
    ]

    failures: list[str] = []
    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as exc:
            print(f"FAIL [{test_fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(test_fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{test_fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(test_fn.__name__)

    print()
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)} tests: {failures}", file=sys.stderr)
        return 1
    print(f"All {len(tests)} _marker unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
