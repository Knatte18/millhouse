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

### Card 13: Rebind project_root in millpy-review-code.py

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

### Card 14: Rebind project_root in millpy-review-plan.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Same pattern and same caveat as Card 13 (do not change the `find_active_slug(project_root, wiki_root, cfg)` call). Immediately after the existing

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

  The insertion point is before the `if args.stage == "prepare": / elif "finalize": / else:` stage dispatch, so every subsequent use of `project_root` — in ALL three stage branches, not just `prepare` (plan-review round 3 NIT: an earlier draft of this card said "in the prepare-stage branch," which understated the fix's reach) — resolves against the corrected worktree: both `require_status_path` calls, the `prepare(...)` call's `project_root=project_root` argument, `briefs_dir`, and equally the `finalize`/`full`-stage branches' own uses of `project_root` (e.g. their `run(...)`/`finalize(...)` calls).
- **Commit:** `fix(millpy-review-plan): rebind project_root to the active task worktree after slug resolution`

### Card 15: Rebind hub_dir in millpy-review-discussion.py

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file uses `hub_dir` as the primary variable with `project_root = hub_dir` as an alias — same caveat as Cards 13-14 (slug resolved via `find_active_slug(project_root, wiki_root, cfg)`; do not change that call's argument). Immediately after the existing

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

### Card 16: Add regression tests for the review-CLI-family rebinds

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-finalize-round.py`
  - `plugins/mill/unit_tests/test-review-cli.py`
  - `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** **Corrected scope (plan-review round 3 BLOCKING finding):** an earlier draft of this card said to add a test "matching that file's existing mocking conventions" for all 3 files — this is only true for `test-review-discussion-flow.py`, which already has a CLI-`main()`-level test (`test_brief_path_nested_layout`, using `importlib.util.spec_from_file_location` + `unittest.mock.patch.dict(sys.modules, ...)` to inject `MagicMock` stand-ins for every module `millpy-review-discussion.py`'s `main()` imports inline, then invoking `mod.main()` directly and asserting on the mocks' recorded calls). `test-review-code-flow.py` and `test-review-plan-flow.py` have **no such harness at all** — they only exercise `_review_code.run()`/`_review_plan.run()` (the backend functions), never `millpy-review-code.py`'s/`millpy-review-plan.py`'s own `main()`, which is where Cards 13/14's rebind actually lives. Testing the rebind in those two files requires building the same importlib/`sys.modules`-injection harness from scratch, not extending an existing convention.

  For **`test-review-discussion-flow.py`** (existing harness, extend it): add one new test, modeled directly on `test_brief_path_nested_layout`, that additionally injects a `MagicMock` for `_paths` whose `resolve_hub_path` returns a decoy directory and whose `resolve_active_hub` returns the fixture's real task-worktree directory (distinct from the decoy), then asserts (via the injected mock's recorded call args, same technique `test_brief_path_nested_layout` already uses for `resolve_task_path`) that `briefs_dir` resolves under the value `resolve_active_hub` returned, not `resolve_hub_path`'s.

  For **`test-review-code-flow.py`** and **`test-review-plan-flow.py`** (no existing harness — build one): add one new test to each, following `test_brief_path_nested_layout`'s exact technique: use `importlib.util.spec_from_file_location` to load `millpy-review-code.py` / `millpy-review-plan.py` respectively; build `MagicMock` stand-ins for every module each file's `main()` imports inline (for `millpy-review-code.py`: `_agent_dispatch`, `_paths`, `_reviewers`, `_review_cli`, `_review_common` — providing `ReviewError`, `find_active_slug`, `load_config`, `resolve_path`, and `_review_code` — providing `prepare`, `finalize`, `run`; for `millpy-review-plan.py`: the same set plus `_parent_branch`, and `_review_common` additionally providing `_load_root_from_overview`, `discover_round`, and `_review_plan` providing `prepare`, `finalize`, `run`); inject them via `unittest.mock.patch.dict(sys.modules, injected_modules)` before `exec_module`; patch `sys.argv` to enter the `--stage prepare` branch; call `mod.main()`; and assert, via the mocked `_paths.resolve_active_hub`'s recorded call (mock its return value to a fixture directory distinct from `resolve_hub_path`'s mocked return value) and the mocked `_agent_dispatch.write_brief`'s recorded `briefs_dir` argument, that `briefs_dir` resolves under `resolve_active_hub`'s value, not `resolve_hub_path`'s.

  For all 3 files, the new test's assertion should fail against the pre-Card-13-through-15 code (which never calls `resolve_active_hub` and would resolve `briefs_dir` under `resolve_hub_path`'s decoy value) and pass after. Do not weaken or remove any existing test in these 3 files.

  **Scope extension (discovered during implementation, not part of the original card):** `test-review-plan-finalize-round.py` patches `_paths.resolve_hub_path`/`resolve_git_root`/`resolve_wiki_path` directly on the real `_paths` module (not via `sys.modules` injection) to drive `millpy-review-plan.py`'s and `millpy-review-discussion.py`'s `main()` through the `--stage finalize` branch, but never mocked `_paths.resolve_container_path`/`resolve_active_hub`. Cards 14/15's rebind now calls those for real inside every one of its 4 test cases, which fails against the tests' plain-tempdir fixture (`not a git repository`). Add `unittest.mock.patch("_paths.resolve_container_path")` and `unittest.mock.patch("_paths.resolve_active_hub")` (returning the same `tmp` value already used for `resolve_hub_path`/`resolve_git_root`) to all 4 test cases' mock stacks.

  **Second scope extension (discovered during implementation):** `test-review-cli.py`'s `test_discussion_prepare_brief_path_uses_hub_dir`, `test_plan_prepare_brief_path_uses_git_root`, and `test_code_prepare_brief_path_uses_git_root` already assert the exact #675 fix this batch implements (brief_path must resolve under `hub_root`/`task_root`, not the wrong root) via real `_mod.main(...)` calls against a plain-tempdir fixture (no real git repo), patching `_paths.resolve_git_root`/`resolve_hub_path`/`resolve_wiki_path` directly on the real `_paths` module. All three pre-date this batch (the plan/code pair as known-failing pins of the not-yet-fixed regression). Cards 13/14/15's rebind now calls the real (unmocked) `_paths.resolve_container_path`/`resolve_active_hub` inside all three tests, which raises `SystemExit` against the fixture's non-git `task_root`/`hub_root` (not a git repository) -- crashing the whole test file before it reaches its later test functions (the discussion test runs first in file order, so it is what actually crashes the process). Add `unittest.mock.patch("_paths.resolve_container_path", return_value=tmp / "wts")` and `unittest.mock.patch("_paths.resolve_active_hub", return_value=hub_root)` (discussion) / `return_value=task_root` (plan, code) to all three tests' mock stacks so the rebind resolves to the value each test was already asserting the fixed brief_path against, instead of hitting real git.

  **Third scope extension (discovered during implementation):** `test-review-cli-error-envelope.py`'s shared `_run_cli_test` helper and `test_plan_uncaught_exception` patch `_paths.resolve_git_root`/`resolve_wiki_path` directly on the real `_paths` module but never mocked `_paths.resolve_container_path`/`resolve_active_hub`, for the same reason as the two scope extensions above. Add `unittest.mock.patch("_paths.resolve_container_path", return_value=self.tempdir_path)` and `unittest.mock.patch("_paths.resolve_active_hub", return_value=self.tempdir_path)` to both mock stacks.
- **Commit:** `test(dispatch-path-gaps): cover project_root/hub_dir rebinding for the review-CLI family`

## Batch Tests

`verify:` runs the existing flow test for each of the 3 edited review CLIs (`test-review-code-flow.py`, `test-review-plan-flow.py`, `test-review-plan-finalize-round.py`, `test-review-discussion-flow.py`) as regression coverage, plus `test-paths.py` since this batch's fix depends on `resolve_active_hub`/`resolve_container_path`.
