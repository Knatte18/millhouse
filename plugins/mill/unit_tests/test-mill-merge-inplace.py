"""Smoke tests for _inplace public surface (mill-merge in-place integration)."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _inplace  # noqa: E402


def _test_is_inplace_importable_and_callable():
    """is_inplace exists and accepts the three declared parameters."""
    fn = getattr(_inplace, "is_inplace", None)
    if fn is None:
        raise AssertionError("_inplace has no is_inplace function")
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    if params != ["slug", "git_root", "cfg"]:
        raise AssertionError(
            f"is_inplace signature mismatch: expected ['slug', 'git_root', 'cfg'], got {params}"
        )
    print("PASS _inplace.is_inplace — importable with correct signature")


def _test_prompt_stale_worktree_importable_and_callable():
    """prompt_stale_worktree exists and accepts the two declared parameters."""
    fn = getattr(_inplace, "prompt_stale_worktree", None)
    if fn is None:
        raise AssertionError("_inplace has no prompt_stale_worktree function")
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    if params != ["slug", "worktree_path"]:
        raise AssertionError(
            f"prompt_stale_worktree signature mismatch: "
            f"expected ['slug', 'worktree_path'], got {params}"
        )
    print("PASS _inplace.prompt_stale_worktree — importable with correct signature")


def _test_is_inplace_returns_bool():
    """is_inplace return type annotation is bool."""
    import typing

    hints = typing.get_type_hints(_inplace.is_inplace)
    return_hint = hints.get("return")
    if return_hint is not bool:
        raise AssertionError(
            f"is_inplace return annotation expected bool, got {return_hint!r}"
        )
    print("PASS _inplace.is_inplace — return annotation is bool")


def _test_prompt_stale_worktree_returns_str():
    """prompt_stale_worktree return type annotation is str."""
    import typing

    hints = typing.get_type_hints(_inplace.prompt_stale_worktree)
    return_hint = hints.get("return")
    if return_hint is not str:
        raise AssertionError(
            f"prompt_stale_worktree return annotation expected str, got {return_hint!r}"
        )
    print("PASS _inplace.prompt_stale_worktree — return annotation is str")


def main() -> int:
    tests = [
        _test_is_inplace_importable_and_callable,
        _test_prompt_stale_worktree_importable_and_callable,
        _test_is_inplace_returns_bool,
        _test_prompt_stale_worktree_returns_str,
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
    print(f"All {len(tests)} _inplace smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
