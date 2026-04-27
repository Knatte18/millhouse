"""Unit tests for plugins/mill/scripts/_inplace.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _inplace  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_active_data(slug: str, branch: str) -> dict:
    return {"slug": slug, "task_title": "Test task", "branch": branch, "spawned_at": "2026-01-01T00:00:00Z"}


def _fake_run_branch(branch: str):
    """Return a _subprocess_util.run-compatible stub that reports ``branch``."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = branch + "\n"
    return result


# ---------------------------------------------------------------------------
# is_inplace tests
# ---------------------------------------------------------------------------


def _test_is_inplace_true_when_branch_matches_and_no_worktree_dir():
    """Returns True when branch matches cwd and worktrees dir absent."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        git_root = tmp / "hub"
        git_root.mkdir()
        # No worktrees dir created — is_inplace should return True.
        cfg = {}
        active_data = _make_active_data("my-task", "my-task")

        with patch("_inplace._subprocess_util.run", return_value=_fake_run_branch("my-task")):
            with patch("_inplace.resolve_worktrees_dir", return_value=tmp / "worktrees"):
                result = _inplace.is_inplace(active_data, git_root, cfg)

        if not result:
            raise AssertionError("Expected is_inplace to return True")
        print("PASS is_inplace — branch matches, no worktrees dir -> True")


def _test_is_inplace_false_on_branch_mismatch():
    """Returns False when HEAD branch does not match recorded branch."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        git_root = tmp / "hub"
        git_root.mkdir()
        cfg = {}
        active_data = _make_active_data("my-task", "my-task")

        with patch("_inplace._subprocess_util.run", return_value=_fake_run_branch("other-branch")):
            with patch("_inplace.resolve_worktrees_dir", return_value=tmp / "worktrees"):
                result = _inplace.is_inplace(active_data, git_root, cfg)

        if result:
            raise AssertionError("Expected is_inplace to return False on branch mismatch")
        print("PASS is_inplace — branch mismatch -> False")


def _test_is_inplace_false_when_worktree_dir_exists_default():
    """Returns False when worktree dir exists at default location."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        git_root = tmp / "hub"
        git_root.mkdir()
        worktree_dir = tmp / "worktrees" / "my-task"
        worktree_dir.mkdir(parents=True)
        cfg = {}
        active_data = _make_active_data("my-task", "my-task")

        with patch("_inplace._subprocess_util.run", return_value=_fake_run_branch("my-task")):
            with patch("_inplace.resolve_worktrees_dir", return_value=tmp / "worktrees"):
                result = _inplace.is_inplace(active_data, git_root, cfg)

        if result:
            raise AssertionError("Expected is_inplace to return False when worktree dir exists")
        print("PASS is_inplace — worktree dir exists (default location) -> False")


def _test_is_inplace_false_when_worktree_dir_exists_override():
    """Returns False when worktree dir exists at overridden location."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        git_root = tmp / "hub"
        git_root.mkdir()
        custom_worktrees = tmp / "custom-worktrees"
        worktree_dir = custom_worktrees / "my-task"
        worktree_dir.mkdir(parents=True)
        cfg = {"spawn": {"worktrees_dir": str(custom_worktrees)}}
        active_data = _make_active_data("my-task", "my-task")

        with patch("_inplace._subprocess_util.run", return_value=_fake_run_branch("my-task")):
            with patch("_inplace.resolve_worktrees_dir", return_value=custom_worktrees):
                result = _inplace.is_inplace(active_data, git_root, cfg)

        if result:
            raise AssertionError(
                "Expected is_inplace to return False when worktree dir exists at override"
            )
        print("PASS is_inplace — worktree dir exists (overridden location) -> False")


# ---------------------------------------------------------------------------
# prompt_stale_worktree tests
# ---------------------------------------------------------------------------


def _test_prompt_stale_worktree_returns_inplace_on_choice_1():
    """Returns 'inplace' when the user enters '1'."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree_path = Path(tmp) / "worktrees" / "my-task"
        with patch("builtins.input", return_value="1"):
            result = _inplace.prompt_stale_worktree("my-task", worktree_path)
        if result != "inplace":
            raise AssertionError(f"Expected 'inplace', got {result!r}")
        print("PASS prompt_stale_worktree — input '1' -> 'inplace'")


def _test_prompt_stale_worktree_returns_worktree_on_choice_2():
    """Returns 'worktree' when the user enters '2'."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree_path = Path(tmp) / "worktrees" / "my-task"
        with patch("builtins.input", return_value="2"):
            result = _inplace.prompt_stale_worktree("my-task", worktree_path)
        if result != "worktree":
            raise AssertionError(f"Expected 'worktree', got {result!r}")
        print("PASS prompt_stale_worktree — input '2' -> 'worktree'")


def _test_prompt_stale_worktree_returns_abort_on_choice_3():
    """Returns 'abort' when the user enters '3'."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree_path = Path(tmp) / "worktrees" / "my-task"
        with patch("builtins.input", return_value="3"):
            result = _inplace.prompt_stale_worktree("my-task", worktree_path)
        if result != "abort":
            raise AssertionError(f"Expected 'abort', got {result!r}")
        print("PASS prompt_stale_worktree — input '3' -> 'abort'")


def _test_prompt_stale_worktree_returns_abort_on_invalid_choice():
    """Returns 'abort' on unrecognised input."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree_path = Path(tmp) / "worktrees" / "my-task"
        with patch("builtins.input", return_value="99"):
            result = _inplace.prompt_stale_worktree("my-task", worktree_path)
        if result != "abort":
            raise AssertionError(f"Expected 'abort' on invalid input, got {result!r}")
        print("PASS prompt_stale_worktree — invalid input -> 'abort'")


def _test_prompt_stale_worktree_returns_abort_on_eof():
    """Returns 'abort' on EOF (non-interactive environment)."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree_path = Path(tmp) / "worktrees" / "my-task"
        with patch("builtins.input", side_effect=EOFError):
            result = _inplace.prompt_stale_worktree("my-task", worktree_path)
        if result != "abort":
            raise AssertionError(f"Expected 'abort' on EOF, got {result!r}")
        print("PASS prompt_stale_worktree — EOF -> 'abort'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        _test_is_inplace_true_when_branch_matches_and_no_worktree_dir,
        _test_is_inplace_false_on_branch_mismatch,
        _test_is_inplace_false_when_worktree_dir_exists_default,
        _test_is_inplace_false_when_worktree_dir_exists_override,
        _test_prompt_stale_worktree_returns_inplace_on_choice_1,
        _test_prompt_stale_worktree_returns_worktree_on_choice_2,
        _test_prompt_stale_worktree_returns_abort_on_choice_3,
        _test_prompt_stale_worktree_returns_abort_on_invalid_choice,
        _test_prompt_stale_worktree_returns_abort_on_eof,
    ]
    failures: list[str] = []
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            print(f"FAIL [{test.__name__}]: {exc}", file=sys.stderr)
            failures.append(test.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{test.__name__}]: {exc}", file=sys.stderr)
            failures.append(test.__name__)

    print()
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)} tests: {failures}", file=sys.stderr)
        return 1
    print(f"All {len(tests)} _inplace unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
