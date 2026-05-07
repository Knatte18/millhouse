"""Unit tests for plugins/mill/scripts/millpy-claim.py.

Verifies:
  - top-level import succeeds (smoke test)
  - main() dry-run with --slug exits 0 and prints expected lines
  - main() happy path calls claim_in_wiki, write_active_marker,
    write_initial_status, and recreate_active_junction in order
  - dirty-tree path with option 3 (Abort) exits 1
  - dirty-tree path with option 1 (Stash) invokes git stash
  - multi-select path skips claim_in_wiki and uses merged task
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

CLAIM_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-claim.py"


# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------


def _make_fake_task(slug: str = "my-task", title: str = "My Task") -> MagicMock:
    task = MagicMock()
    task.slug = slug
    task.title = title
    return task


def _make_ok_run(stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a fake CompletedProcess with returncode=0."""
    cp = MagicMock()
    cp.returncode = 0
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


def _load_claim_module(stub_map: dict) -> object:
    """
    Load millpy-claim.py with the given module stubs injected into sys.modules.

    Returns the loaded module object. Caller must restore sys.modules after
    use to avoid cross-test pollution.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("mill_claim_test_run", CLAIM_PATH)
    mod = importlib.util.module_from_spec(spec)
    saved: dict[str, object] = {}
    for name, stub in stub_map.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = stub
    spec.loader.exec_module(mod)
    return mod, saved


def _restore_modules(saved: dict) -> None:
    for name, original in saved.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _make_stub_map(
    *,
    spawn_core_mock: object | None = None,
    subprocess_mock: object | None = None,
) -> dict:
    """Build the sys.modules stub map for a mill-claim test run."""
    sc = spawn_core_mock or MagicMock()
    subprocess_stub = subprocess_mock or MagicMock(return_value=_make_ok_run())

    paths_mod = MagicMock()
    paths_mod.resolve_git_root = MagicMock(return_value=Path("/fake/repo"))
    paths_mod.resolve_wiki_path = MagicMock(return_value=Path("/fake/wiki"))
    paths_mod.resolve_container_path = MagicMock(return_value=Path("/fake/container"))
    paths_mod.resolve_main_worktree_root = MagicMock(return_value=Path("/fake/repo"))
    paths_mod.resolve_short_name = MagicMock(return_value="MI")
    paths_mod.resolve_hub_path = MagicMock(return_value=Path("/fake/repo/subdir"))

    tasks_md_mod = MagicMock()
    tasks_md_mod.parse.return_value = [_make_fake_task()]

    wiki_mod = MagicMock()
    wiki_mod.sync_pull.return_value = None

    config_mod = types.ModuleType("_config")
    config_mod.load_config = MagicMock(return_value={})

    return {
        "_spawn_core": sc,
        "_subprocess_util": subprocess_stub,
        "_tasks_md": tasks_md_mod,
        "_wiki": wiki_mod,
        "_paths": paths_mod,
        "_vscode": MagicMock(),
        "_junction": MagicMock(),
        "_config": config_mod,
        "_sibling": types.ModuleType("_sibling"),
    }


# ---------------------------------------------------------------------------
# Smoke import
# ---------------------------------------------------------------------------


def test_smoke_import() -> None:
    """millpy-claim.py must import without error."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("mill_claim_smoke", CLAIM_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not build module spec for millpy-claim.py")
    mod = importlib.util.module_from_spec(spec)

    stubs = ["_spawn_core", "_subprocess_util", "_tasks_md", "_wiki", "_paths",
             "_vscode", "_junction", "_config", "_sibling"]
    saved: dict[str, object] = {}
    for name in stubs:
        saved[name] = sys.modules.get(name)
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # _paths needs the symbols that mill-claim imports at module level.
    paths_mod = sys.modules["_paths"]
    paths_mod.resolve_git_root = MagicMock(return_value=Path("/fake/repo"))
    paths_mod.resolve_wiki_path = MagicMock(return_value=Path("/fake/wiki"))
    paths_mod.resolve_container_path = MagicMock(return_value=Path("/fake/container"))
    paths_mod.resolve_main_worktree_root = MagicMock(return_value=Path("/fake/repo"))
    paths_mod.resolve_short_name = MagicMock(return_value="MI")
    paths_mod.resolve_hub_path = MagicMock(return_value=Path("/fake/repo/subdir"))

    # _config needs load_config at module level.
    config_mod = sys.modules["_config"]
    config_mod.load_config = MagicMock(return_value={})

    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        raise AssertionError(f"millpy-claim.py failed to import: {exc}") from exc
    finally:
        _restore_modules(saved)

    if not hasattr(mod, "main"):
        raise AssertionError("mill-claim module must expose main()")
    print("PASS: millpy-claim.py imports cleanly")


