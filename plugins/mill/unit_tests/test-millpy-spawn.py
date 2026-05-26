"""Unit tests for plugins/mill/scripts/millpy-spawn.py (post-refactor).

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

_UNIT_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_UNIT_TESTS))

import _test_helpers  # noqa: E402


# ---------------------------------------------------------------------------
# Smoke import
# ---------------------------------------------------------------------------


def test_smoke_import() -> None:
    """mill-spawn must import without error after the refactor."""
    import importlib
    import importlib.util
    spawn_path = HUB / "plugins" / "mill" / "scripts" / "millpy-spawn.py"
    spec = importlib.util.spec_from_file_location("mill_spawn", spawn_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not build module spec for millpy-spawn.py")
    mod = importlib.util.module_from_spec(spec)
    # Provide minimal stubs for the heavy imports so the module loads without
    # a real git repo or wiki on disk.
    stubs = [
        "_junction", "_setup", "_spawn_core", "_vscode",
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
    paths_mod.resolve_container_path = MagicMock(return_value=Path("/fake/container"))
    paths_mod.resolve_hub_path = MagicMock(return_value=Path("/fake/hub"))
    paths_mod.resolve_hub_relative_path = MagicMock(
        side_effect=lambda wt, sub: wt if sub == "." else wt / sub
    )
    paths_mod.resolve_main_worktree_root = MagicMock(return_value=Path("/fake/repo"))

    # _setup needs create_hub_links so mill-spawn can call it.
    setup_mod = sys.modules["_setup"]
    setup_mod.create_hub_links = MagicMock(return_value={"junctions": [], "hardlinks": []})
    paths_mod.resolve_container_path = MagicMock(return_value=Path("/fake/container"))

    # _spawn_core needs pick_worktree_color because mill-spawn imports it
    # at module level via `from _spawn_core import pick_worktree_color`.
    spawn_core_mod = sys.modules["_spawn_core"]
    spawn_core_mod.pick_worktree_color = MagicMock(return_value="#7d2d6b")

    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        raise AssertionError(f"millpy-spawn.py failed to import: {exc}") from exc

    if not hasattr(mod, "main"):
        raise AssertionError("mill-spawn module must expose main()")
    if not hasattr(mod, "pick_worktree_color"):
        raise AssertionError("mill-spawn must still expose pick_worktree_color")
    print("PASS: millpy-spawn.py imports cleanly after refactor")


# ---------------------------------------------------------------------------
# Helpers for integration-style main() tests
# ---------------------------------------------------------------------------


def _make_fake_task(slug: str = "my-task", title: str = "My Task") -> dict:
    return {
        "slug": slug,
        "title": title,
        "group": None,
        "brief": "",
        "status": "active",
        "id": 0,
        "body": "",
        "has_proposal": False,
    }


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

    spawn_path = HUB / "plugins" / "mill" / "scripts" / "millpy-spawn.py"
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
    spawn_core_mock.write_initial_status.return_value = Path("/fake/worktrees/my-task/status.md")

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
    paths_mock.resolve_container_path.return_value = Path("/fake/container")
    paths_mock.status_path.return_value = Path("/fake/worktrees/my-task/_mill/status.md")

    setup_mock = MagicMock()
    setup_mock.create_hub_links.return_value = {"junctions": [], "hardlinks": []}

    # Inject stubs before loading so the module picks them up.
    saved: dict[str, object] = {}
    stub_map = {
        "_spawn_core": spawn_core_mock,
        "_setup": setup_mock,
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
    write_initial_status in that order."""
    task = _make_fake_task(slug="my-task", title="My Task")
    exit_code, sc, _ = _run_main_with_mocks([], picked_task=task)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0 on happy path, got {exit_code}")

    sc.pick_task_single_or_multi.assert_called_once()
    sc.claim_in_wiki.assert_called_once()
    sc.capture_parent_branch.assert_called_once()
    sc.write_initial_status.assert_called_once()

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
    if status_call.kwargs.get("branch") != "my-task":
        raise AssertionError(
            f"write_initial_status branch mismatch: {status_call}"
        )
    # Must be called with worktree_path=, not wiki_path= (state on worktree).
    # This is an intentional mock-level check: write_initial_status is patched
    # so no files are touched on disk. The absence of wiki_path= in kwargs is
    # the correct proxy — the real function writes to worktree_path/status.md.
    if "wiki_path" in status_call.kwargs:
        raise AssertionError(
            f"write_initial_status must not be called with wiki_path=: {status_call}"
        )
    expected_wt = Path("/fake/worktrees") / "my-task"
    if status_call.kwargs.get("worktree_path") != expected_wt:
        raise AssertionError(
            f"write_initial_status worktree_path should be {expected_wt}, "
            f"got {status_call.kwargs.get('worktree_path')!r}"
        )

    print("PASS: main() happy path calls all _spawn_core helpers in order")


