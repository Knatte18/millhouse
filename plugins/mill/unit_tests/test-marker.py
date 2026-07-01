"""Unit tests for plugins/mill/scripts/_marker.py."""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import unittest.mock
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
for _p in (str(_SCRIPTS), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _marker  # noqa: E402
import _test_helpers  # noqa: E402


def test_slug_from_branch_happy_path() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_happy_path")


def test_slug_from_branch_empty_prefix() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="", phase="active", seed_task=True
        )
        cfg = {}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_empty_prefix")


def test_slug_from_branch_detached_head() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
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
    with _test_helpers.safe_temp_dir() as tmp:
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
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="ready-to-merge", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_ready_to_merge")


def test_slug_from_branch_pr_pending() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="pr-pending", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_pr_pending")


def test_slug_from_branch_done() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="done", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_done")


def test_slug_from_branch_abandoned() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="abandoned", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_abandoned")


def test_slug_from_branch_none() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="none", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_none")


def test_slug_from_branch_prefix_mismatch() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
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


def test_slug_from_branch_prefix_mismatch_bare_branch_known() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="", phase="active", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        stderr_capture = io.StringIO()
        with contextlib.redirect_stderr(stderr_capture):
            slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
        stderr_output = stderr_capture.getvalue()
        if "warning: branch 'foo' does not match prefix" not in stderr_output:
            raise AssertionError(f"expected warning in stderr, got: {stderr_output!r}")
    print("PASS: test_slug_from_branch_prefix_mismatch_bare_branch_known")


def test_slug_from_branch_prefix_mismatch_bare_branch_unknown() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="", phase="active"
        )
        (wiki_path / "Home.md").write_text(
            "## Baz Title\n[[baz]] [active]\n\n_body_\n", encoding="utf-8"
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        try:
            _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        except _marker.MarkerError:
            pass
        else:
            raise AssertionError("expected MarkerError for unknown slug")
    print("PASS: test_slug_from_branch_prefix_mismatch_bare_branch_unknown")


def test_slug_from_branch_user_prefix_no_config_prefix() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active", seed_task=True
        )
        cfg = {}
        slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
    print("PASS: test_slug_from_branch_user_prefix_no_config_prefix")


def test_slug_from_branch_user_prefix_slug_not_found() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "bar", "Bar", branch_prefix="hanf/", phase="active"
        )
        (wiki_path / "Home.md").write_text("[[foo]] [active]\n", encoding="utf-8")
        cfg = {}
        try:
            _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        except _marker.MarkerError:
            pass
        else:
            raise AssertionError("expected MarkerError when stripped slug not found in Home.md")
    print("PASS: test_slug_from_branch_user_prefix_slug_not_found")


def test_task_data_happy_path() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        data = _marker.task_data(worktree_path, wiki_path, cfg)
        expected = {"slug": "foo", "branch": "hanf/foo", "task_title": "Foo Title"}
        if data != expected:
            raise AssertionError(f"expected {expected!r}, got {data!r}")
    print("PASS: test_task_data_happy_path")


def test_slug_from_branch_retries_on_cold_daemon() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        # Capture the real task list before patching, so the retry's second
        # call can still return genuine data.
        real_tasks = _marker.wiki.list_tasks_brief(wiki_path)
        with unittest.mock.patch.object(
            _marker.wiki,
            "list_tasks_brief",
            side_effect=[_marker.wiki.WikiStartupError("cold"), real_tasks],
        ), unittest.mock.patch.object(_marker.wiki, "health_check") as mock_health_check:
            slug = _marker.slug_from_branch(worktree_path, wiki_path, cfg)
        if slug != "foo":
            raise AssertionError(f"expected 'foo', got {slug!r}")
        if mock_health_check.call_count != 1:
            raise AssertionError(f"expected health_check called once, got {mock_health_check.call_count}")
    print("PASS: test_slug_from_branch_retries_on_cold_daemon")


def test_slug_from_branch_exhausted_retry_propagates_wiki_startup_error() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        # Both the initial call and the post-wake retry raise, so the
        # daemon never recovers within the single retry budget.
        with unittest.mock.patch.object(
            _marker.wiki, "list_tasks_brief", side_effect=_marker.wiki.WikiStartupError("still cold")
        ), unittest.mock.patch.object(_marker.wiki, "health_check"):
            try:
                _marker.slug_from_branch(worktree_path, wiki_path, cfg)
            except _marker.wiki.WikiStartupError:
                pass
            else:
                raise AssertionError("expected wiki.WikiStartupError to propagate unwrapped")
    print("PASS: test_slug_from_branch_exhausted_retry_propagates_wiki_startup_error")


def test_task_data_retries_on_cold_daemon() -> None:
    with _test_helpers.safe_temp_dir() as tmp:
        worktree_path, wiki_path = _test_helpers._make_task_worktree(
            tmp, "foo", "Foo Title", branch_prefix="hanf/", phase="active", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        real_tasks = _marker.wiki.list_tasks_brief(wiki_path)
        # task_data() makes 3 total list_tasks_brief calls after the retry
        # fix: 2 inside its own slug_from_branch() call (1 failure + 1
        # retry-success), plus a 3rd from task_data()'s own separate
        # _list_tasks_brief_with_retry() call.
        with unittest.mock.patch.object(
            _marker.wiki,
            "list_tasks_brief",
            side_effect=[_marker.wiki.WikiStartupError("cold"), real_tasks, real_tasks],
        ), unittest.mock.patch.object(_marker.wiki, "health_check") as mock_health_check:
            data = _marker.task_data(worktree_path, wiki_path, cfg)
        expected = {"slug": "foo", "branch": "hanf/foo", "task_title": "Foo Title"}
        if data != expected:
            raise AssertionError(f"expected {expected!r}, got {data!r}")
        if mock_health_check.call_count != 1:
            raise AssertionError(f"expected health_check called once, got {mock_health_check.call_count}")
    print("PASS: test_task_data_retries_on_cold_daemon")


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
        test_slug_from_branch_prefix_mismatch_bare_branch_known,
        test_slug_from_branch_prefix_mismatch_bare_branch_unknown,
        test_slug_from_branch_user_prefix_no_config_prefix,
        test_slug_from_branch_user_prefix_slug_not_found,
        test_task_data_happy_path,
        test_slug_from_branch_retries_on_cold_daemon,
        test_slug_from_branch_exhausted_retry_propagates_wiki_startup_error,
        test_task_data_retries_on_cold_daemon,
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