# ---------------------------------------------------------------------------
# Dry-run with --slug exits 0 and prints expected lines
# ---------------------------------------------------------------------------


def test_main_dry_run_exits_zero() -> None:
    """main(['--slug', 'foo', '--dry-run']) prints DryRun lines and exits 0."""
    task = _make_fake_task(slug="foo", title="Foo Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])

    stub_map = _make_stub_map(spawn_core_mock=sc)
    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        captured: list[str] = []
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
            patch("builtins.print", side_effect=lambda *a, **kw: captured.append(str(a[0]) if a else "")),
        ):
            exit_code = mod.main(["--slug", "foo", "--dry-run"])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0 for dry-run, got {exit_code}")
    dry_run_lines = [line for line in captured if "[DryRun]" in line]
    if len(dry_run_lines) < 4:
        raise AssertionError(f"expected at least 4 [DryRun] lines, got: {captured}")
    print("PASS: main() dry-run with --slug exits 0 and prints expected lines")


# ---------------------------------------------------------------------------
# Happy path: claim_in_wiki, write_active_marker, write_initial_status,
# recreate_active_junction all called
# ---------------------------------------------------------------------------


def test_main_happy_path_calls_spawn_core_helpers() -> None:
    """main() calls all _spawn_core helpers in order on the happy path."""
    task = _make_fake_task(slug="my-task", title="My Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])
    sc.claim_in_wiki.return_value = None
    sc.capture_parent_branch.return_value = "main"
    sc.write_active_marker.return_value = None
    sc.write_initial_status.return_value = Path("/fake/repo/subdir/task/status.md")
    sc.recreate_active_junction.return_value = None

    # subprocess: git checkout -b returns success
    subprocess_stub = MagicMock()
    subprocess_stub.run.return_value = _make_ok_run()

    stub_map = _make_stub_map(spawn_core_mock=sc, subprocess_mock=subprocess_stub)
    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=False),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
        ):
            exit_code = mod.main(["--slug", "my-task"])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0 on happy path, got {exit_code}")

    sc.claim_in_wiki.assert_called_once()
    sc.capture_parent_branch.assert_called_once()
    sc.write_active_marker.assert_called_once()
    sc.write_initial_status.assert_called_once()
    sc.recreate_active_junction.assert_called_once()

    # Verify new signature: (slug, hub_root, container_path)
    rac_call = sc.recreate_active_junction.call_args
    expected_hub_root = Path("/fake/repo/subdir")
    expected_container = Path("/fake/container")
    if rac_call.args[0] != "my-task":
        raise AssertionError(f"recreate_active_junction slug mismatch: {rac_call}")
    if rac_call.args[1] != expected_hub_root:
        raise AssertionError(f"recreate_active_junction hub_root mismatch: {rac_call}")
    if rac_call.args[2] != expected_container:
        raise AssertionError(f"recreate_active_junction container_path mismatch: {rac_call}")

    marker_call = sc.write_active_marker.call_args
    if marker_call.kwargs.get("slug") != "my-task":
        raise AssertionError(f"write_active_marker slug mismatch: {marker_call}")

    status_call = sc.write_initial_status.call_args
    if status_call.kwargs.get("slug") != "my-task":
        raise AssertionError(f"write_initial_status slug mismatch: {status_call}")
    if status_call.kwargs.get("parent_branch") != "main":
        raise AssertionError(f"write_initial_status parent_branch mismatch: {status_call}")
    if status_call.kwargs.get("branch") != "my-task":
        raise AssertionError(f"write_initial_status branch mismatch: {status_call}")
    if "wiki_path" in status_call.kwargs:
        raise AssertionError(f"write_initial_status must not use wiki_path= kwarg: {status_call}")
    if status_call.kwargs.get("worktree_path") != Path("/fake/repo/subdir"):
        raise AssertionError(f"write_initial_status worktree_path should be hub path /fake/repo/subdir: {status_call}")

    # Verify git checkout -b was invoked via subprocess
    run_calls = subprocess_stub.run.call_args_list
    checkout_calls = [c for c in run_calls if "checkout" in c.args[0]]
    if not checkout_calls:
        raise AssertionError("expected git checkout -b call via _subprocess_util.run")

    print("PASS: main() happy path calls all _spawn_core helpers in order")


