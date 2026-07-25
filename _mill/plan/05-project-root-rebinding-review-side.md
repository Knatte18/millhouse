# Batch: project-root-rebinding-review-side

```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: project-root-rebinding-review-side
number: 5
cards: 4
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-plan-flow.py test-review-plan-finalize-round.py test-review-discussion-flow.py test-paths.py"
depends-on: [3]
```

## Batch Scope

The other half of closing #675 (split from `project-root-rebinding-implement-side` solely because the combined batch exceeded the per-batch context budget; the two batches touch entirely disjoint files and have no ordering dependency on each other). Covers the 3 review-CLI-family files: `millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py`. Same underlying bug and same fix shape as the implement-side batch: `project_root`/`hub_dir` is bound once via `resolve_hub_path()`, then reused for `status_path`, the `prepare()` call, and `briefs_dir` alike — this batch rebinds it to the corrected value immediately after each file's own (unmodified) slug resolution, using `_paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True)` from `paths-skip-slug-validation`. Depends only on `paths-skip-slug-validation` (batch 3) — none of these 3 files are touched by `fail-fast-guard`, so no ordering dependency on batch 1 is needed.

**Batch-local decision (why the rebind sits after slug resolution, and why the slug-resolution call itself is untouched):** all 3 files in this batch resolve `slug` via `find_active_slug(project_root, wiki_root, cfg)` — passing the ORIGINAL (possibly escaped) `project_root` value as `find_active_slug`'s `hub_root` parameter. This plan does NOT change that argument: `find_active_slug`'s on-disk `_mill/*.active` glob is scoped by whatever `hub_root` value the caller passes, and in nested M2+sub layouts that scoping may have a different, legitimate meaning tied to the ORIGINAL value. Changing it is a separate, higher-risk change this plan does not make (see the overview's "cfg-loading's use of the original project_root" Shared Decision — the same reasoning applies here: none of the 7 originating issues report a wrong-slug-resolution symptom, only `briefs_dir`/dispatch-hang symptoms, so this plan fixes exactly that and no more).

## Cards

### Card 12: Rebind project_root in millpy-review-code.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Do NOT change the existing

  ```python
  try:
      slug = args.slug or find_active_slug(project_root, wiki_root, cfg)
  except ReviewError as exc:
      print_error_envelope("code", str(exc))
      return 1
  ```

  block — leave it exactly as-is (see this batch's Scope note on why). Immediately after it, and before the `if args.batch is not None:` guard that calls `_paths.require_status_path(project_root, cfg)`, insert:

  ```python
  container_path = _paths.resolve_container_path(git_root)
  project_root = _paths.resolve_active_hub(
      container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True
  )
  mill_dir = project_root / ".millhouse"
  ```

  Every subsequent use of `project_root` (the `require_status_path` guard, the `prepare(...)` call's `project_root=project_root` keyword argument, and **`briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")`** — corrected per plan-review round 1: this line reads `project_root`, not `git_root`; an earlier draft of this card misstated it as already `git_root`-based, which was a factual error against the actual current source — it IS fixed by this rebind, the same as the other review-CLI files) resolves against the corrected worktree.
- **Commit:** `fix(millpy-review-code): rebind project_root to the active task worktree after slug resolution`

### Card 13: Rebind project_root in millpy-review-plan.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Same pattern and same caveat as Card 12 (do not change the `find_active_slug(project_root, wiki_root, cfg)` call). Immediately after the existing

  ```python
  try:
      slug = args.slug or find_active_slug(project_root, wiki_root, cfg)
  except ReviewError as exc:
      print_error_envelope("plan", str(exc))
      return 1
  ```

  block (unmodified) and before the `if args.stage == "prepare":` branch (which calls `_paths.require_status_path(project_root, cfg)` for plan validation, then `prepare(...)`, then binds `briefs_dir = _paths.resolve_task_path(project_root, "_mill/briefs/")`), insert:

  ```python
  container_path = _paths.resolve_container_path(git_root)
  project_root = _paths.resolve_active_hub(
      container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True
  )
  mill_dir = project_root / ".millhouse"
  ```

  Every subsequent use of `project_root` in the `prepare`-stage branch (both `require_status_path` calls, the `prepare(...)` call's `project_root=project_root` argument, and `briefs_dir`) resolves against the corrected worktree.
- **Commit:** `fix(millpy-review-plan): rebind project_root to the active task worktree after slug resolution`

### Card 14: Rebind hub_dir in millpy-review-discussion.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file uses `hub_dir` as the primary variable with `project_root = hub_dir` as an alias — same caveat as Cards 12-13 (slug resolved via `find_active_slug(project_root, wiki_root, cfg)`; do not change that call's argument). Immediately after the existing

  ```python
  try:
      slug = args.slug or find_active_slug(project_root, wiki_root, cfg)
  except ReviewError as exc:
      print_error_envelope("discussion", str(exc))
      return 1
  ```

  block (unmodified) and before the `if args.stage == "prepare":` branch (which calls `prepare(cfg, slug, mill_dir, project_root, wiki_root, ...)` and binds `briefs_dir = _paths.resolve_task_path(hub_dir, "_mill/briefs/")`), insert:

  ```python
  container_path = _paths.resolve_container_path(git_root)
  hub_dir = _paths.resolve_active_hub(
      container_path, slug, cfg=cfg, git_root=git_root, skip_slug_validation=True
  )
  project_root = hub_dir
  mill_dir = hub_dir / ".millhouse"
  ```

  Every subsequent use of `hub_dir`/`project_root` (the `prepare(...)` call and `briefs_dir`) resolves against the corrected worktree.
- **Commit:** `fix(millpy-review-discussion): rebind hub_dir to the active task worktree after slug resolution`

### Card 15: Add regression tests for the review-CLI-family rebinds

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** For each of the 3 test files listed under Edits, add one focused regression test matching that file's existing mocking conventions: mock `_paths.resolve_hub_path` to return a decoy directory simulating the "escaped to main worktree" failure mode (a tmpdir distinct from the fixture's real task worktree), and mock `_paths.resolve_active_hub` to return the fixture's real task worktree path, then assert that `briefs_dir` ends up resolving under the real task worktree, not the decoy, for all three files (`millpy-review-code.py`'s `briefs_dir` is fixed by this batch's rebind exactly like the other two — see the correction on Card 12; do not treat it as already-correct or exempt it from this test). The assertion should fail against the pre-Card-12-through-14 code (which would resolve everything under the decoy) and pass after. Do not weaken or remove any existing test in these 3 files; this card only adds new regression coverage.
- **Commit:** `test(dispatch-path-gaps): cover project_root/hub_dir rebinding for the review-CLI family`

## Batch Tests

`verify:` runs the existing flow test for each of the 3 edited review CLIs (`test-review-code-flow.py`, `test-review-plan-flow.py`, `test-review-plan-finalize-round.py`, `test-review-discussion-flow.py`) as regression coverage, plus `test-paths.py` since this batch's fix depends on `resolve_active_hub`/`resolve_container_path`.
