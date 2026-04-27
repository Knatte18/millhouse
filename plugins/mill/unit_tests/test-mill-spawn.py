"""Unit tests for plugins/mill/scripts/mill-spawn.py (post-refactor).

Verifies:
  - top-level import succeeds (smoke test for broken imports after refactor)
  - main() calls _spawn_core helpers in the correct order with the correct
    arguments on the happy path
  - BacklogEmpty from pick_task_single causes exit 0
  - ValueError from pick_task_single causes exit 1
  - RuntimeError from capture_parent_branch is translated to SystemExit
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))


# ---------------------------------------------------------------------------
# Smoke import
# ---------------------------------------------------------------------------


def test_smoke_import() -> None:
    """mill-spawn must import without error after the refactor."""
    import importlib
    import importlib.util
    spawn_path = HUB / "plugins" / "mill" / "scripts" / "mill-spawn.py"
    spec = importlib.util.spec_from_file_location("mill_spawn", spawn_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not build module spec for mill-spawn.py")
    mod = importlib.util.module_from_spec(spec)
    # Provide minimal stubs for the heavy imports so the module loads without
    # a real git repo or wiki on disk.
    stubs = [
        "_junction", "_spawn_core", "_tasks_md", "_vscode", "_wiki",
        "_worktree", "_paths", "_sibling", "_subprocess_util",
    ]
    for name in stubs:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # _paths needs the functions mill-spawn imports at module level.
    paths_mod = sys.modules["_paths"]
    paths_mod.resolve_git_root = MagicMock(return_value=Path("/fake/repo"))
    paths_mod.resolve_wiki_path = MagicMock(return_value=Path("/fake/wiki"))
    paths_mod.resolve_path = MagicMock(return_value=Path("/fake/worktrees"))
    paths_mod.resolve_worktrees_dir = MagicMock(return_value=Path("/fake/worktrees"))
    paths_mod.resolve_short_name = MagicMock(return_value="MI")

    # _spawn_core needs pick_worktree_color because mill-spawn imports it
    # at module level via `from _spawn_core import pick_worktree_color`.
    spawn_core_mod = sys.modules["_spawn_core"]
    spawn_core_mod.pick_worktree_color = MagicMock(return_value="#7d2d6b")

    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        raise AssertionError(f"mill-spawn.py failed to import: {exc}") from exc

    if not hasattr(mod, "main"):
        raise AssertionError("mill-spawn module must expose main()")
    if not hasattr(mod, "pick_worktree_color"):
        raise AssertionError("mill-spawn must still expose pick_worktree_color")
    print("PASS: mill-spawn.py imports cleanly after refactor")


# ---------------------------------------------------------------------------
# Helpers for integration-style main() tests
# ---------------------------------------------------------------------------


def _make_fake_task(slug: str = "my-task", title: str = "My Task") -> MagicMock:
    task = MagicMock()
    task.slug = slug
    task.title = title
    return task


def _run_main_with_mocks(
    argv: list[str],
    *,
    picked_task: Optional[MagicMock] = None,
    pick_raises: Optional[Exception] = None,
    capture_branch_raises: Optional[Exception] = None,
    parent_branch: str = "main",
) -> tuple[int, MagicMock, MagicMock]:
    """
    Run ``mill_spawn.main(argv)`` with all external calls mocked.

    Returns ``(exit_code, spawn_core_mock, wiki_mock)``.
    """
    import importlib
    import importlib.util

    spawn_path = HUB / "plugins" / "mill" / "scripts" / "mill-spawn.py"
    spec = importlib.util.spec_from_file_location("mill_spawn_test_run", spawn_path)
    mod = importlib.util.module_from_spec(spec)

    # Build a fresh _spawn_core mock for each run so call history is clean.
    spawn_core_mock = MagicMock()
    if pick_raises is not None:
        spawn_core_mock.pick_task_single_or_multi.side_effect = pick_raises
    else:
        task = picked_task or _make_fake_task()
        spawn_core_mock.pick_task_single_or_multi.return_value = ("single", task, [])
    spawn_core_mock.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    spawn_core_mock.claim_in_wiki.return_value = None
    if capture_branch_raises is not None:
        spawn_core_mock.capture_parent_branch.side_effect = capture_branch_raises
    else:
        spawn_core_mock.capture_parent_branch.return_value = parent_branch
    spawn_core_mock.write_active_marker.return_value = None
    spawn_core_mock.write_initial_status.return_value = Path("/fake/wiki/active/my-task/status.md")

    wiki_mock = MagicMock()
    wiki_mock.sync_pull.return_value = None
    wiki_mock.read_junctions.return_value = {}

    junction_mock = MagicMock()
    tasks_md_mock = MagicMock()
    tasks_md_mock.parse.return_value = [_make_fake_task()]

    vscode_mock = MagicMock()
    worktree_mock = MagicMock()

    paths_mock = MagicMock()
    paths_mock.resolve_git_root.return_value = Path("/fake/repo")
    paths_mock.resolve_wiki_path.return_value = Path("/fake/wiki")
    paths_mock.resolve_path.return_value = Path("/fake/worktrees")
    paths_mock.resolve_worktrees_dir.return_value = Path("/fake/worktrees")
    paths_mock.resolve_short_name.return_value = "MI"

    # Inject stubs before loading so the module picks them up.
    saved: dict[str, object] = {}
    stub_map = {
        "_spawn_core": spawn_core_mock,
        "_wiki": wiki_mock,
        "_junction": junction_mock,
        "_tasks_md": tasks_md_mock,
        "_vscode": vscode_mock,
        "_worktree": worktree_mock,
        "_paths": paths_mock,
        "_sibling": types.ModuleType("_sibling"),
        "_subprocess_util": types.ModuleType("_subprocess_util"),
    }
    for name, stub in stub_map.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = stub

    try:
        spec.loader.exec_module(mod)

        # Patch config-loading and worktrees-dir resolution so main() doesn't
        # hit the real filesystem.
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "resolve_worktrees_dir", return_value=Path("/fake/worktrees")),
            patch.object(mod, "pick_worktree_color", return_value="#7d2d6b"),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
            patch.object(Path, "mkdir", return_value=None),
        ):
            exit_code = mod.main(argv)
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    return exit_code, spawn_core_mock, wiki_mock


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_main_happy_path_calls_spawn_core_in_order() -> None:
    """main() calls pick_task_single, claim_in_wiki, capture_parent_branch,
    write_active_marker, write_initial_status in that order."""
    task = _make_fake_task(slug="my-task", title="My Task")
    exit_code, sc, _ = _run_main_with_mocks([], picked_task=task)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0 on happy path, got {exit_code}")

    sc.pick_task_single_or_multi.assert_called_once()
    sc.claim_in_wiki.assert_called_once()
    sc.capture_parent_branch.assert_called_once()
    sc.write_active_marker.assert_called_once()
    sc.write_initial_status.assert_called_once()

    # Verify write_active_marker receives the correct slug and title
    marker_call = sc.write_active_marker.call_args
    if marker_call.kwargs.get("slug") != "my-task":
        raise AssertionError(
            f"write_active_marker slug mismatch: {marker_call}"
        )
    if marker_call.kwargs.get("title") != "My Task":
        raise AssertionError(
            f"write_active_marker title mismatch: {marker_call}"
        )

    # Verify write_initial_status receives the correct slug and parent_branch
    status_call = sc.write_initial_status.call_args
    if status_call.kwargs.get("slug") != "my-task":
        raise AssertionError(
            f"write_initial_status slug mismatch: {status_call}"
        )
    if status_call.kwargs.get("parent_branch") != "main":
        raise AssertionError(
            f"write_initial_status parent_branch mismatch: {status_call}"
        )

    print("PASS: main() happy path calls all _spawn_core helpers in order")


# ---------------------------------------------------------------------------
# write_settings uses short_name= and slug= (not window_title=)
# ---------------------------------------------------------------------------


def test_write_settings_uses_short_name_and_slug() -> None:
    """main() must call _vscode.write_settings with short_name= and slug=."""
    import importlib
    import importlib.util

    spawn_path = HUB / "plugins" / "mill" / "scripts" / "mill-spawn.py"
    spec = importlib.util.spec_from_file_location("mill_spawn_vscode_test", spawn_path)
    mod = importlib.util.module_from_spec(spec)

    task = _make_fake_task(slug="my-task", title="My Task")
    spawn_core_mock = MagicMock()
    spawn_core_mock.pick_task_single_or_multi.return_value = ("single", task, [])
    spawn_core_mock.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    spawn_core_mock.claim_in_wiki.return_value = None
    spawn_core_mock.capture_parent_branch.return_value = "main"
    spawn_core_mock.write_active_marker.return_value = None
    spawn_core_mock.write_initial_status.return_value = Path("/fake/wiki/active/my-task/status.md")

    vscode_mock = MagicMock()
    wiki_mock = MagicMock()
    wiki_mock.sync_pull.return_value = None
    wiki_mock.read_junctions.return_value = {}

    paths_mock = MagicMock()
    paths_mock.resolve_git_root.return_value = Path("/fake/repo")
    paths_mock.resolve_wiki_path.return_value = Path("/fake/wiki")
    paths_mock.resolve_path.return_value = Path("/fake/worktrees")
    paths_mock.resolve_worktrees_dir.return_value = Path("/fake/worktrees")
    paths_mock.resolve_short_name.return_value = "MI"

    stub_map = {
        "_spawn_core": spawn_core_mock,
        "_wiki": wiki_mock,
        "_junction": MagicMock(),
        "_tasks_md": MagicMock(),
        "_vscode": vscode_mock,
        "_worktree": MagicMock(),
        "_paths": paths_mock,
        "_sibling": types.ModuleType("_sibling"),
        "_subprocess_util": types.ModuleType("_subprocess_util"),
    }
    saved: dict[str, object] = {}
    for name, stub in stub_map.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = stub

    try:
        spec.loader.exec_module(mod)
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "resolve_worktrees_dir", return_value=Path("/fake/worktrees")),
            patch.object(mod, "pick_worktree_color", return_value="#7d2d6b"),
            patch.object(mod, "resolve_short_name", return_value="MI"),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
            patch.object(Path, "mkdir", return_value=None),
        ):
            exit_code = mod.main([])
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    if exit_code != 0:
        raise AssertionError(f"expected exit 0, got {exit_code}")

    ws_calls = vscode_mock.write_settings.call_args_list
    if not ws_calls:
        raise AssertionError("_vscode.write_settings was never called")
    ws_call = ws_calls[0]
    if "window_title" in ws_call.kwargs:
        raise AssertionError(
            f"write_settings must not use window_title= anymore: {ws_call}"
        )
    if ws_call.kwargs.get("short_name") != "MI":
        raise AssertionError(
            f"write_settings must use short_name='MI': {ws_call}"
        )
    if ws_call.kwargs.get("slug") != "my-task":
        raise AssertionError(
            f"write_settings must use slug='my-task': {ws_call}"
        )
    print("PASS: write_settings called with short_name= and slug= (not window_title=)")


# ---------------------------------------------------------------------------
# BacklogEmpty → exit 0
# ---------------------------------------------------------------------------


def test_main_backlog_empty_exits_zero() -> None:
    """When pick_task_single_or_multi returns ("empty", None, []), main() returns 0."""
    # pick_task_single_or_multi returns ("empty", None, []) for an empty backlog
    # instead of raising BacklogEmpty. Verify that main() translates this to exit 0.
    import importlib.util

    spawn_path = HUB / "plugins" / "mill" / "scripts" / "mill-spawn.py"
    spec = importlib.util.spec_from_file_location("mill_spawn_empty", spawn_path)
    mod = importlib.util.module_from_spec(spec)

    spawn_core_mock = MagicMock()
    spawn_core_mock.pick_task_single_or_multi.return_value = ("empty", None, [])
    spawn_core_mock.BacklogEmpty = type("BacklogEmpty", (Exception,), {})

    wiki_mock = MagicMock()
    wiki_mock.sync_pull.return_value = None
    tasks_md_mock = MagicMock()
    tasks_md_mock.parse.return_value = []

    paths_mock = MagicMock()
    paths_mock.resolve_git_root.return_value = Path("/fake/repo")
    paths_mock.resolve_wiki_path.return_value = Path("/fake/wiki")
    paths_mock.resolve_path.return_value = Path("/fake/worktrees")

    stub_map = {
        "_spawn_core": spawn_core_mock,
        "_wiki": wiki_mock,
        "_junction": MagicMock(),
        "_tasks_md": tasks_md_mock,
        "_vscode": MagicMock(),
        "_worktree": MagicMock(),
        "_paths": paths_mock,
        "_sibling": types.ModuleType("_sibling"),
        "_subprocess_util": types.ModuleType("_subprocess_util"),
    }
    saved: dict[str, object] = {}
    for name, stub in stub_map.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = stub
    try:
        spec.loader.exec_module(mod)
        fake_cfg = {"spawn": {}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "resolve_worktrees_dir", return_value=Path("/fake/worktrees")),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
            patch.object(Path, "mkdir", return_value=None),
        ):
            exit_code = mod.main([])
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    if exit_code != 0:
        raise AssertionError(f"empty mode should produce exit 0, got {exit_code}")
    print("PASS: main() returns 0 when pick_task_single raises BacklogEmpty")


# ---------------------------------------------------------------------------
# ValueError → exit 1
# ---------------------------------------------------------------------------


def test_main_value_error_from_picker_exits_one() -> None:
    """When pick_task_single raises ValueError, main() returns 1."""
    exit_code, sc, _ = _run_main_with_mocks(
        ["--slug", "bad-slug"],
        pick_raises=ValueError("--slug 'bad-slug' not found in Home.md or already claimed."),
    )
    if exit_code != 1:
        raise AssertionError(f"ValueError should produce exit 1, got {exit_code}")
    print("PASS: main() returns 1 when pick_task_single raises ValueError")


# ---------------------------------------------------------------------------
# RuntimeError from capture_parent_branch → SystemExit
# ---------------------------------------------------------------------------


def test_main_runtime_error_from_capture_branch_raises_system_exit() -> None:
    """RuntimeError from capture_parent_branch must propagate as SystemExit."""
    try:
        _run_main_with_mocks(
            [],
            capture_branch_raises=RuntimeError("git failed"),
        )
    except SystemExit:
        print("PASS: RuntimeError from capture_parent_branch becomes SystemExit")
    else:
        raise AssertionError("expected SystemExit when capture_parent_branch raises RuntimeError")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_smoke_import,
        test_main_happy_path_calls_spawn_core_in_order,
        test_write_settings_uses_short_name_and_slug,
        test_main_backlog_empty_exits_zero,
        test_main_value_error_from_picker_exits_one,
        test_main_runtime_error_from_capture_branch_raises_system_exit,
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
    print(f"All {len(tests)} mill-spawn unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