# ---------------------------------------------------------------------------
# Dirty-tree abort (option 3) exits 1
# ---------------------------------------------------------------------------


def test_main_dirty_tree_abort_exits_one() -> None:
    """Dirty tree with option 3 (Abort) causes main() to exit 1."""
    task = _make_fake_task(slug="my-task", title="My Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])
    sc.claim_in_wiki.return_value = None
    sc.capture_parent_branch.return_value = "main"

    stub_map = _make_stub_map(spawn_core_mock=sc)
    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=True),
            # _prompt_dirty_tree raises SystemExit(1) for Abort
            patch.object(mod, "_prompt_dirty_tree", side_effect=SystemExit(1)),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
        ):
            try:
                exit_code = mod.main(["--slug", "my-task"])
            except SystemExit as exc:
                exit_code = exc.code
    finally:
        _restore_modules(saved)

    if exit_code != 1:
        raise AssertionError(f"expected exit 1 on abort, got {exit_code!r}")
    print("PASS: dirty-tree abort (option 3) exits 1")


# ---------------------------------------------------------------------------
# Dirty-tree stash (option 1) invokes git stash push
# ---------------------------------------------------------------------------


def test_main_dirty_tree_stash_invokes_git_stash() -> None:
    """Dirty tree with option 1 (Stash) calls git stash push before checkout."""
    task = _make_fake_task(slug="my-task", title="My Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])
    sc.claim_in_wiki.return_value = None
    sc.capture_parent_branch.return_value = "main"
    sc.write_active_marker.return_value = None
    sc.write_initial_status.return_value = Path("/fake/repo/subdir/task/status.md")
    sc.recreate_active_junction.return_value = None

    subprocess_stub = MagicMock()
    subprocess_stub.run.return_value = _make_ok_run()

    stub_map = _make_stub_map(spawn_core_mock=sc, subprocess_mock=subprocess_stub)
    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=True),
            patch.object(mod, "_prompt_dirty_tree", return_value=1),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
        ):
            exit_code = mod.main(["--slug", "my-task"])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0 for stash path, got {exit_code}")

    run_calls = subprocess_stub.run.call_args_list
    stash_push_calls = [
        c for c in run_calls
        if "stash" in c.args[0] and "push" in c.args[0]
    ]
    if not stash_push_calls:
        raise AssertionError("expected git stash push call via _subprocess_util.run")

    stash_pop_calls = [
        c for c in run_calls
        if "stash" in c.args[0] and "pop" in c.args[0]
    ]
    if not stash_pop_calls:
        raise AssertionError("expected git stash pop call via _subprocess_util.run")

    print("PASS: dirty-tree stash (option 1) invokes git stash push and pop")


# ---------------------------------------------------------------------------
# Multi-select path: claim_in_wiki skipped; merged task used for rest of flow
# ---------------------------------------------------------------------------


