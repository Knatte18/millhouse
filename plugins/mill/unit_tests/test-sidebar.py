"""Unit tests for plugins/mill/scripts/_sidebar.py."""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _sidebar import render_sidebar  # noqa: E402


def test_linked_task_contains_md_suffix() -> None:
    """Task with has_proposal=True emits a link ending in .md."""
    tasks = [{"slug": "my-task", "title": "My Task", "has_proposal": True}]
    output = render_sidebar(tasks)
    assert "(proposal-my-task.md)" in output, (
        f"Expected '(proposal-my-task.md)' in sidebar output; got:\n{output}"
    )
    print("PASS: render_sidebar linked task contains (proposal-<slug>.md)")


def test_plain_task_has_no_parenthesised_link() -> None:
    """Task with has_proposal=False emits plain text — no parenthesised link."""
    tasks = [{"slug": "plain-task", "title": "Plain Task", "has_proposal": False}]
    output = render_sidebar(tasks)
    for line in output.splitlines():
        if "Plain Task" in line:
            assert "(" not in line, (
                f"Plain task line must not contain a parenthesised link; got: {line!r}"
            )
            break
    else:
        raise AssertionError("'Plain Task' line not found in sidebar output")
    print("PASS: render_sidebar plain task has no parenthesised link")


def main() -> int:
    tests = [
        test_linked_task_contains_md_suffix,
        test_plain_task_has_no_parenthesised_link,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
