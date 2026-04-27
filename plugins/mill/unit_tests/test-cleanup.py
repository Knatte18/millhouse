"""Unit tests for build_plan() and in-place cleanup in mill-cleanup.py."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("mill_cleanup", SCRIPTS / "mill-cleanup.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["mill_cleanup"] = mod
spec.loader.exec_module(mod)
build_plan = mod.build_plan
CleanupPlan = mod.CleanupPlan
SlugRecord = mod.SlugRecord
apply_plan = mod.apply_plan
_resolve_inplace_mode = mod._resolve_inplace_mode

import _active  # noqa: E402
import _status  # noqa: E402
import _tasks_md  # noqa: E402


def _make_status_md(phase: str, parent: str = "main") -> str:
    return (
        "# Status\n\n"
        "```yaml\n"
        f"phase: {phase}\n"
        f"parent: {parent}\n"
        "task: test task\n"
        "task_description: |\n"
        "  test\n"
        "```\n\n"
        "## Timeline\n\n"
        "```text\n"
        f"{phase}  2026-01-01T00:00:00Z\n"
        "```\n"
    )


def _make_task(slug: str, phase_marker: str | None) -> _tasks_md.Task:
    return _tasks_md.Task(slug=slug, title="test", phase=phase_marker, has_proposal=False, heading_line_no=1)


def main() -> int:
    try:
        # --- read_parent_branch: missing file -> None ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            result = _status.read_parent_branch(tmp / "nonexistent.md")
            assert result is None, f"Expected None for missing file, got {result!r}"
            print("PASS read_parent_branch — missing file -> None")

        # --- read_parent_branch: absent parent: key -> None ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            no_parent_status = (
                "# Status\n\n"
                "```yaml\n"
                "phase: done\n"
                "task: test task\n"
                "task_description: |\n"
                "  test\n"
                "```\n\n"
                "## Timeline\n\n"
                "```text\n"
                "done  2026-01-01T00:00:00Z\n"
                "```\n"
            )
            status_path = tmp / "status.md"
            status_path.write_text(no_parent_status, encoding="utf-8")
            result = _status.read_parent_branch(status_path)
            assert result is None, f"Expected None for absent parent: key, got {result!r}"
            print("PASS read_parent_branch — absent parent: key -> None")

        # --- read_parent_branch: well-formed -> correct branch string ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            status_path = tmp / "status.md"
            status_path.write_text(_make_status_md("done", parent="main"), encoding="utf-8")
            result = _status.read_parent_branch(status_path)
            assert result == "main", f"Expected 'main', got {result!r}"
            print("PASS read_parent_branch — well-formed -> 'main'")

        # --- done slug with worktree and active_dir ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub = tmp / "hub"
            hub.mkdir()
            active_dir = tmp / "done-slug"
            active_dir.mkdir()
            (active_dir / "status.md").write_text(_make_status_md("done"), encoding="utf-8")
            worktrees = [
                {"path": str(hub), "branch": "main"},
                {"path": str(tmp / "worktrees" / "done-slug"), "branch": "impl/done-slug"},
            ]
            home_tasks = [_make_task("done-slug", "done")]
            plan = build_plan([active_dir], worktrees, home_tasks, tmp, hub_root=hub)
            assert len(plan.to_remove_done) == 1, f"expected 1 done, got {len(plan.to_remove_done)}"
            assert plan.to_remove_done[0].slug == "done-slug"
            assert plan.to_remove_done[0].branch == "impl/done-slug"
            assert plan.to_reset_home == [], f"expected empty to_reset_home, got {plan.to_reset_home}"
            assert plan.to_report == [], f"expected empty to_report, got {plan.to_report}"
            print("PASS build_plan — done slug with worktree -> to_remove_done")

        # --- abandoned slug with [active] marker ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub = tmp / "hub"
            hub.mkdir()
            active_dir = tmp / "abandoned-slug"
            active_dir.mkdir()
            (active_dir / "status.md").write_text(_make_status_md("abandoned"), encoding="utf-8")
            worktrees = [{"path": str(hub), "branch": "main"}]
            home_tasks = [_make_task("abandoned-slug", "active")]
            plan = build_plan([active_dir], worktrees, home_tasks, tmp, hub_root=hub)
            assert len(plan.to_remove_abandoned) == 1
            assert plan.to_reset_home == ["abandoned-slug"]
            assert plan.to_report == []
            print("PASS build_plan — abandoned slug + [active] marker -> to_remove_abandoned + to_reset_home")

        # --- abandoned slug with [done] marker (inconsistency) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub = tmp / "hub"
            hub.mkdir()
            active_dir = tmp / "bad-abandoned-slug"
            active_dir.mkdir()
            (active_dir / "status.md").write_text(_make_status_md("abandoned"), encoding="utf-8")
            worktrees = [{"path": str(hub), "branch": "main"}]
            home_tasks = [_make_task("bad-abandoned-slug", "done")]
            plan = build_plan([active_dir], worktrees, home_tasks, tmp, hub_root=hub)
            assert plan.to_remove_abandoned == []
            assert plan.to_reset_home == []
            assert len(plan.to_report) == 1
            assert "skipping" in plan.to_report[0].lower()
            print("PASS build_plan — abandoned + [done] marker -> inconsistency reported, not removed")

        # --- live slug (implementing) -> no action ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub = tmp / "hub"
            hub.mkdir()
            active_dir = tmp / "live-slug"
            active_dir.mkdir()
            (active_dir / "status.md").write_text(_make_status_md("implementing"), encoding="utf-8")
            worktrees = [{"path": str(hub), "branch": "main"}]
            home_tasks = [_make_task("live-slug", "active")]
            plan = build_plan([active_dir], worktrees, home_tasks, tmp, hub_root=hub)
            assert plan.to_remove_done == [] and plan.to_remove_abandoned == [] and plan.to_reset_home == []
            print("PASS build_plan — live phase (implementing) -> no action")

        # --- unreadable status.md (missing file) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub = tmp / "hub"
            hub.mkdir()
            active_dir = tmp / "bad-slug"
            active_dir.mkdir()
            # no status.md written
            worktrees = [{"path": str(hub), "branch": "main"}]
            home_tasks = [_make_task("bad-slug", None)]
            plan = build_plan([active_dir], worktrees, home_tasks, tmp, hub_root=hub)
            assert len(plan.to_report) == 1
            assert "bad-slug" in plan.to_report[0]
            assert "unreadable" in plan.to_report[0]
            print("PASS build_plan — missing status.md -> reported as unreadable, no action")

        # --- orphan worktree (worktree with no active_dir) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            worktrees = [
                {"path": str(hub_root), "branch": "main"},
                {"path": str(tmp / "worktrees" / "ghost-slug"), "branch": "impl/ghost-slug"},
            ]
            plan = build_plan([], worktrees, [], tmp, hub_root=hub_root)
            orphan_lines = [line for line in plan.to_report if "orphan worktree" in line and "ghost-slug" in line]
            assert len(orphan_lines) == 1, f"expected 1 orphan worktree line, got {plan.to_report}"
            print("PASS build_plan — orphan worktree -> reported")

        # --- orphan Home.md marker ([active] with no active_dir) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            home_tasks = [_make_task("ghost-slug", "active")]
            worktrees = [{"path": str(hub_root), "branch": "main"}]
            plan = build_plan([], worktrees, home_tasks, tmp, hub_root=hub_root)
            orphan_lines = [line for line in plan.to_report if "orphan" in line and "ghost-slug" in line]
            assert len(orphan_lines) == 1, f"expected 1 orphan marker line, got {plan.to_report}"
            print("PASS build_plan — orphan [active] Home.md marker -> reported")

        # --- orphan active_dir (active_dir with no Home.md entry) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            active_dir = tmp / "no-home-slug"
            active_dir.mkdir()
            (active_dir / "status.md").write_text(_make_status_md("implementing"), encoding="utf-8")
            worktrees = [{"path": str(hub_root), "branch": "main"}]
            plan = build_plan([active_dir], worktrees, [], tmp, hub_root=hub_root)
            orphan_lines = [line for line in plan.to_report if "orphan" in line and "no-home-slug" in line]
            assert len(orphan_lines) == 1, f"expected 1 orphan active_dir line, got {plan.to_report}"
            print("PASS build_plan — orphan active_dir (no Home.md entry) -> reported")

        # --- in-place cleanup: branch matches, no worktree dir -> branch delete, no worktree remove ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            mill_dir = hub_root / ".millhouse"
            mill_dir.mkdir()

            active_dir = tmp / "wiki" / "active" / "my-task"
            active_dir.mkdir(parents=True)
            (active_dir / "status.md").write_text(
                _make_status_md("done", parent="main"), encoding="utf-8"
            )

            # Write the active.slug.md marker.
            _active.write(
                mill_dir,
                slug="my-task",
                task_title="My task",
                branch="impl/my-task",
                spawned_at="2026-01-01T00:00:00Z",
            )

            record = SlugRecord(
                slug="my-task",
                worktree_path=None,
                branch="impl/my-task",
                active_dir=active_dir,
                home_marker="done",
            )

            run_calls: list = []

            def _fake_run(argv, **kwargs):
                run_calls.append(argv)
                result = MagicMock()
                result.returncode = 0
                result.stdout = "impl/my-task\n"
                result.stderr = ""
                return result

            # is_inplace: branch matches, no worktree dir → True → inplace mode.
            # _resolve_inplace_mode returns (mode, task_branch) tuple.
            with patch("mill_cleanup._subprocess_util.run", side_effect=_fake_run):
                with patch("mill_cleanup._resolve_inplace_mode", return_value=("inplace", "impl/my-task")):
                    with patch("mill_cleanup._junction.remove") as mock_junction_remove:
                        with patch("mill_cleanup._wiki.write_commit_push"):
                            with patch("mill_cleanup._sidebar.regenerate"):
                                wiki_path = tmp / "wiki"
                                wiki_path.mkdir(exist_ok=True)
                                (wiki_path / "Home.md").write_text("", encoding="utf-8")
                                plan = CleanupPlan(
                                    to_remove_done=[record],
                                    to_remove_abandoned=[],
                                    to_reset_home=[],
                                    to_report=[],
                                )
                                apply_plan(plan, wiki_path, hub_root, {})

            # Assert git worktree remove was NOT called.
            worktree_remove_calls = [
                c for c in run_calls if "worktree" in c and "remove" in c
            ]
            assert worktree_remove_calls == [], (
                f"Expected no 'git worktree remove' call, got: {worktree_remove_calls}"
            )
            # Assert git branch -d was called for done phase.
            branch_delete_calls = [
                c for c in run_calls if "branch" in c and ("-d" in c or "-D" in c)
            ]
            assert len(branch_delete_calls) == 1, (
                f"Expected exactly one branch delete call, got: {branch_delete_calls}"
            )
            assert "-d" in branch_delete_calls[0], (
                f"Expected '-d' (safe delete) for done phase, got: {branch_delete_calls[0]}"
            )
            # Assert .active junction removal was called with hub_root / ".active".
            junction_call_paths = [str(c.args[0]) for c in mock_junction_remove.call_args_list]
            expected_junction = str(hub_root / ".active")
            assert any(p == expected_junction for p in junction_call_paths), (
                f"Expected _junction.remove called with {expected_junction!r}, "
                f"got calls: {junction_call_paths}"
            )
            # Assert active.slug.md marker was deleted from the real filesystem.
            marker_path = hub_root / ".millhouse" / "active.slug.md"
            assert not marker_path.exists(), (
                f"Expected active.slug.md to be deleted after apply_plan, but it still exists: {marker_path}"
            )
            print("PASS apply_plan — in-place cleanup (done): no worktree remove, git branch -d called, junction removed, marker deleted")

        # --- stale-worktree-dir: worktree dir exists, user picks inplace -> in-place flow taken ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            mill_dir = hub_root / ".millhouse"
            mill_dir.mkdir()

            active_dir = tmp / "wiki" / "active" / "my-task"
            active_dir.mkdir(parents=True)
            (active_dir / "status.md").write_text(
                _make_status_md("abandoned", parent="main"), encoding="utf-8"
            )

            _active.write(
                mill_dir,
                slug="my-task",
                task_title="My task",
                branch="impl/my-task",
                spawned_at="2026-01-01T00:00:00Z",
            )

            # Pre-create the worktree dir to trigger stale-worktree edge.
            stale_dir = tmp / "worktrees" / "my-task"
            stale_dir.mkdir(parents=True)

            record = SlugRecord(
                slug="my-task",
                worktree_path=None,
                branch="impl/my-task",
                active_dir=active_dir,
                home_marker="active",
            )

            run_calls2: list = []

            def _fake_run2(argv, **kwargs):
                run_calls2.append(argv)
                result = MagicMock()
                result.returncode = 0
                result.stdout = "impl/my-task\n"
                result.stderr = ""
                return result

            # Stale-worktree prompt: mock prompt_stale_worktree to return "inplace"
            # so _resolve_inplace_mode's real branch-match + worktree-dir detection
            # runs end-to-end and calls the prompt as the plan specified.
            with patch("mill_cleanup._subprocess_util.run", side_effect=_fake_run2):
                with patch("mill_cleanup._inplace.prompt_stale_worktree", return_value="inplace") as mock_prompt:
                    with patch("mill_cleanup._junction.remove") as mock_junction_remove2:
                        with patch("mill_cleanup._wiki.write_commit_push"):
                            with patch("mill_cleanup._sidebar.regenerate"):
                                wiki_path = tmp / "wiki"
                                wiki_path.mkdir(exist_ok=True)
                                # Home.md must contain the task so set_phase can reset it.
                                # Format: ## Title / [slug] [phase]
                                (wiki_path / "Home.md").write_text(
                                    "## My task\n[my-task] [active]\n",
                                    encoding="utf-8",
                                )
                                plan = CleanupPlan(
                                    to_remove_done=[],
                                    to_remove_abandoned=[record],
                                    to_reset_home=["my-task"],
                                    to_report=[],
                                )
                                apply_plan(plan, wiki_path, hub_root, {})

            # Assert prompt_stale_worktree was actually called, proving the real
            # _resolve_inplace_mode detection path ran (not bypassed by a patch).
            assert mock_prompt.called, (
                "Expected _inplace.prompt_stale_worktree to be called by "
                "_resolve_inplace_mode's stale-worktree detection, but it was not."
            )

            # In-place mode was taken: no git worktree remove.
            worktree_remove_calls2 = [
                c for c in run_calls2 if "worktree" in c and "remove" in c
            ]
            assert worktree_remove_calls2 == [], (
                f"Expected no 'git worktree remove' after inplace choice, got: {worktree_remove_calls2}"
            )
            # git branch -D called for abandoned phase.
            branch_delete_calls2 = [
                c for c in run_calls2 if "branch" in c and ("-d" in c or "-D" in c)
            ]
            assert len(branch_delete_calls2) == 1, (
                f"Expected exactly one branch delete call, got: {branch_delete_calls2}"
            )
            assert "-D" in branch_delete_calls2[0], (
                f"Expected '-D' (force delete) for abandoned phase, got: {branch_delete_calls2[0]}"
            )
            # Assert .active junction removal was called with hub_root / ".active".
            junction_call_paths2 = [str(c.args[0]) for c in mock_junction_remove2.call_args_list]
            expected_junction2 = str(hub_root / ".active")
            assert any(p == expected_junction2 for p in junction_call_paths2), (
                f"Expected _junction.remove called with {expected_junction2!r}, "
                f"got calls: {junction_call_paths2}"
            )
            # Assert active.slug.md marker was deleted from the real filesystem.
            marker_path2 = hub_root / ".millhouse" / "active.slug.md"
            assert not marker_path2.exists(), (
                f"Expected active.slug.md to be deleted after apply_plan, but it still exists: {marker_path2}"
            )
            print("PASS apply_plan — stale-worktree-dir: inplace choice taken, no worktree remove, git branch -D called, junction removed, marker deleted")

        print("All build_plan unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