def test_main_multi_path_skips_claim_in_wiki() -> None:
    """Multi mode uses the merged task from multi_select_groom_then_claim and
    skips the standard claim_in_wiki call."""
    task_a = _make_fake_task(slug="task-a", title="Task A")
    task_b = _make_fake_task(slug="task-b", title="Task B")
    merged_task = _make_fake_task(slug="merged-task", title="Merged Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    # pick returns multi mode with two source tasks
    sc.pick_task_single_or_multi.return_value = ("multi", [task_a, task_b], [])
    sc.prompt_merged_entry.return_value = (
        "Merged Task", "merged-task",
        "Merged body.", False, None,
    )
    sc.multi_select_groom_then_claim.return_value = merged_task
    sc.capture_parent_branch.return_value = "main"
    sc.write_active_marker.return_value = None
    sc.write_initial_status.return_value = Path("/fake/repo/subdir/task/status.md")
    sc.recreate_active_junction.return_value = None

    subprocess_stub = MagicMock()
    subprocess_stub.run.return_value = _make_ok_run()

    stub_map = _make_stub_map(spawn_core_mock=sc, subprocess_mock=subprocess_stub)
    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=False),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
        ):
            exit_code = mod.main([])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0 for multi path, got {exit_code}")

    # Multi mode must NOT call claim_in_wiki (already claimed in groom_then_claim)
    sc.claim_in_wiki.assert_not_called()
    # Must call groom_then_claim with the two source slugs
    sc.multi_select_groom_then_claim.assert_called_once()
    groom_call = sc.multi_select_groom_then_claim.call_args
    source_slugs_arg = groom_call.args[1] if len(groom_call.args) > 1 else groom_call.kwargs.get("source_slugs")
    if set(source_slugs_arg) != {"task-a", "task-b"}:
        raise AssertionError(f"unexpected source_slugs: {source_slugs_arg!r}")
    # write_active_marker and write_initial_status use the merged task's slug
    sc.write_active_marker.assert_called_once()
    marker_call = sc.write_active_marker.call_args
    if marker_call.kwargs.get("slug") != "merged-task":
        raise AssertionError(f"write_active_marker slug should be merged-task: {marker_call}")
    print("PASS: multi-select path skips claim_in_wiki and uses merged task")


# ---------------------------------------------------------------------------
# Portal entry lands under resolve_container_path(), not git_root.parent
# ---------------------------------------------------------------------------


def test_portal_entry_uses_resolve_container_path() -> None:
    """Portal entry link_path must be under container_path/portals, not git_root.parent."""
    task = _make_fake_task(slug="my-task", title="My Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])
    sc.claim_in_wiki.return_value = None
    sc.capture_parent_branch.return_value = "main"
    sc.write_active_marker.return_value = None
    sc.write_initial_status.return_value = Path("/fake/repo/subdir/task/status.md")
    sc.recreate_active_junction.return_value = None

    subprocess_stub = MagicMock()
    subprocess_stub.run.return_value = _make_ok_run()

    stub_map = _make_stub_map(spawn_core_mock=sc, subprocess_mock=subprocess_stub)
    # container_path (/fake/container) is different from git_root.parent (/fake)
    # to distinguish a correct call from an accidental git_root.parent usage.
    junction_mock = stub_map["_junction"]
    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=False),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_symlink", return_value=False),
            patch.object(Path, "read_text", return_value="# Home\n"),
            patch.object(Path, "mkdir", return_value=None),
        ):
            exit_code = mod.main(["--slug", "my-task"])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0, got {exit_code}")

    create_calls = junction_mock.create.call_args_list
    if not create_calls:
        raise AssertionError("_junction.create was never called")

    portal_call = create_calls[0]
    link_path_arg = portal_call.kwargs.get("link_path") or portal_call.args[1]
    expected_portal_dir = Path("/fake/container") / "portals"
    # Must be under /fake/container/portals, NOT under /fake/portals (git_root.parent)
    if not str(link_path_arg).startswith(str(expected_portal_dir)):
        raise AssertionError(
            f"portal entry link_path {link_path_arg!r} should be under "
            f"{expected_portal_dir!r} (resolve_container_path output), "
            f"not under git_root.parent ({Path('/fake/portals')!r})"
        )
    print("PASS: portal entry link_path uses resolve_container_path, not git_root.parent")


# ---------------------------------------------------------------------------
# Call order: portal entry created before recreate_active_junction
# ---------------------------------------------------------------------------


