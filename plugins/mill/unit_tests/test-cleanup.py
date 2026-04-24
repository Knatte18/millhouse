"""Unit tests for build_plan() in plugins/mill/scripts/mill-cleanup.py."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

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

import _tasks_md  # noqa: E402


def _make_status_md(phase: str) -> str:
    return f"```yaml\nphase: {phase}\n```\n"


def _make_task(slug: str, phase_marker: str | None) -> _tasks_md.Task:
    return _tasks_md.Task(slug=slug, title="test", phase=phase_marker, has_proposal=False, heading_line_no=1)


def main() -> int:
    try:
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
            orphan_lines = [l for l in plan.to_report if "orphan worktree" in l and "ghost-slug" in l]
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
            orphan_lines = [l for l in plan.to_report if "orphan" in l and "ghost-slug" in l]
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
            orphan_lines = [l for l in plan.to_report if "orphan" in l and "no-home-slug" in l]
            assert len(orphan_lines) == 1, f"expected 1 orphan active_dir line, got {plan.to_report}"
            print("PASS build_plan — orphan active_dir (no Home.md entry) -> reported")

        print("All build_plan unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
