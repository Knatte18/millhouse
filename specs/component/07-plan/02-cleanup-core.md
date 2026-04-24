# Batch: cleanup-core

```yaml
task: mill-cleanup script
batch: cleanup-core
cards: 2
verify: python plugins/mill/unit_tests/test-cleanup.py
depends-on: [foundation]
```

## Batch Scope

Create `plugins/mill/scripts/mill-cleanup.py` — the full sweeper CLI. The script separates `build_plan()` (side-effect-free w.r.t. git and wiki writes; reads status.md files via `_read_phase`) from the impure `apply_plan()` executor. Add `plugins/mill/unit_tests/test-cleanup.py` that exercises `build_plan` with tempfile fixtures covering all phase and orphan combinations.

## Cards

### Card 3: `plugins/mill/scripts/mill-cleanup.py`

- **Reads:** `plugins/mill/scripts/_worktree.py` (list_worktrees, remove — post-batch-01), `plugins/mill/scripts/_wiki.py` (sync_pull, acquire_lock, release_lock, write_commit_push, read_junctions), `plugins/mill/scripts/_junction.py` (remove, resolve_target, has_slug_token), `plugins/mill/scripts/_sidebar.py` (regenerate), `plugins/mill/scripts/_tasks_md.py` (Task dataclass, parse, set_phase), `plugins/mill/scripts/_paths.py` (resolve_git_root, resolve_wiki_path), `plugins/mill/scripts/_subprocess_util.py`, `plugins/mill/scripts/mill-spawn.py` (argparse + main pattern reference).
- **Modifies:** (none)
- **Creates:** `plugins/mill/scripts/mill-cleanup.py`
- **Requirements:**
  - Module docstring: brief description — "Sweeper: reconcile hub git worktrees, wiki active/<slug>/ dirs, and Home.md markers based on status.md phase. Runs from the hub. Pass --apply to execute removals; default is dry-run."
  - **Imports:** `argparse`, `dataclasses`, `importlib`, `shutil`, `sys`, `pathlib.Path`, `yaml`, `_junction`, `_paths`, `_sidebar`, `_subprocess_util`, `_tasks_md`, `_wiki`, `_worktree`.
  - **Dataclasses** (at module level, after imports):
    ```python
    @dataclass(frozen=True)
    class SlugRecord:
        slug: str
        worktree_path: Path | None   # abs path of matching worktree, or None
        branch: str | None           # short branch name, or None
        active_dir: Path | None      # wiki/active/<slug>/ path, or None
        home_marker: str | None      # "active", "done", "s", None, etc.

    @dataclass(frozen=True)
    class CleanupPlan:
        to_remove_done: list[SlugRecord]      # done-phase slugs with residual artefacts
        to_remove_abandoned: list[SlugRecord] # abandoned-phase slugs with [active] marker
        to_reset_home: list[str]              # slugs whose Home.md [active] must be cleared
        to_report: list[str]                  # human-readable lines for orphans + unreadable
    ```
  - **`def _read_phase(status_path: Path) -> str | None:`**
    - Opens `status_path`, finds the first `` ```yaml `` fence, reads content until the closing ` ``` `, `yaml.safe_load`s it, returns `cfg.get("phase")`. Returns `None` on any exception (`FileNotFoundError`, `yaml.YAMLError`, `AttributeError`, etc.). No docstring — inline comment: `# Returns None if status.md is missing or phase: is unreadable.`
  - **`def build_plan(active_dirs: list[Path], worktrees: list[dict], home_tasks: list[Task], wiki_path: Path, hub_root: Path) -> CleanupPlan:`**
    - Side-effect-free w.r.t. git and wiki writes: no subprocess calls, no mutations. Reads `status.md` files via `_read_phase` (file I/O) — unit tests compensate with `tempfile` fixtures.
    - Build lookup maps:
      - `wt_by_slug: dict[str, dict]` — `{Path(w["path"]).name: w for w in worktrees}` (path basename = slug).
      - `marker_by_slug: dict[str, str | None]` — `{t.slug: t.phase for t in home_tasks}`.
      - `active_dir_by_slug: dict[str, Path]` — `{d.name: d for d in active_dirs if d.is_dir()}`.
      - `all_active_slugs = set(active_dir_by_slug)`.
    - Initialise result lists (mutable during build, frozen at return).
    - **Main loop** over `active_dir_by_slug.items()`:
      - Read `phase = _read_phase(active_dir / "status.md")`.
      - If `phase is None`: append `f"{slug} — status.md unreadable, skipping (inspect manually)"` to `to_report`. Continue.
      - Build record:
        ```python
        wt = wt_by_slug.get(slug)
        wt_path = Path(wt["path"]) if wt else None
        branch = wt["branch"] if wt else None
        record = SlugRecord(slug, wt_path, branch, active_dir, marker_by_slug.get(slug))
        ```
      - Decision table:
        - `phase == "done"` AND (`record.worktree_path` is not None OR `record.active_dir` is not None) → `to_remove_done.append(record)`.
        - `phase == "abandoned"` AND `record.home_marker == "active"` → `to_remove_abandoned.append(record); to_reset_home.append(slug)`.
        - `phase == "abandoned"` AND `record.home_marker != "active"` → append: `f"{slug} — phase=abandoned but Home.md marker is {record.home_marker!r}, not [active]; skipping (inspect manually)"` to `to_report`.
        - `phase` in `{"discussing","discussed","planning","planned","implementing","reviewing","fixing","blocked"}` → no action (live phase).
        - Any other phase string → append `f"{slug} — unknown phase {phase!r}, skipping"` to `to_report`.
    - **Orphan worktrees** — worktrees where the path basename is not in `all_active_slugs` and the path is not the hub itself:
      - For each `w` in `worktrees` where `Path(w["path"]) != hub_root` and `Path(w["path"]).name` not in `all_active_slugs`: append `f"orphan worktree: {w['path']} (no matching active/<slug>/ dir)"` to `to_report`.
    - **Orphan home markers** — `[active]` in home_tasks with no matching active_dir:
      - For each `task` in `home_tasks` where `task.phase == "active"` and `task.slug` not in `all_active_slugs`: append `f"orphan Home.md marker: {task.slug} is [active] but has no active/{task.slug}/ directory"` to `to_report`.
    - **Orphan active dirs** — active_dir slug not in `marker_by_slug` at all (no Home.md entry):
      - For each `slug` in `all_active_slugs` where `slug` not in `marker_by_slug`: append `f"orphan active dir: active/{slug}/ exists but no Home.md entry"` to `to_report`.
    - Return `CleanupPlan(to_remove_done, to_remove_abandoned, to_reset_home, to_report)`.
  - **`def _print_plan(plan: CleanupPlan) -> None:`**
    - Prints to stdout. If all lists empty: print "Nothing to do."
    - For each `r` in `to_remove_done`: `print(f"REMOVE (done):      {r.slug}  [worktree={r.worktree_path}, branch={r.branch}, active_dir={r.active_dir}]")`.
    - For each `r` in `to_remove_abandoned`: `print(f"REMOVE (abandoned): {r.slug}  [worktree={r.worktree_path}, branch={r.branch}, active_dir={r.active_dir}]  → Home.md marker reset to unclaimed")`.
    - For each line in `to_report`: `print(f"REPORT: {line}")`.
  - **`def apply_plan(plan: CleanupPlan, wiki_path: Path, hub_root: Path, junctions_cfg: dict[str, str]) -> None:`**
    - Executor — performs all side effects. Called only when `--apply` is passed.
    - `wiki_relative_paths: list[str] = []` — accumulates paths for `write_commit_push`.
    - **Remove loop** over `plan.to_remove_done + plan.to_remove_abandoned`:
      - If `record.worktree_path` is not None:
        - Iterate `junctions_cfg.items()`: for each `(link_tpl, target_tpl)` where `_junction.has_slug_token(target_tpl)`: resolve the relative link path via `_junction.resolve_target(link_tpl, {"SLUG": record.slug, "WIKI_PATH": str(wiki_path), "HUB_PATH": str(hub_root)})`. Note: `resolve_target` only raises on tokens referenced in `link_tpl` that are absent from the dict — extra dict keys are harmless, so passing all three tokens is safe. The resolved link is a relative path (e.g. `.active`) — anchor it to the worktree: `abs_link = record.worktree_path / resolved_link`. Call `_junction.remove(abs_link)`. Log to stderr. (mill-spawn creates junctions at `worktree_path / junction_rel`; the cleanup must remove them at the same absolute location, not relative to the hub cwd.)
        - Call `_worktree.remove(record.worktree_path, cwd=hub_root)`.
        - If `record.branch` is not None: `_subprocess_util.run(["git", "-C", str(hub_root), "branch", "-D", record.branch])` — log stdout/stderr. Do not raise on failure (branch may already be gone); log and continue.
      - If `record.active_dir` is not None:
        - `shutil.rmtree(record.active_dir)`.
        - `wiki_relative_paths.append(f"active/{record.slug}")`.
    - **Home.md reset** (only if `plan.to_reset_home` is non-empty):
      - `home_text = (wiki_path / "Home.md").read_text("utf-8")`.
      - For each `slug` in `plan.to_reset_home`: `home_text = _tasks_md.set_phase(home_text, slug, None)`.
      - `(wiki_path / "Home.md").write_text(home_text, "utf-8")`.
      - `wiki_relative_paths.append("Home.md")`.
    - **Wiki commit** (only when `wiki_relative_paths` is non-empty — i.e. at least one active_dir was deleted or at least one Home.md marker was reset):
      - `_sidebar.regenerate(wiki_path)`. `wiki_relative_paths.append("_Sidebar.md")`.
      - `_wiki.write_commit_push(wiki_path, wiki_relative_paths, f"chore: cleanup — {len(plan.to_remove_done)} done, {len(plan.to_remove_abandoned)} abandoned")`.
      - Note: sidebar regenerate lives inside this guard so it only runs when there is a commit to attach it to. Worktree-only removals (no active_dir, no Home.md reset) skip the wiki commit entirely — correct, since nothing in the wiki changed.
  - **`def main() -> None:`**
    - Parse args first — `--help` and unknown-arg errors must fail before any I/O:
      - `parser = argparse.ArgumentParser(description="Sweep done/abandoned task artefacts.")`. Add `--apply` boolean flag. `args = parser.parse_args()`.
    - Guard: `if (Path.cwd() / ".millhouse" / "active.slug.md").exists(): sys.exit("Error: mill-cleanup must run from the hub, not from a worktree.")`.
    - `git_root = _paths.resolve_git_root(); wiki_path = _paths.resolve_wiki_path(git_root)`.
    - `_wiki.sync_pull(wiki_path)`.
    - `active_root = wiki_path / "active"`. If not `active_root.exists()`: print "No active/ directory found; nothing to clean." and exit 0.
    - `active_dirs = sorted(p for p in active_root.iterdir() if p.is_dir())`.
    - `worktrees = _worktree.list_worktrees(cwd=git_root)`.
    - `home_text = (wiki_path / "Home.md").read_text("utf-8"); home_tasks = _tasks_md.parse(home_text)`.
    - `junctions_cfg = _wiki.read_junctions(wiki_path)`.
    - `plan = build_plan(active_dirs, worktrees, home_tasks, wiki_path, hub_root=git_root)`.
    - `_print_plan(plan)`.
    - If `not args.apply`: print `"\nDry-run. Pass --apply to execute."`. `sys.exit(0)`.
    - `_wiki.acquire_lock(wiki_path, "mill-cleanup")`.
    - `try: apply_plan(plan, wiki_path, git_root, junctions_cfg)`.
    - `finally: _wiki.release_lock(wiki_path)`.
    - Print summary: `f"\nDone: {len(plan.to_remove_done)} done, {len(plan.to_remove_abandoned)} abandoned removed. {len(plan.to_report)} orphans/unreadable reported."`.
  - `if __name__ == "__main__": main()`.
