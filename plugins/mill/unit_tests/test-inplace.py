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


def _test_is_inplace_true_when_topology_matches():
    """Returns True when git_root IS the main worktree root."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        git_root = tmp / "hub"
        git_root.mkdir()
        cfg = {}
        # git_root is reported as the main worktree root -- in-place.
        with patch("_inplace.resolve_main_worktree_root", return_value=git_root):
            result = _inplace.is_inplace("my-task", git_root, cfg)

        if not result:
            raise AssertionError("Expected is_inplace to return True")
        print("PASS is_inplace — topology matches -> True")


def _test_is_inplace_false_when_topology_differs_735_regression():
    """Returns False when git_root is NOT the main worktree root.

    Regression test for issue #735: a real separate worktree parked at a
    non-canonical location (no directory at the canonical <wts>/<slug>/
    path) must still be detected as a worktree, not misdetected as
    in-place. The old path-existence implementation would have wrongly
    returned True here.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        git_root = tmp / "hub"
        git_root.mkdir()
        # Simulate the main worktree living elsewhere -- no directory is
        # created at the canonical <wts>/my-task/ path at all.
        main_root = tmp / "elsewhere" / "main"
        main_root.mkdir(parents=True)
        cfg = {}

        with patch("_inplace.resolve_main_worktree_root", return_value=main_root):
            result = _inplace.is_inplace("my-task", git_root, cfg)

        if result:
            raise AssertionError(
                "Expected is_inplace to return False when topology differs"
            )
        print("PASS is_inplace — topology differs (#735 regression) -> False")


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
        _test_is_inplace_true_when_topology_matches,
        _test_is_inplace_false_when_topology_differs_735_regression,
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