def test_portal_before_recreate_active_junction_order() -> None:
    """_junction.create (portal entry) must fire before recreate_active_junction."""
    task = _make_fake_task(slug="my-task", title="My Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])
    sc.claim_in_wiki.return_value = None
    sc.capture_parent_branch.return_value = "main"
    sc.write_active_marker.return_value = None
    sc.write_initial_status.return_value = Path("/fake/repo/subdir/task/status.md")

    call_log: list[str] = []
    sc.recreate_active_junction.side_effect = lambda *a, **kw: call_log.append("recreate_active_junction")

    subprocess_stub = MagicMock()
    subprocess_stub.run.return_value = _make_ok_run()

    stub_map = _make_stub_map(spawn_core_mock=sc, subprocess_mock=subprocess_stub)
    junction_mock = stub_map["_junction"]
    junction_mock.create.side_effect = lambda *a, **kw: call_log.append("junction.create")

    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=False),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_symlink", return_value=False),
            patch.object(Path, "read_text", return_value="# Home\n"),
            patch.object(Path, "mkdir", return_value=None),
        ):
            exit_code = mod.main(["--slug", "my-task"])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0, got {exit_code}")

    if "junction.create" not in call_log:
        raise AssertionError("_junction.create was never called")
    if "recreate_active_junction" not in call_log:
        raise AssertionError("recreate_active_junction was never called")
    create_idx = call_log.index("junction.create")
    rac_idx = call_log.index("recreate_active_junction")
    if create_idx >= rac_idx:
        raise AssertionError(
            f"junction.create (pos {create_idx}) must fire BEFORE recreate_active_junction "
            f"(pos {rac_idx}), got order: {call_log}"
        )
    print("PASS: portal entry _junction.create fires before recreate_active_junction")


# ---------------------------------------------------------------------------
# Idempotent re-claim: portal exists + same target → skip, no second create
# ---------------------------------------------------------------------------


def test_portal_idempotent_when_already_correct() -> None:
    """Re-claiming the same slug when portal already points at the correct
    worktree must not call _junction.create and must exit 0."""
    task = _make_fake_task(slug="my-task", title="My Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])
    sc.claim_in_wiki.return_value = None
    sc.capture_parent_branch.return_value = "main"
    sc.write_active_marker.return_value = None
    sc.write_initial_status.return_value = Path("/fake/repo/subdir/task/status.md")
    sc.recreate_active_junction.return_value = None

    subprocess_stub = MagicMock()
    subprocess_stub.run.return_value = _make_ok_run()

    stub_map = _make_stub_map(spawn_core_mock=sc, subprocess_mock=subprocess_stub)
    junction_mock = stub_map["_junction"]

    # Simulate portal_link already existing and pointing at the same target.
    # os.path.realpath returns the same string for both portal_link and main_root.
    same_target = "/fake/repo"

    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        import unittest.mock as _um
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=False),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_symlink", return_value=False),
            patch.object(Path, "read_text", return_value="# Home\n"),
            patch.object(Path, "mkdir", return_value=None),
            _um.patch("os.path.realpath", return_value=same_target),
        ):
            exit_code = mod.main(["--slug", "my-task"])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0 for idempotent re-claim, got {exit_code}")

    # _junction.create must NOT be called (portal already correct).
    junction_mock.create.assert_not_called()
    # _junction.remove must NOT be called either.
    junction_mock.remove.assert_not_called()
    print("PASS: idempotent re-claim skips _junction.create when portal already correct")


# ---------------------------------------------------------------------------
# Hub-title flip: when settings.json has green background, title is updated
# ---------------------------------------------------------------------------


