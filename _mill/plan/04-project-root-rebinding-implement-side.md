# Batch: project-root-rebinding-implement-side

```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: project-root-rebinding-implement-side
number: 4
cards: 4
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-millpy-fix.py test-millpy-merge-in-subagent.py test-merge-in-subagent.py test-paths.py"
depends-on: [1, 3]
```

## Batch Scope

Half of closing #675 (the other half is `project-root-rebinding-review-side`, split out solely because the combined batch exceeded the per-batch context budget). Covers the 3 implementer/fixer-family CLIs: `millpy-implement.py`, `millpy-fix.py`, `millpy-merge-in-subagent.py`. In each, `project_root` is bound once near the top of `main()` via `_paths.resolve_hub_path()` (or, in `millpy-merge-in-subagent.py`'s case, raw `Path.cwd()` — no `.millhouse` walk at all), then reused for `status_path`, `plan_base`, cleanliness-snapshot paths, git subprocess `cwd=`, the `PROJECT_ROOT` template token, and `briefs_dir` alike. `resolve_hub_path()`'s cwd-walk falls back to the **main** worktree when it finds no `.millhouse/config.local.yaml` — every downstream consumer breaks identically when that fallback fires, not just `briefs_dir` (the symptom the originating issue reports named). This batch rebinds `project_root` to the corrected value in all 3 files, immediately after each file's own (unmodified) slug resolution, using `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True)` from `paths-skip-slug-validation` — never a `briefs_dir`-only parallel binding. Depends on `fail-fast-guard` (batch 1) because both batches edit `millpy-implement.py`'s `main()` and must not run in an unordered parallel fashion; depends on `paths-skip-slug-validation` (batch 3) because it needs that batch's new `skip_slug_validation` parameter.

**Batch-local decision (why the rebind sits after slug resolution, not at the original binding site):** see the overview's "project_root/hub_dir rebind happens AFTER slug resolution" Shared Decision — every card below implements that pattern. No card in this batch changes how any file resolves `slug` itself.

## Cards

### Card 8: Rebind project_root in millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `main()`, immediately after the existing

  ```python
  try:
      slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
  except _marker.MarkerError as e:
      print(str(e), file=sys.stderr)
      return 1
  except WikiStartupError as e:
      print(f"wiki daemon unreachable: {e}", file=sys.stderr)
      return 1
  ```

  block (unmodified) and before `plan_dir = cfg.get("paths", {}).get("plan_dir", "_mill/plan/")`, insert:

  ```python
  container_path = _paths.resolve_container_path(git_root)
  project_root = _paths.resolve_active_hub(
      container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True
  )
  mill_dir = project_root / ".millhouse"
  ```

  Every use of `project_root` from this point forward in the function (`status_path = _paths.require_status_path(project_root, cfg)`, `plan_base = _paths.resolve_task_path(project_root, plan_dir)`, the cleanliness-snapshot paths, every `cwd=project_root` git subprocess call, the `"PROJECT_ROOT": str(project_root)` template token, and `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")`) now resolves against the corrected worktree. The earlier `mill_dir`/`project_root` binding at the top of `main()` (used only to bootstrap `cfg` via `_review_common.load_config`) is left unchanged — see the overview's Shared Decision on why.
- **Commit:** `fix(millpy-implement): rebind project_root to the active task worktree after slug resolution`

### Card 9: Rebind project_root in millpy-fix.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Identical pattern to Card 8. Immediately after the existing

  ```python
  try:
      slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
  except _marker.MarkerError as e:
      print(str(e), file=sys.stderr)
      return 1
  except WikiStartupError as e:
      print(f"wiki daemon unreachable: {e}", file=sys.stderr)
      return 1
  ```

  block (unmodified) and before `status_path = _paths.require_status_path(project_root, cfg)`, insert:

  ```python
  container_path = _paths.resolve_container_path(git_root)
  project_root = _paths.resolve_active_hub(
      container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True
  )
  mill_dir = project_root / ".millhouse"
  ```

  Every subsequent use of `project_root` (`status_path`, `plan_base = _paths.resolve_task_path(project_root, "_mill/plan/")`, `fixer_snapshot_path`, git `cwd=project_root` calls, the `"PROJECT_ROOT": str(project_root)` template token, and `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")`) resolves against the corrected worktree.
- **Commit:** `fix(millpy-fix): rebind project_root to the active task worktree after slug resolution`

### Card 10: Capture slug and rebind project_root in millpy-merge-in-subagent.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file's `project_root` binding is raw `Path.cwd()` — no `.millhouse` walk at all, and its slug-resolving call currently discards the return value:

  ```python
  try:
      _marker.slug_from_branch(git_root, wiki_path, cfg)
  except _marker.MarkerError as e:
      print(str(e), file=sys.stderr)
      return 1
  ```

  Replace with (capturing the slug, then rebinding `project_root`):

  ```python
  try:
      slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
  except _marker.MarkerError as e:
      print(str(e), file=sys.stderr)
      return 1

  container_path = _paths.resolve_container_path(git_root)
  project_root = _paths.resolve_active_hub(
      container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True
  )
  mill_dir = project_root / ".millhouse"
  ```

  placed immediately before `if args.recompute_baseline: return _run_recompute_baseline(project_root, git_root, cfg)`. This ensures `_run_recompute_baseline` and every later call in this file that receives `project_root` as a parameter (`_run_conflicts`, `_run_verify_fix`, and their internal `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")` at all 3 call sites) receives the corrected value — no changes are needed inside `_run_conflicts`/`_run_verify_fix` themselves, since they already take `project_root` as a parameter from their caller.
- **Commit:** `fix(millpy-merge-in-subagent): capture slug and rebind project_root to the active task worktree`

### Card 11: Add regression tests for the implementer/fixer-family rebinds

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** For each of the 3 test files listed under Edits, add one focused regression test matching that file's existing mocking conventions (e.g. `test-millpy-implement.py`'s `setUp`/`_p(...)`/`_run_main` pattern): mock `_paths.resolve_hub_path` (or, for `test-millpy-merge-in-subagent.py`, mock `Path.cwd`) to return a decoy directory simulating the "escaped to main worktree" failure mode (a tmpdir distinct from the fixture's real task worktree), and mock `_paths.resolve_active_hub` to return the fixture's real task worktree path, then assert that `briefs_dir` (or `status_path`, whichever is the simplest observable surface in that file's existing test harness) ends up resolving under the real task worktree, not the decoy. The assertion should fail against the pre-Card-8-through-10 code (which would resolve everything under the decoy) and pass after. Do not weaken or remove any existing test in these 3 files; this card only adds new regression coverage.
- **Commit:** `test(dispatch-path-gaps): cover project_root rebinding for implement/fix/merge-in-subagent`

## Batch Tests

`verify:` runs the existing test file for each of the 3 edited CLIs (`test-millpy-implement.py`, `test-millpy-fix.py`, `test-millpy-merge-in-subagent.py`, `test-merge-in-subagent.py`) as regression coverage, plus `test-paths.py` since this batch's fix depends on `resolve_active_hub`/`resolve_container_path`.