# ---------------------------------------------------------------------------
# write_settings uses short_name= and slug= (not window_title=)
# ---------------------------------------------------------------------------


def test_write_settings_uses_short_name_and_slug() -> None:
    """main() must call _vscode.write_settings with short_name= and slug=."""
    import importlib
    import importlib.util

    spawn_path = HUB / "plugins" / "mill" / "scripts" / "millpy-spawn.py"
    spec = importlib.util.spec_from_file_location("mill_spawn_vscode_test", spawn_path)
    mod = importlib.util.module_from_spec(spec)

    task = _make_fake_task(slug="my-task", title="My Task")
    spawn_core_mock = MagicMock()
    spawn_core_mock.pick_task_single_or_multi.return_value = ("single", task, [])
    spawn_core_mock.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    spawn_core_mock.claim_in_wiki.return_value = None
    spawn_core_mock.capture_parent_branch.return_value = "main"
    spawn_core_mock.write_initial_status.return_value = Path("/fake/worktrees/my-task/status.md")

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
    paths_mock.resolve_container_path.return_value = Path("/fake/container")
    paths_mock.status_path.return_value = Path("/fake/worktrees/my-task/_mill/status.md")

    setup_mock = MagicMock()
    setup_mock.create_hub_links.return_value = {"junctions": [], "hardlinks": []}

    stub_map = {
        "_spawn_core": spawn_core_mock,
        "_setup": setup_mock,
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
# BacklogEmpty -> exit 0
# ---------------------------------------------------------------------------


def test_main_backlog_empty_exits_zero() -> None:
    """When pick_task_single_or_multi returns ("empty", None, []), main() returns 0."""
    # pick_task_single_or_multi returns ("empty", None, []) for an empty backlog
    # instead of raising BacklogEmpty. Verify that main() translates this to exit 0.
    import importlib.util

    spawn_path = HUB / "plugins" / "mill" / "scripts" / "millpy-spawn.py"
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

    setup_mock = MagicMock()
    setup_mock.create_hub_links.return_value = {"junctions": [], "hardlinks": []}
    paths_mock.resolve_container_path = MagicMock(return_value=Path("/fake/container"))

    stub_map = {
        "_spawn_core": spawn_core_mock,
        "_setup": setup_mock,
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
# ValueError -> exit 1
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
# RuntimeError from capture_parent_branch -> SystemExit
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
# _setup.create_hub_links called AFTER portal junction.create
# ---------------------------------------------------------------------------


def test_create_hub_links_called_after_portal_creation() -> None:
    """create_hub_links must be invoked AFTER the portal _junction.create call.

    Uses a call_log side-effect to record the order of _junction.create and
    _setup.create_hub_links invocations and asserts the portal entry is
    created first.
    """
    import importlib
    import importlib.util

    spawn_path = HUB / "plugins" / "mill" / "scripts" / "millpy-spawn.py"
    spec = importlib.util.spec_from_file_location("mill_spawn_order_test", spawn_path)
    mod = importlib.util.module_from_spec(spec)

    task = _make_fake_task(slug="my-task", title="My Task")
    spawn_core_mock = MagicMock()
    spawn_core_mock.pick_task_single_or_multi.return_value = ("single", task, [])
    spawn_core_mock.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    spawn_core_mock.claim_in_wiki.return_value = None
    spawn_core_mock.capture_parent_branch.return_value = "main"
    spawn_core_mock.write_initial_status.return_value = Path("/fake/worktrees/my-task/status.md")

    container_path = Path("/fake/container")
    paths_mock = MagicMock()
    paths_mock.resolve_git_root.return_value = Path("/fake/repo")
    paths_mock.resolve_wiki_path.return_value = Path("/fake/wiki")
    paths_mock.resolve_path.return_value = Path("/fake/worktrees")
    paths_mock.resolve_worktrees_dir.return_value = Path("/fake/worktrees")
    paths_mock.resolve_short_name.return_value = "MI"
    paths_mock.resolve_container_path.return_value = container_path

    call_log: list[str] = []

    junction_mock = MagicMock()
    junction_mock.create.side_effect = lambda *a, **kw: call_log.append("junction.create")

    setup_mock = MagicMock()
    setup_mock.create_hub_links.side_effect = (
        lambda *a, **kw: call_log.append("create_hub_links") or {"junctions": [], "hardlinks": []}
    )

    wiki_mock = MagicMock()
    wiki_mock.sync_pull.return_value = None
    wiki_mock.read_junctions.return_value = {}

    stub_map = {
        "_spawn_core": spawn_core_mock,
        "_setup": setup_mock,
        "_wiki": wiki_mock,
        "_junction": junction_mock,
        "_tasks_md": MagicMock(),
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
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "resolve_worktrees_dir", return_value=Path("/fake/worktrees")),
            patch.object(mod, "pick_worktree_color", return_value="#7d2d6b"),
            patch.object(mod, "resolve_container_path", return_value=container_path),
            patch.object(mod, "resolve_main_worktree_root", return_value=Path("/fake/repo")),
            patch.object(
                mod, "resolve_hub_relative_path",
                side_effect=lambda wt, sub: wt if sub == "." else wt / sub,
            ),
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

    # Verify call ordering: junction.create (portal entry) must come before create_hub_links
    if "junction.create" not in call_log:
        raise AssertionError("_junction.create was never called (portal entry missing)")
    if "create_hub_links" not in call_log:
        raise AssertionError("_setup.create_hub_links was never called")

    portal_idx = call_log.index("junction.create")
    hub_links_idx = call_log.index("create_hub_links")
    if portal_idx >= hub_links_idx:
        raise AssertionError(
            f"portal _junction.create must precede create_hub_links; "
            f"call_log={call_log}"
        )

    # Verify create_hub_links received dest_hub (== worktree_path for standard layout) as first arg
    hub_links_call = setup_mock.create_hub_links.call_args
    if hub_links_call is None:
        raise AssertionError("create_hub_links call_args is None")
    first_arg = hub_links_call.args[0] if hub_links_call.args else None
    expected_worktree = Path("/fake/worktrees") / "my-task"
    if first_arg != expected_worktree:
        raise AssertionError(
            f"create_hub_links first arg should be {expected_worktree}, got {first_arg!r}"
        )

    # Verify portal target is worktree/_mill (not wiki/active/)
    all_create_calls = junction_mock.create.call_args_list
    expected_portal_link = container_path / "portals" / "my-task"
    portal_create_call = next(
        (c for c in all_create_calls
         if (c.kwargs.get("link_path") or (c.args[1] if len(c.args) > 1 else None))
         == expected_portal_link),
        None,
    )
    if portal_create_call is None:
        raise AssertionError(f"No junction.create call with portal link_path {expected_portal_link}")
    portal_target = portal_create_call.kwargs.get("target") or (portal_create_call.args[0] if portal_create_call.args else None)
    expected_portal_target = Path("/fake/worktrees") / "my-task" / "_mill"
    if portal_target != expected_portal_target:
        raise AssertionError(
            f"portal target should be {expected_portal_target!r}, got {portal_target!r}"
        )

    # .portals junction is NOT created by millpy-spawn directly; it is
    # created (when configured) by _setup.create_hub_links via the
    # mill-config.yaml junctions section.
    expected_portals_link = Path("/fake/worktrees") / "my-task" / ".portals"
    portals_create_call = next(
        (c for c in all_create_calls
         if (c.kwargs.get("link_path") or (c.args[1] if len(c.args) > 1 else None))
         == expected_portals_link),
        None,
    )
    if portals_create_call is not None:
        raise AssertionError(
            f".portals junction should NOT be created directly by millpy-spawn; "
            f"create_hub_links owns it. Got: {portals_create_call}"
        )

    print("PASS: _setup.create_hub_links called after portal _junction.create")


# ---------------------------------------------------------------------------
# dry-run prints worktree status path
# ---------------------------------------------------------------------------


def test_main_dry_run_prints_worktree_status_path() -> None:
    """--dry-run output must print <worktree_path>/status.md, not a wiki path."""
    import io

    captured = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured
    try:
        exit_code, sc, _ = _run_main_with_mocks(["--dry-run"])
    finally:
        sys.stdout = original_stdout

    if exit_code != 0:
        raise AssertionError(f"expected exit 0 for --dry-run, got {exit_code}")

    output = captured.getvalue()
    expected_path = str(Path("/fake/worktrees") / "my-task" / "_mill" / "status.md")
    if expected_path not in output:
        raise AssertionError(
            f"dry-run output must contain {expected_path!r}\n"
            f"Got:\n{output}"
        )
    if "wiki/active" in output:
        raise AssertionError(
            f"dry-run output must NOT contain 'wiki/active'\nGot:\n{output}"
        )
    # write_initial_status must NOT have been called (dry-run exits before live steps)
    if sc.write_initial_status.called:
        raise AssertionError(
            "write_initial_status must not be called in --dry-run mode"
        )
    print("PASS: --dry-run output prints worktree status path (not wiki path)")


# ---------------------------------------------------------------------------
# Helpers for real-filesystem spawn tests (Cards 9-11)
# ---------------------------------------------------------------------------


def _fake_copy_millhouse_real(src: Path, dst: Path, exclude: set) -> None:
    """Copy .millhouse contents from src to dst, skipping excluded names."""
    import shutil as _shutil
    dst.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    for item in src.iterdir():
        if item.name in exclude or item.is_symlink():
            continue
        target = dst / item.name
        if item.is_dir():
            _shutil.copytree(str(item), str(target), dirs_exist_ok=True)
        else:
            _shutil.copy2(str(item), str(target))


def _run_spawn_real_fs(
    tmpdir: Path,
    hub_subpath: str,
    slug: str = "test-task",
    title: str = "Test Task",
) -> tuple[int, Path, MagicMock, MagicMock]:
    """
    Run spawn main() with ``tmpdir`` as the root filesystem.

    Mocks all git/wiki/junction operations; lets Python file I/O happen.
    Returns ``(exit_code, worktree_path, vscode_mock, setup_mock)``.
    """
    import importlib.util
    import yaml

    # Source hub filesystem
    hub = tmpdir / "hub"
    (hub / ".millhouse").mkdir(parents=True)
    src_config: dict = {}
    if hub_subpath != ".":
        src_config["hub_relative_path"] = hub_subpath
    (hub / ".millhouse" / "config.local.yaml").write_text(
        yaml.safe_dump(src_config) if src_config else "",
        encoding="utf-8",
    )

    wiki = tmpdir / "wiki"
    wiki.mkdir()
    (wiki / "config.yaml").write_text("junctions: {}\nhardlinks: {}\n", encoding="utf-8")
    (wiki / "Home.md").write_text("# Home\n", encoding="utf-8")

    worktrees = tmpdir / "wts"
    worktrees.mkdir()
    container = tmpdir
    (container / "portals").mkdir(exist_ok=True)

    worktree_path = worktrees / slug

    task = _make_fake_task(slug=slug, title=title)
    spawn_core_mock = MagicMock()
    spawn_core_mock.pick_task_single_or_multi.return_value = ("single", task, [])
    spawn_core_mock.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    spawn_core_mock.claim_in_wiki.return_value = None
    spawn_core_mock.capture_parent_branch.return_value = "main"
    spawn_core_mock.write_initial_status.return_value = worktree_path / "status.md"

    vscode_mock = MagicMock()
    setup_mock = MagicMock()
    setup_mock.create_hub_links.return_value = {"junctions": [], "hardlinks": []}

    worktree_mock = MagicMock()
    worktree_mock.create.side_effect = lambda branch, target, cwd: target.mkdir(
        parents=True, exist_ok=True
    )
    worktree_mock.copy_millhouse.side_effect = _fake_copy_millhouse_real

    paths_mock = MagicMock()
    paths_mock.resolve_git_root.return_value = hub
    paths_mock.resolve_wiki_path.return_value = wiki

    stub_map = {
        "_spawn_core": spawn_core_mock,
        "_setup": setup_mock,
        "_wiki": MagicMock(),
        "_junction": MagicMock(),
        "_tasks_md": MagicMock(),
        "_vscode": vscode_mock,
        "_worktree": worktree_mock,
        "_paths": paths_mock,
        "_sibling": types.ModuleType("_sibling"),
        "_subprocess_util": types.ModuleType("_subprocess_util"),
    }
    saved: dict[str, object] = {}
    for name, stub in stub_map.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = stub

    try:
        spawn_path = HUB / "plugins" / "mill" / "scripts" / "millpy-spawn.py"
        spec = importlib.util.spec_from_file_location(
            f"mill_spawn_fs_{slug}", spawn_path
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        fake_cfg: dict = {}
        if hub_subpath != ".":
            fake_cfg["hub_relative_path"] = hub_subpath

        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "resolve_hub_path", return_value=hub),
            patch.object(mod, "resolve_git_root", return_value=hub),
            patch.object(mod, "resolve_wiki_path", return_value=wiki),
            patch.object(mod, "resolve_worktrees_dir", return_value=worktrees),
            patch.object(mod, "resolve_container_path", return_value=container),
            patch.object(mod, "resolve_main_worktree_root", return_value=hub),
            patch.object(
                mod, "resolve_hub_relative_path",
                side_effect=lambda wt, sub: wt if sub == "." else wt / sub,
            ),
            patch.object(mod, "resolve_short_name", return_value="MI"),
            patch.object(mod, "pick_worktree_color", return_value="#7d2d6b"),
        ):
            exit_code = mod.main([])
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    return exit_code, worktree_path, vscode_mock, setup_mock


# ---------------------------------------------------------------------------
# Test 1: standard layout regression (Card 11)
# ---------------------------------------------------------------------------


def test_spawn_standard_layout_regression() -> None:
    """Standard layout (no hub_relative_path): hub state lands at worktree_path/.millhouse/."""
    with _test_helpers.safe_temp_dir() as tmpdir:
        exit_code, wt, vscode_mock, setup_mock = _run_spawn_real_fs(tmpdir, ".")

        if exit_code != 0:
            raise AssertionError(f"expected exit 0, got {exit_code}")

        # vscode settings target must be at worktree_path/.vscode/settings.json
        ws_call = vscode_mock.write_settings.call_args
        if ws_call is None:
            raise AssertionError("_vscode.write_settings was never called")
        actual_target = ws_call.kwargs.get("target")
        expected_target = wt / ".vscode" / "settings.json"
        if actual_target != expected_target:
            raise AssertionError(
                f"write_settings target should be {expected_target}, got {actual_target!r}"
            )

        # create_hub_links first arg must be dest_hub == worktree_path for standard layout
        hl_call = setup_mock.create_hub_links.call_args
        if hl_call is None:
            raise AssertionError("create_hub_links was never called")
        first_arg = hl_call.args[0] if hl_call.args else None
        if first_arg != wt:
            raise AssertionError(
                f"create_hub_links first arg should be {wt}, got {first_arg!r}"
            )

        # no bootstrap stub written for standard layout
        stub_path = wt / ".millhouse" / "config.local.yaml"
        if stub_path.exists():
            import yaml
            cfg = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
            hub_rel = cfg.get("hub_relative_path", ".")
            if hub_rel != ".":
                raise AssertionError(
                    f"config.local.yaml has unexpected hub_relative_path={hub_rel!r}"
                )

    print("PASS: test_spawn_standard_layout_regression")


# ---------------------------------------------------------------------------
# Test 2: subfolder-install destination layout (Card 11)
# ---------------------------------------------------------------------------


def test_spawn_subfolder_install_destination_layout() -> None:
    """Subfolder-install (hub_relative_path: src/Models): hub state lands at dest_hub."""
    import yaml

    hub_subpath = "src/Models"
    with _test_helpers.safe_temp_dir() as tmpdir:
        exit_code, wt, vscode_mock, setup_mock = _run_spawn_real_fs(
            tmpdir, hub_subpath, slug="subfolder-task", title="Subfolder Task"
        )

        if exit_code != 0:
            raise AssertionError(f"expected exit 0, got {exit_code}")

        dest_hub = wt / hub_subpath

        # (a) vscode target at dest_hub/.vscode/settings.json (via mock call args)
        ws_call = vscode_mock.write_settings.call_args
        if ws_call is None:
            raise AssertionError("_vscode.write_settings was never called")
        actual_target = ws_call.kwargs.get("target")
        expected_target = dest_hub / ".vscode" / "settings.json"
        if actual_target != expected_target:
            raise AssertionError(
                f"write_settings target should be {expected_target}, got {actual_target!r}"
            )

        # (c) bootstrap stub exists at worktree_path/.millhouse/config.local.yaml
        stub_path = wt / ".millhouse" / "config.local.yaml"
        if not stub_path.exists():
            raise AssertionError(f"bootstrap stub not found at {stub_path}")

        # (d) stub YAML equals exactly {"hub_relative_path": "src/Models"} — no extra keys
        stub_cfg = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
        if stub_cfg != {"hub_relative_path": hub_subpath}:
            raise AssertionError(
                f"stub YAML should be exactly {{hub_relative_path: {hub_subpath!r}}}, "
                f"got {stub_cfg!r}"
            )

        # (e) create_hub_links first positional arg == dest_hub
        hl_call = setup_mock.create_hub_links.call_args
        if hl_call is None:
            raise AssertionError("create_hub_links was never called")
        first_arg = hl_call.args[0] if hl_call.args else None
        if first_arg != dest_hub:
            raise AssertionError(
                f"create_hub_links first arg should be {dest_hub}, got {first_arg!r}"
            )

    print("PASS: test_spawn_subfolder_install_destination_layout")


# ---------------------------------------------------------------------------
# Test 3: discovery round-trip on subfolder-install layout (Card 11)
# ---------------------------------------------------------------------------


def test_spawn_discovery_round_trip_subfolder() -> None:
    """After spawn produces a subfolder layout, discover/load_config/resolve all work."""
    import _safe_rmtree
    import tempfile
    import yaml

    hub_subpath = "src/Models"
    slug = "rt-task"
    tmpdir = Path(tempfile.mkdtemp())
    try:
        # Build the subfolder-install layout manually (mirrors what spawn produces)
        worktrees = tmpdir / "wts"
        worktrees.mkdir()
        wt = worktrees / slug
        wt.mkdir()

        # Bootstrap stub at wt/.millhouse/
        stub_dir = wt / ".millhouse"
        stub_dir.mkdir()
        (stub_dir / "config.local.yaml").write_text(
            yaml.safe_dump({"hub_relative_path": hub_subpath}),
            encoding="utf-8",
        )

        # Real hub at wt/src/Models/
        dest_hub = wt / hub_subpath
        (dest_hub / ".millhouse").mkdir(parents=True)

        # Git repo on task branch so discover_active_worktrees detects this worktree.
        # branch_prefix includes trailing slash (standard convention, e.g. "feat/").
        branch_prefix = "feat/"
        real_local = {"repo": {"short_name": "RT"}, "spawn": {"branch_prefix": branch_prefix}}
        (dest_hub / ".millhouse" / "config.local.yaml").write_text(
            yaml.safe_dump(real_local),
            encoding="utf-8",
        )

        import subprocess as _sp
        _sp.run(["git", "init", str(wt)], capture_output=True)
        _sp.run(["git", "-C", str(wt), "config", "user.email", "t@t.com"], capture_output=True)
        _sp.run(["git", "-C", str(wt), "config", "user.name", "T"], capture_output=True)
        (wt / ".keep").write_text("", encoding="utf-8")
        _sp.run(["git", "-C", str(wt), "add", ".keep"], capture_output=True)
        _sp.run(["git", "-C", str(wt), "commit", "-m", "init"], capture_output=True)
        _sp.run(["git", "-C", str(wt), "checkout", "-b", f"{branch_prefix}{slug}"], capture_output=True)

        # Wiki config and Home.md (discover filters by home_tasks)
        wiki = tmpdir / "wiki"
        wiki.mkdir()
        (wiki / "config.yaml").write_text("junctions: {}\nhardlinks: {}\n", encoding="utf-8")
        (wiki / "mill-config.yaml").write_text("paths:\n  discussion_file: discussion.md\nspawn:\n  branch_prefix: \"\"\n", encoding="utf-8")
        (wiki / "Home.md").write_text(
            f"## RT Task\n[{slug}] [active]\n\n_body_\n", encoding="utf-8"
        )

        # Import real module implementations (scripts dir is on sys.path)
        # Temporarily clear any stubs injected by previous tests.
        _to_clear = ["_spawn_core", "_config", "_paths", "_yaml_writer",
                     "_sibling", "_subprocess_util"]
        _saved = {n: sys.modules.pop(n, None) for n in _to_clear}
        try:
            import _spawn_core as real_sc
            import _config as real_cfg_mod
            import _paths as real_paths_mod
            from wiki._parse import parse_home_md

            # 1. discover_active_worktrees with new signature
            home_tasks = parse_home_md((wiki / "Home.md").read_text(encoding="utf-8"))
            discovered = real_sc.discover_active_worktrees(worktrees, home_tasks, branch_prefix, cwd=wt)
            if len(discovered) != 1:
                raise AssertionError(
                    f"expected 1 discovered worktree, got {len(discovered)}: {discovered}"
                )
            _, found_slug, _ = discovered[0]
            if found_slug != slug:
                raise AssertionError(
                    f"discovered slug should be {slug!r}, got {found_slug!r}"
                )

            # 2. load_config merges stub + real config + wiki config
            merged = real_cfg_mod.load_config(wiki, wt)
            if merged.get("hub_relative_path") != hub_subpath:
                raise AssertionError(
                    f"hub_relative_path should be {hub_subpath!r} in merged cfg: {merged}"
                )
            if merged.get("repo", {}).get("short_name") != "RT":
                raise AssertionError(
                    f"operational key repo.short_name missing from merged cfg: {merged}"
                )

            # 3. resolve_hub_relative_path returns correct path
            resolved = real_paths_mod.resolve_hub_relative_path(wt, hub_subpath)
            expected = wt / hub_subpath
            if resolved != expected:
                raise AssertionError(
                    f"resolve_hub_relative_path({wt!r}, {hub_subpath!r}) should be "
                    f"{expected}, got {resolved}"
                )
        finally:
            # Restore whatever was in sys.modules before
            for name, orig in _saved.items():
                if orig is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = orig
    finally:
        _safe_rmtree.safe_rmtree(tmpdir, allowed_root=tmpdir, ignore_errors=True)

    print("PASS: test_spawn_discovery_round_trip_subfolder")


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
        test_create_hub_links_called_after_portal_creation,
        test_main_dry_run_prints_worktree_status_path,
        test_spawn_standard_layout_regression,
        test_spawn_subfolder_install_destination_layout,
        test_spawn_discovery_round_trip_subfolder,
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
