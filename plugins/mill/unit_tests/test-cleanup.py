"""Unit tests for build_plan() and in-place cleanup in millpy-cleanup.py."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("mill_cleanup", SCRIPTS / "millpy-cleanup.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["mill_cleanup"] = mod
spec.loader.exec_module(mod)
build_plan = mod.build_plan
CleanupPlan = mod.CleanupPlan
SlugRecord = mod.SlugRecord
apply_plan = mod.apply_plan
_resolve_inplace_mode = mod._resolve_inplace_mode

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


def _mock_branch_run(branch: str):
    """Return a side_effect for _subprocess_util.run covering branch and tag calls in build_plan."""
    def _run(argv, **kwargs):
        r = MagicMock()
        r.returncode = 0
        r.stderr = ""
        if "--show-current" in argv:
            r.stdout = f"{branch}\n"
        elif "tag" in argv and "-l" in argv:
            r.stdout = "archive/slug\n"
        else:
            r.stdout = ""
        return r
    return _run


def _make_git_repo(path: Path) -> None:
    """Initialise a minimal git repo."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )


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

        # --- done slug with worktree (fresh layout, no wiki/active/<slug>/) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "done-slug"
            wt.mkdir(parents=True)
            (wt / "status.md").write_text(_make_status_md("done"), encoding="utf-8")

            home_tasks = [_make_task("done-slug", "done")]
            wiki_path = tmp / "wiki"
            wiki_path.mkdir()

            with patch("mill_cleanup._subprocess_util.run", side_effect=_mock_branch_run("impl/done-slug")):
                plan = build_plan([wt], home_tasks, wiki_path, hub_root=hub, branch_prefix="impl/")

            assert len(plan.to_remove_done) == 1, f"expected 1 done, got {len(plan.to_remove_done)}"
            assert plan.to_remove_done[0].slug == "done-slug"
            assert plan.to_remove_done[0].branch == "impl/done-slug"
            assert plan.to_remove_done[0].worktree_path == wt
            assert plan.to_remove_done[0].wiki_active_dir is None, (
                f"expected wiki_active_dir=None for fresh layout, got {plan.to_remove_done[0].wiki_active_dir}"
            )
            assert plan.to_reset_home == []
            assert plan.to_report == []
            print("PASS build_plan — done slug, fresh layout (no wiki/active/) -> to_remove_done, wiki_active_dir=None")

        # --- done slug with worktree AND legacy wiki/active/<slug>/ dir ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "done-slug"
            wt.mkdir(parents=True)
            (wt / "status.md").write_text(_make_status_md("done"), encoding="utf-8")

            # Create legacy wiki/active/<slug>/ dir
            wiki_path = tmp / "wiki"
            legacy_active = wiki_path / "active" / "done-slug"
            legacy_active.mkdir(parents=True)
            (legacy_active / "status.md").write_text(_make_status_md("done"), encoding="utf-8")

            home_tasks = [_make_task("done-slug", "done")]
            with patch("mill_cleanup._subprocess_util.run", side_effect=_mock_branch_run("impl/done-slug")):
                plan = build_plan([wt], home_tasks, wiki_path, hub_root=hub, branch_prefix="impl/")

            assert len(plan.to_remove_done) == 1
            assert plan.to_remove_done[0].wiki_active_dir == legacy_active, (
                f"expected wiki_active_dir={legacy_active}, got {plan.to_remove_done[0].wiki_active_dir}"
            )
            print("PASS build_plan — done slug, legacy layout (wiki/active/ present) -> wiki_active_dir set")

        # --- abandoned slug with [active] marker ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "abandoned-slug"
            wt.mkdir(parents=True)
            (wt / "status.md").write_text(_make_status_md("abandoned"), encoding="utf-8")

            home_tasks = [_make_task("abandoned-slug", "active")]
            wiki_path = tmp / "wiki"
            wiki_path.mkdir()
            with patch("mill_cleanup._subprocess_util.run", side_effect=_mock_branch_run("impl/abandoned-slug")):
                plan = build_plan([wt], home_tasks, wiki_path, hub_root=hub, branch_prefix="impl/")

            assert len(plan.to_remove_abandoned) == 1
            assert plan.to_reset_home == ["abandoned-slug"]
            assert plan.to_report == []
            print("PASS build_plan — abandoned slug + [active] marker -> to_remove_abandoned + to_reset_home")

        # --- abandoned slug with [done] marker (inconsistency) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "bad-abandoned-slug"
            wt.mkdir(parents=True)
            (wt / "status.md").write_text(_make_status_md("abandoned"), encoding="utf-8")

            home_tasks = [_make_task("bad-abandoned-slug", "done")]
            wiki_path = tmp / "wiki"
            wiki_path.mkdir()
            with patch("mill_cleanup._subprocess_util.run", side_effect=_mock_branch_run("impl/bad-abandoned-slug")):
                plan = build_plan([wt], home_tasks, wiki_path, hub_root=hub, branch_prefix="impl/")

            assert plan.to_remove_abandoned == []
            assert plan.to_reset_home == []
            assert len(plan.to_report) == 1
            assert "skipping" in plan.to_report[0].lower()
            print("PASS build_plan — abandoned + [done] marker -> inconsistency reported, not removed")

        # --- live slug (implementing) -> no action ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "live-slug"
            wt.mkdir(parents=True)
            (wt / "status.md").write_text(_make_status_md("implementing"), encoding="utf-8")

            home_tasks = [_make_task("live-slug", "active")]
            wiki_path = tmp / "wiki"
            wiki_path.mkdir()
            with patch("mill_cleanup._subprocess_util.run", side_effect=_mock_branch_run("impl/live-slug")):
                plan = build_plan([wt], home_tasks, wiki_path, hub_root=hub, branch_prefix="impl/")

            assert plan.to_remove_done == [] and plan.to_remove_abandoned == [] and plan.to_reset_home == []
            print("PASS build_plan — live phase (implementing) -> no action")

        # --- unreadable status.md (missing file) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "bad-slug"
            wt.mkdir(parents=True)
            # no status.md written

            home_tasks = [_make_task("bad-slug", None)]
            wiki_path = tmp / "wiki"
            wiki_path.mkdir()
            with patch("mill_cleanup._subprocess_util.run", side_effect=_mock_branch_run("impl/bad-slug")):
                plan = build_plan([wt], home_tasks, wiki_path, hub_root=hub, branch_prefix="impl/")

            assert len(plan.to_report) == 1
            assert "bad-slug" in plan.to_report[0]
            assert "unreadable" in plan.to_report[0]
            print("PASS build_plan — missing status.md -> reported as unreadable, no action")

        # --- orphan worktree (wts dir without active marker) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            container = tmp
            wts_dir = container / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            _make_git_repo(hub)
            # Ghost wts dir with no active marker
            ghost = wts_dir / "ghost-slug"
            ghost.mkdir()

            wiki_path = container / "wiki"
            wiki_path.mkdir()

            # resolve_container_path uses git; patch it so the test stays pure.
            with patch("mill_cleanup._paths.resolve_container_path", return_value=container):
                plan = build_plan([], [], wiki_path, hub_root=hub, container_path=container)

            orphan_lines = [line for line in plan.to_report if "orphan worktree" in line and "ghost-slug" in line]
            assert len(orphan_lines) == 1, f"expected 1 orphan worktree line, got {plan.to_report}"
            assert "git worktree remove --force" in orphan_lines[0]
            print("PASS build_plan — orphan worktree (no active marker) -> reported")

        # --- orphan Home.md marker ([active] with no active worktree) ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub = tmp / "hub"
            hub.mkdir()
            wiki_path = tmp / "wiki"
            wiki_path.mkdir()
            home_tasks = [_make_task("ghost-slug", "active")]
            plan = build_plan([], home_tasks, wiki_path, hub_root=hub)
            orphan_lines = [line for line in plan.to_report if "orphan" in line and "ghost-slug" in line]
            assert len(orphan_lines) == 1, f"expected 1 orphan marker line, got {plan.to_report}"
            print("PASS build_plan — orphan [active] Home.md marker -> reported")

        # --- orphan active worktree (task branch but no Home.md entry) ---
        # discover_active_worktrees skips worktrees not in Home.md, so build_plan
        # receives active_worktrees=[] and detects the dir via container_path wts scan.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "no-home-slug"
            wt.mkdir(parents=True)

            wiki_path = tmp / "wiki"
            wiki_path.mkdir()
            plan = build_plan([], [], wiki_path, hub_root=hub, container_path=tmp)
            orphan_lines = [line for line in plan.to_report if "orphan" in line and "no-home-slug" in line]
            assert len(orphan_lines) == 1, f"expected 1 orphan worktree line, got {plan.to_report}"
            print("PASS build_plan — orphan active worktree (no Home.md entry) -> reported via wts scan")

        # --- in-place cleanup: branch matches, no worktree dir -> branch delete, no worktree remove ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            mill_dir = hub_root / ".millhouse"
            mill_dir.mkdir()

            # Status.md lives at worktree root (hub root for in-place tasks).
            # worktree_path = hub_root for in-place.
            (hub_root / "status.md").write_text(
                _make_status_md("done", parent="main"), encoding="utf-8"
            )

            record = SlugRecord(
                slug="my-task",
                worktree_path=hub_root,
                branch="impl/my-task",
                wiki_active_dir=None,
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

            with patch("mill_cleanup._subprocess_util.run", side_effect=_fake_run):
                with patch("mill_cleanup._resolve_inplace_mode", return_value=("inplace", "impl/my-task")):
                    with patch("mill_cleanup._junction.remove") as mock_junction_remove:
                        with patch("mill_cleanup._wiki.write_commit_push"):
                            with patch("mill_cleanup._sidebar.regenerate"):
                                with patch("mill_cleanup._paths.resolve_container_path", return_value=tmp / "container"):
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

            worktree_remove_calls = [
                c for c in run_calls if "worktree" in c and "remove" in c
            ]
            assert worktree_remove_calls == [], (
                f"Expected no 'git worktree remove' call, got: {worktree_remove_calls}"
            )
            branch_delete_calls = [
                c for c in run_calls if "branch" in c and ("-d" in c or "-D" in c)
            ]
            assert len(branch_delete_calls) == 1, (
                f"Expected exactly one branch delete call, got: {branch_delete_calls}"
            )
            assert "-d" in branch_delete_calls[0], (
                f"Expected '-d' (safe delete) for done phase, got: {branch_delete_calls[0]}"
            )
            junction_call_paths = [str(c.args[0]) for c in mock_junction_remove.call_args_list]
            expected_junction = str(hub_root / ".active")
            assert any(p == expected_junction for p in junction_call_paths), (
                f"Expected _junction.remove called with {expected_junction!r}, "
                f"got calls: {junction_call_paths}"
            )
            print("PASS apply_plan — in-place cleanup (done): no worktree remove, git branch -d, junction removed")

        # --- apply_plan: portal entry removed for worktree record ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            container = tmp / "container"
            wts_dir = container / "wts"
            hub_root = wts_dir / "my-repo"
            hub_root.mkdir(parents=True)

            portal_dir = container / "portals"
            portal_dir.mkdir(parents=True)
            portal_entry = portal_dir / "my-task"
            portal_entry.mkdir()

            wt_path = wts_dir / "my-task"
            wt_path.mkdir(parents=True)

            record = SlugRecord(
                slug="my-task",
                worktree_path=wt_path,
                branch="impl/my-task",
                wiki_active_dir=None,
                home_marker="done",
            )

            junction_remove_calls: list = []

            def _fake_junction_remove(path: Path) -> None:
                junction_remove_calls.append(path)

            with patch("mill_cleanup._resolve_inplace_mode", return_value=("worktree", "")):
                with patch("mill_cleanup._worktree.remove"):
                    with patch("mill_cleanup._subprocess_util.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
                        with patch("mill_cleanup._junction.remove", side_effect=_fake_junction_remove):
                            with patch("mill_cleanup._wiki.write_commit_push"):
                                with patch("mill_cleanup._sidebar.regenerate"):
                                    with patch("mill_cleanup._paths.resolve_container_path", return_value=container):
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

            portal_removal = [p for p in junction_remove_calls if "portals" in str(p) and "my-task" in str(p)]
            assert len(portal_removal) == 1, (
                f"Expected portal entry removal, got junction_remove calls: {junction_remove_calls}"
            )
            assert portal_removal[0] == container / "portals" / "my-task", (
                f"Expected removal of {container / 'portals' / 'my-task'}, got {portal_removal[0]}"
            )
            print("PASS apply_plan — portal entry removed for worktree record")

        # --- apply_plan: fresh layout — no wiki/active/<slug>/, worktree NOT rmtree'd ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            wt_path = tmp / "wts" / "my-task"
            wt_path.mkdir(parents=True)

            record = SlugRecord(
                slug="my-task",
                worktree_path=wt_path,
                branch="impl/my-task",
                wiki_active_dir=None,
                home_marker="done",
            )

            rmtree_calls: list = []

            with patch("mill_cleanup._resolve_inplace_mode", return_value=("worktree", "")):
                with patch("mill_cleanup._worktree.remove"):
                    with patch("mill_cleanup._subprocess_util.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
                        with patch("mill_cleanup._junction.remove"):
                            with patch("mill_cleanup._wiki.write_commit_push"):
                                with patch("mill_cleanup._sidebar.regenerate"):
                                    with patch("mill_cleanup._paths.resolve_container_path", return_value=tmp):
                                        with patch("mill_cleanup.shutil.rmtree", side_effect=rmtree_calls.append):
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

            # No rmtree should have been called (fresh layout, no wiki_active_dir).
            assert rmtree_calls == [], (
                f"Expected no rmtree call for fresh layout, got: {rmtree_calls}"
            )
            # Worktree dir itself must not be rmtree'd — it's handled by _worktree.remove.
            assert not any(str(wt_path) in str(c) for c in rmtree_calls), (
                f"worktree_path must never be rmtree'd, got: {rmtree_calls}"
            )
            print("PASS apply_plan — fresh layout: no rmtree, worktree not directly deleted")

        # --- apply_plan: legacy layout — wiki/active/<slug>/ present, rmtree on it, NOT worktree ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            wt_path = tmp / "wts" / "my-task"
            wt_path.mkdir(parents=True)

            wiki_path = tmp / "wiki"
            legacy_active = wiki_path / "active" / "my-task"
            legacy_active.mkdir(parents=True)

            record = SlugRecord(
                slug="my-task",
                worktree_path=wt_path,
                branch="impl/my-task",
                wiki_active_dir=legacy_active,
                home_marker="done",
            )

            rmtree_calls = []

            with patch("mill_cleanup._resolve_inplace_mode", return_value=("worktree", "")):
                with patch("mill_cleanup._worktree.remove"):
                    with patch("mill_cleanup._subprocess_util.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
                        with patch("mill_cleanup._junction.remove"):
                            with patch("mill_cleanup._wiki.write_commit_push"):
                                with patch("mill_cleanup._sidebar.regenerate"):
                                    with patch("mill_cleanup._paths.resolve_container_path", return_value=tmp):
                                        with patch("mill_cleanup.shutil.rmtree", side_effect=rmtree_calls.append):
                                            (wiki_path / "Home.md").write_text("", encoding="utf-8")
                                            plan = CleanupPlan(
                                                to_remove_done=[record],
                                                to_remove_abandoned=[],
                                                to_reset_home=[],
                                                to_report=[],
                                            )
                                            apply_plan(plan, wiki_path, hub_root, {})

            assert len(rmtree_calls) == 1, f"Expected exactly 1 rmtree call, got: {rmtree_calls}"
            assert rmtree_calls[0] == legacy_active, (
                f"Expected rmtree on legacy_active={legacy_active}, got {rmtree_calls[0]}"
            )
            assert rmtree_calls[0] != wt_path, "worktree_path must NEVER be rmtree'd"
            print("PASS apply_plan — legacy layout: rmtree on wiki_active_dir, NOT on worktree_path")

        # --- stale-worktree-dir: worktree dir exists, user picks inplace -> in-place flow taken ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root = tmp / "hub"
            hub_root.mkdir()
            mill_dir = hub_root / ".millhouse"
            mill_dir.mkdir()

            # Status.md at worktree root (hub root for in-place).
            (hub_root / "status.md").write_text(
                _make_status_md("abandoned", parent="main"), encoding="utf-8"
            )

            # Pre-create the worktree dir to trigger stale-worktree edge.
            stale_dir = tmp / "my-task"
            stale_dir.mkdir(parents=True)

            record = SlugRecord(
                slug="my-task",
                worktree_path=hub_root,
                branch="impl/my-task",
                wiki_active_dir=None,
                home_marker="active",
            )

            run_calls2: list = []

            def _fake_run2(argv, **kwargs):
                run_calls2.append(argv)
                result = MagicMock()
                result.returncode = 0
                if "--git-common-dir" in argv:
                    result.stdout = f"{hub_root / '.git'}\n"
                else:
                    result.stdout = "impl/my-task\n"
                result.stderr = ""
                return result

            wiki_path = tmp / "wiki"
            wiki_path.mkdir(exist_ok=True)
            (wiki_path / "Home.md").write_text("## My task\n[my-task] [active]\n", encoding="utf-8")
            plan_stale = CleanupPlan(
                to_remove_done=[],
                to_remove_abandoned=[record],
                to_reset_home=["my-task"],
                to_report=[],
            )
            with (
                patch("mill_cleanup._subprocess_util.run", side_effect=_fake_run2),
                patch("mill_cleanup._marker.slug_from_branch", return_value="my-task"),
                patch("mill_cleanup._inplace.prompt_stale_worktree", return_value="inplace") as mock_prompt,
                patch("mill_cleanup._junction.remove") as mock_junction_remove2,
                patch("mill_cleanup._wiki.write_commit_push"),
                patch("mill_cleanup._sidebar.regenerate"),
                patch("mill_cleanup._paths.resolve_container_path", return_value=tmp / "container"),
            ):
                apply_plan(plan_stale, wiki_path, hub_root, {})

            assert mock_prompt.called, (
                "Expected _inplace.prompt_stale_worktree to be called by "
                "_resolve_inplace_mode's stale-worktree detection, but it was not."
            )

            worktree_remove_calls2 = [
                c for c in run_calls2 if "worktree" in c and "remove" in c
            ]
            assert worktree_remove_calls2 == [], (
                f"Expected no 'git worktree remove' after inplace choice, got: {worktree_remove_calls2}"
            )
            branch_delete_calls2 = [
                c for c in run_calls2 if "branch" in c and ("-d" in c or "-D" in c)
            ]
            assert len(branch_delete_calls2) == 1, (
                f"Expected exactly one branch delete call, got: {branch_delete_calls2}"
            )
            assert "-D" in branch_delete_calls2[0], (
                f"Expected '-D' (force delete) for abandoned phase, got: {branch_delete_calls2[0]}"
            )
            junction_call_paths2 = [str(c.args[0]) for c in mock_junction_remove2.call_args_list]
            expected_junction2 = str(hub_root / ".active")
            assert any(p == expected_junction2 for p in junction_call_paths2), (
                f"Expected _junction.remove called with {expected_junction2!r}, "
                f"got calls: {junction_call_paths2}"
            )
            print("PASS apply_plan — stale-worktree-dir: inplace choice taken, no worktree remove, git branch -D, junction removed")

        # --- test_build_plan_reads_task_status_md: task/status.md is the primary path ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "task-status-slug"
            wt.mkdir(parents=True)
            # Write status.md in task/ only — no root status.md
            task_dir = wt / "task"
            task_dir.mkdir()
            (task_dir / "status.md").write_text(_make_status_md("done"), encoding="utf-8")

            home_tasks = [_make_task("task-status-slug", "done")]
            wiki_path = tmp / "wiki"
            wiki_path.mkdir()

            with patch("mill_cleanup._subprocess_util.run",
                       side_effect=_mock_branch_run("impl/task-status-slug")):
                plan = build_plan([wt], home_tasks, wiki_path, hub_root=hub, branch_prefix="impl/")

            assert any(r.slug == "task-status-slug" for r in plan.to_remove_done), (
                f"expected task-status-slug in to_remove_done, got {plan.to_remove_done}"
            )
            assert not any("task-status-slug" in r for r in plan.to_report), (
                f"task-status-slug must not be in to_report, got {plan.to_report}"
            )
            print("PASS test_build_plan_reads_task_status_md — task/status.md primary path")

        # --- test_build_plan_falls_back_to_root_status_md: legacy layout fallback ---
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            wts_dir = tmp / "wts"
            hub = wts_dir / "my-repo"
            hub.mkdir(parents=True)
            wt = wts_dir / "legacy-status-slug"
            wt.mkdir(parents=True)
            # Write status.md at root only — legacy layout, no task/ dir
            (wt / "status.md").write_text(_make_status_md("done"), encoding="utf-8")

            home_tasks = [_make_task("legacy-status-slug", "done")]
            wiki_path = tmp / "wiki"
            wiki_path.mkdir()

            with patch("mill_cleanup._subprocess_util.run",
                       side_effect=_mock_branch_run("impl/legacy-status-slug")):
                plan = build_plan([wt], home_tasks, wiki_path, hub_root=hub, branch_prefix="impl/")

            assert any(r.slug == "legacy-status-slug" for r in plan.to_remove_done), (
                f"expected legacy-status-slug in to_remove_done, got {plan.to_remove_done}"
            )
            assert not any("legacy-status-slug" in r for r in plan.to_report), (
                f"legacy-status-slug must not be in to_report, got {plan.to_report}"
            )
            print("PASS test_build_plan_falls_back_to_root_status_md — legacy layout fallback")

        # --- test_apply_plan_removes_dangling_active_junction ---
        # Scenario A: os.path.lexists returns False -> _junction.remove NOT called for .active
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root_da = tmp / "hub"
            hub_root_da.mkdir()
            wiki_path_da = tmp / "wiki"
            wiki_path_da.mkdir()
            (wiki_path_da / "Home.md").write_text("", encoding="utf-8")
            plan_da = CleanupPlan(to_remove_done=[], to_remove_abandoned=[], to_reset_home=[], to_report=[])

            junction_remove_calls_a: list = []
            with patch("os.path.lexists", return_value=False):
                with patch("mill_cleanup._junction.remove", side_effect=junction_remove_calls_a.append):
                    apply_plan(plan_da, wiki_path_da, hub_root_da, {})

            active_link_a = hub_root_da / ".active"
            assert not any(p == active_link_a for p in junction_remove_calls_a), (
                f"Scenario A: expected no .active removal when lexists=False, got: {junction_remove_calls_a}"
            )
            print("PASS test_apply_plan_removes_dangling_active_junction — Scenario A: lexists=False, no removal")

        # Scenario B: os.path.lexists returns True, Path.is_dir returns False (dangling) -> removal
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root_db = tmp / "hub"
            hub_root_db.mkdir()
            wiki_path_db = tmp / "wiki"
            wiki_path_db.mkdir()
            (wiki_path_db / "Home.md").write_text("", encoding="utf-8")
            plan_db = CleanupPlan(to_remove_done=[], to_remove_abandoned=[], to_reset_home=[], to_report=[])

            junction_remove_calls_b: list = []
            with patch("os.path.lexists", return_value=True):
                with patch.object(Path, "is_dir", return_value=False):
                    with patch("mill_cleanup._junction.remove", side_effect=junction_remove_calls_b.append):
                        apply_plan(plan_db, wiki_path_db, hub_root_db, {})

            active_link_b = hub_root_db / ".active"
            assert any(p == active_link_b for p in junction_remove_calls_b), (
                f"Scenario B: expected .active removal when lexists=True and is_dir=False, got: {junction_remove_calls_b}"
            )
            print("PASS test_apply_plan_removes_dangling_active_junction — Scenario B: dangling junction removed")

        # --- test_apply_inplace_record_reads_task_status_md ---
        # task/status.md (done + parent=feature-branch) takes priority over
        # root status.md (abandoned + parent=stale-branch).
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            hub_root_ip = tmp / "hub"
            hub_root_ip.mkdir()

            # Write task/status.md with done + feature-branch
            task_dir_ip = hub_root_ip / "task"
            task_dir_ip.mkdir()
            (task_dir_ip / "status.md").write_text(
                _make_status_md("done", parent="feature-branch"), encoding="utf-8"
            )
            # Write root status.md as a stale decoy with different data
            (hub_root_ip / "status.md").write_text(
                _make_status_md("abandoned", parent="stale-branch"), encoding="utf-8"
            )

            record_ip = SlugRecord(
                slug="my-task",
                worktree_path=hub_root_ip,
                branch="impl/my-task",
                wiki_active_dir=None,
                home_marker="done",
            )

            git_calls_ip: list = []

            def _fake_run_ip(argv, **kwargs):
                git_calls_ip.append(argv)
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            with patch("mill_cleanup._subprocess_util.run", side_effect=_fake_run_ip):
                with patch("mill_cleanup._junction.remove"):
                    with patch("mill_cleanup._paths.resolve_container_path", return_value=tmp / "container"):
                        mod._apply_inplace_record(record_ip, hub_root_ip, task_branch="impl/my-task")

            # read_parent_branch must resolve to task/status.md (feature-branch, not stale-branch)
            checkout_calls_ip = [args for args in git_calls_ip if "checkout" in args]
            assert len(checkout_calls_ip) == 1, f"Expected one git checkout call, got: {checkout_calls_ip}"
            assert "feature-branch" in checkout_calls_ip[0], (
                f"Expected checkout of 'feature-branch' (task/status.md), got: {checkout_calls_ip[0]}"
            )

            # _read_phase must resolve to task/status.md (done -> -d, not abandoned -> -D)
            branch_calls_ip = [args for args in git_calls_ip if "branch" in args and ("-d" in args or "-D" in args)]
            assert len(branch_calls_ip) == 1, f"Expected one branch delete call, got: {branch_calls_ip}"
            assert "-d" in branch_calls_ip[0], (
                f"Expected '-d' (done from task/status.md), not '-D' (abandoned from root), got: {branch_calls_ip[0]}"
            )
            print("PASS test_apply_inplace_record_reads_task_status_md — read_parent_branch and _read_phase resolve to task/")

        print("All build_plan unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