def test_main_hub_title_flip_when_cwd_is_hub() -> None:
    """When .vscode/settings.json has the hub green, mill-claim flips the title."""
    task = _make_fake_task(slug="my-task", title="My Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])
    sc.claim_in_wiki.return_value = None
    sc.capture_parent_branch.return_value = "main"
    sc.write_active_marker.return_value = None
    sc.write_initial_status.return_value = Path("/fake/repo/subdir/task/status.md")
    sc.recreate_active_junction.return_value = None

    subprocess_stub = MagicMock()
    subprocess_stub.run.return_value = _make_ok_run()

    vscode_mock = MagicMock()

    stub_map = _make_stub_map(spawn_core_mock=sc, subprocess_mock=subprocess_stub)
    stub_map["_vscode"] = vscode_mock

    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        green_settings = '{"workbench.colorCustomizations": {"titleBar.activeBackground": "#2d7d46"}, "window.title": "MH"}'
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=False),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value=green_settings),
        ):
            exit_code = mod.main(["--slug", "my-task"])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0, got {exit_code}")

    ws_calls = vscode_mock.write_settings.call_args_list
    if not ws_calls:
        raise AssertionError("_vscode.write_settings was not called — hub title not updated")
    ws_call = ws_calls[0]
    if ws_call.kwargs.get("slug") != "my-task":
        raise AssertionError(f"write_settings slug mismatch: {ws_call}")
    if ws_call.kwargs.get("color_hex") != "#2d7d46":
        raise AssertionError(f"write_settings color_hex should stay green: {ws_call}")
    if "window_title" in ws_call.kwargs:
        raise AssertionError(f"write_settings must not use window_title=: {ws_call}")
    print("PASS: mill-claim flips hub .vscode/settings.json title when cwd is the hub")


# ---------------------------------------------------------------------------
# cwd != git_root: hub paths resolve to cwd, not git-root
# ---------------------------------------------------------------------------


def test_hub_paths_use_cwd_not_git_root() -> None:
    """When cwd != git_root, .vscode/settings.json and mill_dir target cwd, not git_root."""
    task = _make_fake_task(slug="my-task", title="My Task")

    sc = MagicMock()
    sc.BacklogEmpty = type("BacklogEmpty", (Exception,), {})
    sc.pick_task_single_or_multi.return_value = ("single", task, [])
    sc.claim_in_wiki.return_value = None
    sc.capture_parent_branch.return_value = "main"
    sc.write_active_marker.return_value = None
    sc.write_initial_status.return_value = Path("/fake/repo/src/Models/task/status.md")
    sc.recreate_active_junction.return_value = None

    subprocess_stub = MagicMock()
    subprocess_stub.run.return_value = _make_ok_run()

    stub_map = _make_stub_map(spawn_core_mock=sc, subprocess_mock=subprocess_stub)
    # Simulate cwd being a subdirectory of the git repo.
    hub_path = Path("/fake/repo/src/Models")
    stub_map["_paths"].resolve_git_root = MagicMock(return_value=Path("/fake/repo"))
    stub_map["_paths"].resolve_hub_path = MagicMock(return_value=hub_path)

    mod, saved = _load_claim_module(stub_map)
    try:
        fake_cfg = {"spawn": {"branch_prefix": ""}}
        with (
            patch.object(mod, "_load_config", return_value=fake_cfg),
            patch.object(mod, "_is_dirty", return_value=False),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="# Home\n"),
        ):
            exit_code = mod.main(["--slug", "my-task"])
    finally:
        _restore_modules(saved)

    if exit_code != 0:
        raise AssertionError(f"expected exit 0, got {exit_code}")

    # write_initial_status must use the hub path (cwd), not the git_root.
    status_call = sc.write_initial_status.call_args
    if status_call.kwargs.get("worktree_path") != hub_path:
        raise AssertionError(
            f"write_initial_status worktree_path should be hub path {hub_path}, "
            f"not git_root: {status_call}"
        )

    # write_active_marker's mill_dir arg must be hub_path / ".millhouse".
    marker_call = sc.write_active_marker.call_args
    expected_mill_dir = hub_path / ".millhouse"
    if marker_call.args[0] != expected_mill_dir:
        raise AssertionError(
            f"write_active_marker mill_dir should be {expected_mill_dir}, got: {marker_call}"
        )

    print("PASS: hub paths (.vscode, .millhouse) resolve from cwd, not git_root")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_smoke_import,
        test_main_dry_run_exits_zero,
        test_main_happy_path_calls_spawn_core_helpers,
        test_main_dirty_tree_abort_exits_one,
        test_main_dirty_tree_stash_invokes_git_stash,
        test_main_multi_path_skips_claim_in_wiki,
        test_portal_entry_uses_resolve_container_path,
        test_portal_before_recreate_active_junction_order,
        test_portal_idempotent_when_already_correct,
        test_main_hub_title_flip_when_cwd_is_hub,
        test_hub_paths_use_cwd_not_git_root,
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
    print(f"All {len(tests)} mill-claim unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