- **Commit:** `feat(cleanup): add mill-cleanup.py — sweep done/abandoned task artefacts`

### Card 4: `plugins/mill/unit_tests/test-cleanup.py`

- **Reads:** `plugins/mill/scripts/mill-cleanup.py` (post-Card-3), `plugins/mill/unit_tests/test-tasks-md.py` (pattern for testing with synthetic text inputs), `plugins/mill/unit_tests/test-paths.py` (importlib pattern for script with hyphens).
- **Modifies:** (none)
- **Creates:** `plugins/mill/unit_tests/test-cleanup.py`
- **Requirements:**
  - Constants: `SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"`.
  - Import via importlib:
    ```python
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mill_cleanup", SCRIPTS / "mill-cleanup.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    build_plan = mod.build_plan
    CleanupPlan = mod.CleanupPlan
    SlugRecord = mod.SlugRecord
    ```
  - Helper: `_make_status_md(phase: str) -> str` — returns minimal status.md content with a fenced yaml block containing `phase: <phase>`.
  - Helper: `_make_task(slug, phase_marker)` — returns a `_tasks_md.Task` with the given slug and phase marker and stub values for the remaining required fields: `Task(slug=slug, title="test", phase=phase_marker, has_proposal=False, heading_line_no=1)`. (Task is a frozen dataclass with five required fields; all five must be supplied.)
  - All test fixtures use `tempfile.TemporaryDirectory` to create real `active/<slug>/status.md` files (because `_read_phase` reads files).
  - **Test — done slug with worktree and active_dir:**
    - `active_dirs = [tmp / "done-slug"]`; write `status.md` with `phase: done`.
    - `worktrees = [{"path": str(tmp / "hub"), "branch": "main"}, {"path": str(tmp / "worktrees" / "done-slug"), "branch": "impl/done-slug"}]`. (Hub entry must be included so orphan filter works correctly.)
    - `home_tasks = [_make_task("done-slug", "done")]`.
    - `plan = build_plan(active_dirs, worktrees, home_tasks, tmp, hub_root=tmp / "hub")`.
    - Assert `len(plan.to_remove_done) == 1`. Assert `plan.to_remove_done[0].slug == "done-slug"`. Assert `plan.to_remove_done[0].branch == "impl/done-slug"`. Assert `plan.to_reset_home == []`. Assert `plan.to_report == []`.
    - PASS: `"PASS build_plan — done slug with worktree → to_remove_done"`.
  - **Test — abandoned slug with [active] marker:**
    - `phase: abandoned` in status.md; home marker `"active"`.
    - Assert `len(plan.to_remove_abandoned) == 1`. Assert `plan.to_reset_home == ["abandoned-slug"]`. Assert `plan.to_report == []`.
    - PASS: `"PASS build_plan — abandoned slug + [active] marker → to_remove_abandoned + to_reset_home"`.
  - **Test — abandoned slug with [done] marker (inconsistency):**
    - `phase: abandoned` in status.md; home marker `"done"`.
    - Assert `plan.to_remove_abandoned == []`. Assert `plan.to_reset_home == []`. Assert `len(plan.to_report) == 1`. Assert `"skipping" in plan.to_report[0].lower()`.
    - PASS: `"PASS build_plan — abandoned + [done] marker → inconsistency reported, not removed"`.
  - **Test — live slug (implementing) → no action:**
    - `phase: implementing`. Any marker.
    - Assert `plan.to_remove_done == [] and plan.to_remove_abandoned == [] and plan.to_reset_home == []`.
    - PASS: `"PASS build_plan — live phase (implementing) → no action"`.
  - **Test — unreadable status.md (missing file):**
    - Create `active_dirs = [tmp / "bad-slug"]` but do NOT write `status.md`.
    - Assert `len(plan.to_report) == 1`. Assert `"bad-slug" in plan.to_report[0]` and `"unreadable" in plan.to_report[0]`.
    - PASS: `"PASS build_plan — missing status.md → reported as unreadable, no action"`.
  - **Test — orphan worktree (worktree with no active_dir):**
    - `active_dirs = []`. `hub_root = tmp / "hub"`. `worktrees = [{"path": str(hub_root), "branch": "main"}, {"path": str(tmp / "worktrees" / "ghost-slug"), "branch": "impl/ghost-slug"}]`.
    - Assert `plan.to_report` contains a line with `"orphan worktree"` and `"ghost-slug"`.
    - PASS: `"PASS build_plan — orphan worktree → reported"`.
  - **Test — orphan Home.md marker ([active] with no active_dir):**
    - `active_dirs = []`. `home_tasks = [_make_task("ghost-slug", "active")]`. `worktrees = [{"path": str(hub_root), "branch": "main"}]`.
    - Assert `plan.to_report` contains a line with `"orphan"` and `"ghost-slug"`.
    - PASS: `"PASS build_plan — orphan [active] Home.md marker → reported"`.
  - **Test — orphan active_dir (active_dir with no Home.md entry):**
    - `active_dirs = [tmp / "no-home-slug"]`; write `status.md` with `phase: implementing`; `home_tasks = []` (no entry for this slug).
    - Assert `plan.to_report` contains a line with `"orphan"` and `"no-home-slug"`.
    - PASS: `"PASS build_plan — orphan active_dir (no Home.md entry) → reported"`.
  - Follow `main()` / PASS pattern from `test-paths.py`.
- **Commit:** `test(cleanup): unit tests for build_plan — all phase and orphan combinations`

## Batch Tests

`python plugins/mill/unit_tests/test-cleanup.py` must pass. Uses real files in `tempfile.TemporaryDirectory` for `_read_phase`; no git required. Batch 03 depends on this passing before running the full integration test.
