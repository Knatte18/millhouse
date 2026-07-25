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

### Card 9: Rebind project_root in millpy-implement.py

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

### Card 10: Rebind project_root in millpy-fix.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Identical pattern to Card 9. Immediately after the existing

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

### Card 11: Capture slug and rebind project_root in millpy-merge-in-subagent.py

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

### Card 12: Add regression tests for the implementer/fixer-family rebinds

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** **Prerequisite fix required before this card's own new test will pass, and before ANY pre-existing test in these 3 files will still pass (plan-review round 3 BLOCKING finding):** Cards 9-11 add an unguarded `container_path = _paths.resolve_container_path(git_root)` call. `resolve_container_path` → `resolve_main_worktree_root` → `_pygit2_util` performs real git operations against `git_root`; none of the 3 files' existing test fixtures use a real git repo, and none mock `resolve_container_path` or `resolve_active_hub` today. Left unmocked, `resolve_main_worktree_root` raises an uncaught `SystemExit` against the fake `git_root`, crashing every pre-existing test in all 3 files, not just new ones.

  **Corrected per-file description of how `project_root` resolves today (plan-review round 5 NIT — an earlier draft over-generalized this as "setUp mocks `resolve_hub_path`" for all 3 files, which is only true for one):**
  - `test-millpy-implement.py`: `setUp` mocks both `_paths.resolve_git_root` and `_paths.resolve_hub_path` directly, each returning `self.tmp_path`.
  - `test-millpy-fix.py`: `setUp` mocks only `_paths.resolve_git_root` (returning `self.tmp_path`) — `resolve_hub_path` is NOT mocked in `setUp` (only in a few specific nested-hub test methods elsewhere in the file). Instead, `setUp` calls `os.chdir(self.tmp_path)` and `_make_fixture` writes a real `.millhouse/config.local.yaml` at `self.tmp_path`, so the real (unmocked) `resolve_hub_path()` succeeds by finding `.millhouse` immediately at cwd — no escaping-fallback code path is exercised, and `project_root` still ends up equal to `self.tmp_path`.
  - `test-millpy-merge-in-subagent.py`: this CLI uses `Path.cwd()` directly, not `resolve_hub_path` at all — `setUp` mocks only `_paths.resolve_git_root`; `project_root` resolves to `self.tmp_path` because `setUp` calls `os.chdir(self.tmp_path)` and a `.millhouse/config.local.yaml` is written there (unused by this file's `Path.cwd()` binding, but present from the shared fixture-writing pattern).

  In all 3 cases, `project_root` ends up equal to `self.tmp_path` **today**, by whichever mechanism that file actually uses — this is the value the new `resolve_active_hub` mock must also return, so every pre-existing assertion stays unchanged.

  **Fix, applied to each of the 3 files' shared `setUp`:** add two new mocks, following the same `_p(...)` (or equivalent) pattern already used for `resolve_git_root`:
  - `_paths.resolve_container_path` → return a stable decoy value (e.g. `self.tmp_path.parent`, or any fixed path — its value is never asserted on directly).
  - `_paths.resolve_active_hub` → return `self.tmp_path` (the same value `project_root` already resolves to in each file's fixture, per the per-file description above). This keeps every pre-existing test's `project_root`-derived assertions byte-for-byte unchanged, since the rebind now resolves to the identical value the old code path did in these fixtures.

  **Then**, for each of the 3 test files, add one new, focused regression test that OVERRIDES `resolve_active_hub`'s return value specifically for that one test (via `unittest.mock.patch.object` scoped to the test method, or by temporarily reassigning the shared mock's `return_value`) to a decoy directory DISTINCT from `self.tmp_path`, while whatever the file's original resolver was (`resolve_hub_path` for `test-millpy-implement.py`; the real cwd-based walk for `test-millpy-fix.py`; `Path.cwd()` for `test-millpy-merge-in-subagent.py`) still points at `self.tmp_path` (simulating "escaped to main worktree" — the old path returns the wrong place, but the corrected `resolve_active_hub` call returns the right one). Assert that `briefs_dir` (or `status_path`, whichever is the simplest observable surface in that file's existing test harness) ends up resolving under the value `resolve_active_hub` returns (the "corrected" one), not the old value. The assertion should fail against the pre-Card-9-through-11 code (which never calls `resolve_active_hub`) and pass after. Do not weaken or remove any existing test in these 3 files; this card only adds the two new shared mocks plus one new regression test per file.

  **Additional discovered scope (implementer, round 1):** `test-merge-in-subagent.py` (note: distinct from `test-millpy-merge-in-subagent.py` above — this is the separate `main()`-level verify-fix success-gating test file) exercises `millpy-merge-in-subagent.py`'s `main()` directly against a real git repo in a `tempfile.TemporaryDirectory()`, mocking only `_marker.slug_from_branch` and `_review_common.load_config`; it never mocks `_paths.resolve_git_root`, `_paths.resolve_container_path`, or `_paths.resolve_active_hub`, and never `os.chdir`s into its fixture directory. Before Card 11, this was harmless because `project_root = Path.cwd()` never consulted `git_root` at all. After Card 11's rebind, the now-unmocked `_paths.resolve_active_hub(container_path, "test-task", ...)` call performs a real `resolve_active_worktree` lookup for a worktree literally named `test-task` under the real container's `wts/`, which does not exist, raising `ActiveWorktreeNotFound` and crashing all 4 of this file's fixture-dependent cases (A, B, C, C-finalize). Fix: in each of those 4 cases' fixture setup, additionally mock `_paths.resolve_git_root` to return `project_root` and `_paths.resolve_active_hub` to return `project_root` (mirroring the `_marker.slug_from_branch`/`_review_common.load_config` mocking already present in each case), so `project_root` resolves to the fixture's own tempdir exactly as it did before Card 11 (no assertion changes needed beyond the added mocks).
- **Commit:** `test(dispatch-path-gaps): cover project_root rebinding for implement/fix/merge-in-subagent`

## Batch Tests

`verify:` runs the existing test file for each of the 3 edited CLIs (`test-millpy-implement.py`, `test-millpy-fix.py`, `test-millpy-merge-in-subagent.py`, `test-merge-in-subagent.py`) as regression coverage, plus `test-paths.py` since this batch's fix depends on `resolve_active_hub`/`resolve_container_path`.
