"""
Unit-level smoke tests for mill-spawn pure helpers.

``pick_task`` and ``pick_worktree_color`` are the two functions with
enough branching to warrant standalone checks — the rest of mill-spawn
is covered by ``test-spawn.py``'s end-to-end run.

Run from hub root:
    python plugins/mill/integration_tests/test-spawn-units.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _tasks_md  # noqa: E402

# mill-spawn.py has a dash in its filename so plain ``import mill_spawn``
# doesn't work. Load it directly via importlib.
spec = importlib.util.spec_from_file_location(
    "mill_spawn", SCRIPTS / "mill-spawn.py"
)
mill_spawn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mill_spawn)


def _task(slug: str, phase: str | None = None) -> _tasks_md.Task:
    return _tasks_md.Task(
        slug=slug, title=slug.replace("-", " ").title(),
        phase=phase, has_proposal=False, heading_line_no=0,
    )


def test_pick_task_fast_path() -> None:
    tasks = [_task("one"), _task("two", "s"), _task("three", "s")]
    mode, picked, candidates = mill_spawn.pick_task(tasks)
    assert mode == "fast-path", f"Expected fast-path, got {mode!r}"
    assert picked.slug == "two", "Fast-path must pick the first [s] in file order"
    assert candidates == []
    print("PASS: pick_task() fast-path returns first [s] task")


def test_pick_task_numbered() -> None:
    tasks = [
        _task("claimed", "active"),
        _task("backlog-a"),
        _task("tombstone", "done"),
        _task("backlog-b"),
    ]
    mode, picked, candidates = mill_spawn.pick_task(tasks)
    assert mode == "numbered"
    assert picked is None
    assert [t.slug for t in candidates] == ["backlog-a", "backlog-b"], (
        f"Numbered candidates must exclude claimed/done: {[t.slug for t in candidates]!r}"
    )
    print("PASS: pick_task() numbered filters [active]/[done] from candidates")


def test_pick_task_empty() -> None:
    tasks = [_task("claimed", "active"), _task("tombstone", "done")]
    mode, picked, candidates = mill_spawn.pick_task(tasks)
    assert mode == "empty" and picked is None and candidates == []
    print("PASS: pick_task() empty when only claimed/done tasks exist")

    # Totally empty input → empty.
    mode, _, _ = mill_spawn.pick_task([])
    assert mode == "empty"
    print("PASS: pick_task() empty when task list is empty")


def test_pick_worktree_color_no_siblings() -> None:
    """With no siblings, we always get the first non-green palette entry."""
    with tempfile.TemporaryDirectory() as tmp:
        wt_dir = Path(tmp) / "empty-worktrees"
        wt_dir.mkdir()
        color = mill_spawn.pick_worktree_color(wt_dir)
        assert color.lower() != mill_spawn._MAIN_WORKTREE_COLOR.lower(), (
            "Must never return the hub-reserved green"
        )
        assert color in mill_spawn._WORKTREE_COLOR_PALETTE
        print(f"PASS: pick_worktree_color() picks first non-green when empty ({color})")


def test_pick_worktree_color_skips_used() -> None:
    """Siblings with assigned colours must be excluded."""
    with tempfile.TemporaryDirectory() as tmp:
        wt_dir = Path(tmp) / "worktrees"
        wt_dir.mkdir()
        # Seed three siblings using purple/blue/yellow.
        for slug, color in (
            ("a", "#7d2d6b"),
            ("b", "#2d4f7d"),
            ("c", "#7d5c2d"),
        ):
            sib = wt_dir / slug / ".vscode"
            sib.mkdir(parents=True)
            (sib / "settings.json").write_text(
                json.dumps({
                    "workbench.colorCustomizations": {
                        "titleBar.activeBackground": color,
                    },
                }),
                encoding="utf-8",
            )
        color = mill_spawn.pick_worktree_color(wt_dir)
        assert color.lower() not in {"#7d2d6b", "#2d4f7d", "#7d5c2d"}, (
            f"Must not reuse a sibling's colour: {color}"
        )
        assert color.lower() != mill_spawn._MAIN_WORKTREE_COLOR.lower()
        print(f"PASS: pick_worktree_color() skips sibling-used colours ({color})")


def main() -> int:
    try:
        test_pick_task_fast_path()
        test_pick_task_numbered()
        test_pick_task_empty()
        test_pick_worktree_color_no_siblings()
        test_pick_worktree_color_skips_used()
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("All mill-spawn unit smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
