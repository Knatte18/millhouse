"""Unit tests for plugins/mill/scripts/_inplace.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _inplace  # noqa: E402


# ---------------------------------------------------------------------------
# is_inplace tests
# ---------------------------------------------------------------------------


def _test_is_inplace_true_when_no_worktree_dir():
    """Returns True when no worktree directory exists for the slug."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        git_root = tmp / "hub"
        git_root.mkdir()
        cfg = {}
        # No worktrees dir created — is_inplace should return True.
        with patch("_inplace.resolve_worktrees_dir", return_value=tmp / "worktrees"):
            result = _inplace.is_inplace("my-task", git_root, cfg)

        if not result:
            raise AssertionError("Expected is_inplace to return True")
        print("PASS is_inplace — no worktrees dir -> True")


def _test_is_inplace_false_when_worktree_dir_exists_default():
    """Returns False when worktree dir exists at default location."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        git_root = tmp / "hub"
        git_root.mkdir()
        worktree_dir = tmp / "worktrees" / "my-task"
        worktree_dir.mkdir(parents=True)
        cfg = {}

        with patch("_inplace.resolve_worktrees_dir", return_value=tmp / "worktrees"):
            result = _inplace.is_inplace("my-task", git_root, cfg)

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

        with patch("_inplace.resolve_worktrees_dir", return_value=custom_worktrees):
            result = _inplace.is_inplace("my-task", git_root, cfg)

        if result:
            raise AssertionError(
                "Expected is_inplace to return False when worktree dir exists at override"
            )
        print("PASS is_inplace — worktree dir exists (overridden location) -> False")


# ---------------------------------------------------------------------------
# prompt_stale_worktree tests
# ---------------------------------------------------------------------------


def _test_prompt_stale_worktree_returns_abort_on_choice_1():
    """Returns 'abort' when the user enters '1'."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree_path = Path(tmp) / "worktrees" / "my-task"
        with patch("builtins.input", return_value="1"):
            result = _inplace.prompt_stale_worktree("my-task", worktree_path)
        if result != "abort":
            raise AssertionError(f"Expected 'abort', got {result!r}")
        print("PASS prompt_stale_worktree — input '1' -> 'abort'")


def _test_prompt_stale_worktree_returns_inplace_on_choice_2():
    """Returns 'inplace' when the user enters '2'."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree_path = Path(tmp) / "worktrees" / "my-task"
        with patch("builtins.input", return_value="2"):
            result = _inplace.prompt_stale_worktree("my-task", worktree_path)
        if result != "inplace":
            raise AssertionError(f"Expected 'inplace', got {result!r}")
        print("PASS prompt_stale_worktree — input '2' -> 'inplace'")


def _test_prompt_stale_worktree_returns_worktree_on_choice_3():
    """Returns 'worktree' when the user enters '3'."""
    with tempfile.TemporaryDirectory() as tmp:
        worktree_path = Path(tmp) / "worktrees" / "my-task"
        with patch("builtins.input", return_value="3"):
            result = _inplace.prompt_stale_worktree("my-task", worktree_path)
        if result != "worktree":
            raise AssertionError(f"Expected 'worktree', got {result!r}")
        print("PASS prompt_stale_worktree — input '3' -> 'worktree'")


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
        _test_is_inplace_importable_and_callable,
        _test_prompt_stale_worktree_importable_and_callable,
        _test_is_inplace_returns_bool,
        _test_prompt_stale_worktree_returns_str,
        _test_is_inplace_true_when_no_worktree_dir,
        _test_is_inplace_false_when_worktree_dir_exists_default,
        _test_is_inplace_false_when_worktree_dir_exists_override,
        _test_prompt_stale_worktree_returns_abort_on_choice_1,
        _test_prompt_stale_worktree_returns_inplace_on_choice_2,
        _test_prompt_stale_worktree_returns_worktree_on_choice_3,
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


# ---------------------------------------------------------------------------
# Public-surface signature smoke tests (was test-mill-merge-inplace.py).
# These catch API drift before behavioural tests run.
# ---------------------------------------------------------------------------

def _test_is_inplace_importable_and_callable():
    import inspect
    fn = getattr(_inplace, "is_inplace", None)
    if fn is None:
        raise AssertionError("_inplace has no is_inplace function")
    params = list(inspect.signature(fn).parameters.keys())
    if params != ["slug", "git_root", "cfg"]:
        raise AssertionError(
            f"is_inplace signature mismatch: expected ['slug', 'git_root', 'cfg'], got {params}"
        )
    print("PASS _inplace.is_inplace — importable with correct signature")


def _test_prompt_stale_worktree_importable_and_callable():
    import inspect
    fn = getattr(_inplace, "prompt_stale_worktree", None)
    if fn is None:
        raise AssertionError("_inplace has no prompt_stale_worktree function")
    params = list(inspect.signature(fn).parameters.keys())
    if params != ["slug", "worktree_path"]:
        raise AssertionError(
            f"prompt_stale_worktree signature mismatch: expected ['slug', 'worktree_path'], got {params}"
        )
    print("PASS _inplace.prompt_stale_worktree — importable with correct signature")


def _test_is_inplace_returns_bool():
    import typing
    hints = typing.get_type_hints(_inplace.is_inplace)
    if hints.get("return") is not bool:
        raise AssertionError(f"is_inplace return annotation expected bool, got {hints.get('return')!r}")
    print("PASS _inplace.is_inplace — return annotation is bool")


def _test_prompt_stale_worktree_returns_str():
    import typing
    hints = typing.get_type_hints(_inplace.prompt_stale_worktree)
    if hints.get("return") is not str:
        raise AssertionError(
            f"prompt_stale_worktree return annotation expected str, got {hints.get('return')!r}"
        )
    print("PASS _inplace.prompt_stale_worktree — return annotation is str")


if __name__ == "__main__":
    sys.exit(main())
