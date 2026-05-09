# Batch: migration

```yaml
task: Drop active.slug.md marker
batch: migration
number: 2
cards: 25
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

This batch performs the atomic migration: every production caller of `_active` switches to `_marker`, every signature change to `is_inplace` / `find_active_slug` / `load_task_title` / `discover_active_worktrees` / `write_active_marker` is propagated through every caller and every test, and `_active.py` plus `test-active.py` are deleted. The verify is the full unit test suite (`run-all.py`); the batch is correct only when every test passes.

The batch is large by file count (~46 files) but mechanical — each card edits a tightly-scoped logical unit. Cards are grouped by signature-change-cluster: within a cluster, every caller and every test that touches the changed surface lands in adjacent cards so the build is internally consistent at the end of the batch. Card numbering is global across the plan; cards in this batch start at 4.

External interface delivered: the codebase no longer imports `_active`; `_marker` is the single source of truth for branch+Home.md slug derivation; `_inplace.is_inplace` and `_review_common.find_active_slug` / `load_task_title` and `_spawn_core.discover_active_worktrees` carry their final-state signatures; `write_active_marker` does not exist; the marker file is never written by mill-spawn or mill-claim, never read by anyone, and the existing leftover marker files in user worktrees are harmless cruft per the discussion.

Batch-local decisions:

- **`discover_active_worktrees` derives slug from branch, not from directory name.** Even though `<wts>/<slug>/` invariant holds, using the branch matches the proposal's wording and gives a "is this worktree actively on its task branch" filter for free.
- **`discover_active_worktrees` takes `branch_prefix: str`, not `cfg: dict`.** Explicit dependency makes the function easier to test and keeps the signature focused.
- **The stub-read for `hub_relative_path` inside `discover_active_worktrees` is dropped.** `git -C <entry> branch --show-current` works regardless of hub_subpath because the git worktree root IS `<entry>`. The stub-read existed because the old marker file lived at `<entry>/<hub_subpath>/.millhouse/active.slug.md`; with branch detection there's no marker to find.

## Cards

### Card 4: rewrite `_paths.resolve_active_worktree` and `resolve_active_hub` to use `_marker`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_active.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the `import _active` line with `import _marker`. Rewrite `resolve_active_worktree(container_path, slug, *, cfg, git_root)` body: replace the `_active.read_all(hub_dir / ".millhouse")` block (lines around 290-300) with a `try: marker_slug = _marker.slug_from_branch(git_root, _paths.resolve_wiki_path(git_root), cfg); except _marker.MarkerError: marker_slug = None` pattern. The "in-place mode" check becomes `if marker_slug == slug and _inplace.is_inplace(slug, git_root, cfg): return git_root`. Replace the `_active.read_slug(worktree / ".millhouse")` call (line 307) with: read the per-worktree branch directly via `_subprocess_util.run(["git", "-C", str(worktree), "branch", "--show-current"])` and compute `dir_slug = branch.removeprefix(cfg.get("spawn", {}).get("branch_prefix", ""))`. Raise `ActiveWorktreeSlugMismatch(...)` when `dir_slug != slug`. Keep both `ActiveWorktreeNotFound` and `ActiveWorktreeSlugMismatch` exception classes and their `__all__` exports unchanged. Update the docstring entry for `resolve_active_worktree` and `resolve_active_hub` so the reference to "active marker" is replaced with "current branch (slug derived via `_marker.slug_from_branch`)".
- **Commit:** `refactor(paths): resolve_active_worktree uses _marker for slug detection`

### Card 5: update `test-paths.py` for `_paths` rewrite

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-paths.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Drop the `_active.write(...)` setup helper (around line 46) and replace usages with `_test_helpers._make_task_worktree(...)` (or inline equivalent: real `git init`, real `git checkout -b <branch>`, write a Home.md). Adjust the in-place test (around line 380) and the slug-mismatch test (around line 416) so both use branch+Home.md state instead of marker writes. Adjust the slug-mismatch assertion (existing test at lines 429, 516) to construct a worktree where the directory name is one slug but the checked-out branch is a different slug, then assert `ActiveWorktreeSlugMismatch` is raised. Drop `import _active` if present; add `import _marker` and `_test_helpers` (with sys.path bootstrap for unit_tests). Every passing test must still pass with the new internals.
- **Commit:** `test(paths): adapt resolve_active_* tests to branch+Home.md state`

### Card 6: change `_inplace.is_inplace` signature

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_inplace.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Change the function signature from `is_inplace(active_data: dict, git_root: Path, cfg: dict) -> bool` to `is_inplace(slug: str, git_root: Path, cfg: dict) -> bool`. Drop the branch-fetch via `_subprocess_util.run(["git", ...])` and the `current_branch != recorded_branch` check — both become tautological now that slug derives from current branch by definition (the helper assumes the caller already validated branch via `_marker.slug_from_branch`). Body reduces to: `worktrees_dir = _paths.resolve_worktrees_dir(cfg, git_root); return not (worktrees_dir / slug).is_dir()`. Drop `import _subprocess_util` if it becomes unused; keep `from _paths import resolve_worktrees_dir`. Keep `prompt_stale_worktree(slug, worktree_path)` unchanged. Update the module docstring's "Public API" block so the `is_inplace` signature line matches the new arguments.
- **Commit:** `refactor(inplace): is_inplace takes (slug, git_root, cfg)`

### Card 7: update `test-inplace.py` and `test-mill-merge-inplace.py` for new `is_inplace` signature

- **Context:**
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-inplace.py`
  - `plugins/mill/unit_tests/test-mill-merge-inplace.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-inplace.py`: every test that builds `active_data = {"slug": ..., "branch": ...}` and passes it to `is_inplace` must rewrite to pass `slug` directly. The `_inplace._subprocess_util.run` mock that returned a fake branch becomes obsolete (no branch fetch in `is_inplace`); remove those `patch("_inplace._subprocess_util.run", ...)` lines and the `_fake_run_branch` helper. Every "branch matches" / "branch mismatch" test reduces to "worktree dir exists" / "worktree dir absent". Drop the branch-mismatch tests (test names currently like `_test_is_inplace_false_on_branch_mismatch`) entirely — that condition no longer triggers a False return because the helper no longer reads branch. In `test-mill-merge-inplace.py`: update the `_test_is_inplace_importable_and_callable` test's expected params list from `["active_data", "git_root", "cfg"]` to `["slug", "git_root", "cfg"]`, and update the corresponding error-message string.
- **Commit:** `test(inplace): adapt is_inplace tests to (slug, git_root, cfg) signature`

### Card 8: rewrite `_spawn_core.discover_active_worktrees` and delete `write_active_marker`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_active.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Delete the `write_active_marker(mill_dir, slug, title, branch, ts)` function entirely (around lines 653-679) along with its docstring entry in the module's "Public API" block (around lines 46-47). Rewrite `discover_active_worktrees` with new signature `discover_active_worktrees(worktrees_dir: Path, home_tasks: list[_tasks_md.Task], branch_prefix: str) -> list[tuple[Path, str, str]]`. Body: `slugs_in_home = {t.slug: t for t in home_tasks}`; for each `entry in worktrees_dir.iterdir()` that is a directory, run `branch_proc = _subprocess_util.run(["git", "-C", str(entry), "branch", "--show-current"])`. When `returncode != 0` or `branch_proc.stdout.strip() == ""`, skip silently. Compute `branch = branch_proc.stdout.strip()`. When `branch_prefix` is non-empty and `not branch.startswith(branch_prefix)`, skip. Compute `slug = branch.removeprefix(branch_prefix) if branch_prefix else branch`. Look up `task = slugs_in_home.get(slug)`; skip when None. Append `(entry, slug, task.title)`. The `hub_relative_path` stub-read is dropped (no marker file to find). Drop `import _active` if it becomes unused after this change. Drop `import yaml` from inside the old function body. Update the module docstring's "Public API" block to reflect the new signature and to remove the `write_active_marker` line.
- **Commit:** `refactor(spawn-core): discover_active_worktrees uses branch+home_tasks; drop write_active_marker`

### Card 9: update `test-spawn-core.py` for `_spawn_core` rewrites

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Drop the `from _spawn_core import write_active_marker` import (around line 23). Delete `test_write_active_marker` (around lines 351-373) and remove its entry from the test list at the bottom of the file (around line 1013). Rewrite `test_discover_active_worktrees_standard_layout` (line 918) and `test_discover_active_worktrees_subfolder_install` (line 946) to call `discover_active_worktrees(wts_dir, home_tasks, branch_prefix)`: build `home_tasks` as a list of `_tasks_md.Task` instances by parsing a synthetic Home.md, set up real git repos under each `wts_dir / <slug>` with `git checkout -b f"{branch_prefix}{slug}"`, and assert the returned tuples match expectations. Drop the marker-write setup that called `_active.write(...)`. The subfolder-install test now exercises the path where the worktree git root is `<entry>` regardless of hub_subpath — verify the result is unchanged. Drop `import _active` if unused.
- **Commit:** `test(spawn-core): adapt to new discover signature; drop write_active_marker test`

### Card 10: rewrite `_review_common.find_active_slug` and `load_task_title` signatures

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Drop `import _active`. Add `import _marker`. Change `find_active_slug(mill_dir: Path) -> str` to `find_active_slug(git_root: Path, wiki_path: Path, cfg: dict) -> str`; body delegates to `_marker.slug_from_branch(git_root, wiki_path, cfg)` wrapped in `try/except _marker.MarkerError as exc: raise ReviewError(str(exc)) from exc`. Change `load_task_title(mill_dir: Path, slug: str) -> str` to `load_task_title(git_root: Path, wiki_path: Path, cfg: dict, slug: str) -> str`; body delegates to `_marker.task_data(git_root, wiki_path, cfg)` and returns `data.get("task_title") or slug`; on `_marker.MarkerError`, fall back to returning `slug`. Update the module docstring's `find_active_slug()` and `load_task_title()` description lines so the "_active" references are replaced with "_marker".
- **Commit:** `refactor(review-common): find_active_slug/load_task_title delegate to _marker`

### Card 11: update `_review_code.py`, `_review_discussion.py`, `_review_plan.py` callers of `load_task_title`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each of the three files, locate the `load_task_title(mill_dir, slug)` call and replace with `load_task_title(git_root, wiki_path, cfg, slug)`. Each module already has `git_root`, `wiki_path`, and `cfg` resolved earlier in its containing function (search upward for `_paths.resolve_git_root()` / `_paths.resolve_wiki_path(...)` / `load_config(...)` / equivalent locals — if a local is named differently, use that local; do not introduce new resolutions). Specifically: `_review_code.py:273` `load_task_title(mill_dir, slug)` → `load_task_title(git_root, wiki_path, cfg, slug)`; `_review_discussion.py:91` same pattern; `_review_plan.py:334` same pattern. If any of these three files lacks `git_root` / `wiki_path` / `cfg` in scope at the call site, plumb them through — but verify each function's existing locals first; the discussion notes these callers already have the values in scope.
- **Commit:** `refactor(review): pass git_root/wiki_path/cfg to load_task_title`

### Card 12: update review CLI scripts that call `find_active_slug`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each of the four files, replace `find_active_slug(mill_dir)` with `find_active_slug(git_root, wiki_path, cfg)`. Each script already resolves `git_root`, `wiki_path`, and `cfg` immediately before the call: `millpy-review-code.py:78`, `millpy-review-discussion.py:45`, `millpy-review-plan.py:78`, `millpy-validate-plan.py:44`. If a script resolves them in a different order than the new call expects, reorder the resolutions so the call is satisfied with already-bound locals. Drop the `mill_dir = ... / ".millhouse"` line if it becomes unused; it remains needed only for any `_review_common.load_config(wiki_path, mill_dir)` call still using the old signature (left unchanged in this card).
- **Commit:** `refactor(review-cli): pass git_root/wiki_path/cfg to find_active_slug`

### Card 13: update `test-review-common.py` and review-flow tests

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-review-common.py`: drop the `_active.write(...)` setup pattern; replace each `find_active_slug(<mill_dir>)` call with `find_active_slug(git_root, wiki_path, cfg)` and use `_test_helpers._make_task_worktree` to set up state. The "empty dir → ReviewError" test (around line 195) becomes "non-task branch → ReviewError" (since the new path raises `MarkerError → ReviewError` on `slug_from_branch` failure). The "load_task_title with task_title in active marker" test (around line 213) becomes a Home.md-driven test using `_make_task_worktree`. Drop the slug-mismatch assertion at lines 292-294 (or rewrite to construct a worktree-on-different-branch state and assert `ActiveWorktreeSlugMismatch` from the `_paths.resolve_active_*` helpers). In each of the three flow tests: drop `_active.write(...)` calls (around lines 40, 110, 104, 265, 324, 451, 661); replace with `_make_task_worktree` setup. Each flow test's existing assertions about review outputs should pass once the setup uses the new state-building.
- **Commit:** `test(review): use branch+Home.md fixtures via _make_task_worktree`

### Card 14: update `test-millpy-validate-plan.py` mock targets

- **Context:**
  - `plugins/mill/scripts/millpy-validate-plan.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update each `mock.patch("_review_common.find_active_slug", return_value=slug)` (around lines 115, 157, 215, 270) so the patched target signature accepts the new arguments. The patch return-value stays `slug`; the test setup just needs to ensure the call is reachable. If any test passes positional args to `find_active_slug` that asserted the old call shape, update those assertions. No production-side change here.
- **Commit:** `test(validate-plan): update find_active_slug mock for new signature`

### Card 15: update `millpy-spawn.py` to drop `write_active_marker` call

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Delete the `_spawn_core.write_active_marker(...)` call at lines 230-236 (the entire 7-line block). The surrounding `ts` variable is still needed for `write_initial_status` (line 251) and `write_wiki_active_task_md` (line 207); leave it. The bootstrap stub block at lines 240-246 (which writes `<worktree_root>/.millhouse/config.local.yaml`) is unrelated to the active marker and stays untouched. Update the module docstring's flow description (lines 4-19) so step 7 no longer mentions writing the active marker; renumber/condense the step list so step 9 (`write_initial_status`) is the only post-junctions write.
- **Commit:** `refactor(spawn): stop writing active.slug.md marker`

### Card 16: update `millpy-claim.py` to drop `write_active_marker` call

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Delete the `_spawn_core.write_active_marker(...)` call at lines 300-306 (and the comment at line 299 above it: `# Write the per-worktree active marker so downstream skills find this task.`). The `mill_dir` local variable defined elsewhere in the file remains needed by other operations (verify by searching the file for `mill_dir` after the edit); do not delete it. The `ts` variable is still used by `write_initial_status` and other calls; leave it.
- **Commit:** `refactor(claim): stop writing active.slug.md marker`

### Card 17: update `test-millpy-spawn.py` and `test-millpy-claim.py` to drop marker assertions

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-millpy-spawn.py`: remove every `spawn_core_mock.write_active_marker.return_value = None` line (lines 128, 279, 488); remove the `sc.write_active_marker.assert_called_once()` assertions and the surrounding marker-call introspection (lines 213-224); update the docstring at line 203 (`write_active_marker, write_initial_status in that order`) to drop the `write_active_marker` reference. Delete `_fake_write_active_marker_real` (lines 647 onwards) and its `side_effect` assignment (line 704). Drop the marker-existence assertions at lines 793-798 and 861-867. Adjust the test at line 943 (the manual marker write `(dest_hub / ".millhouse" / "active.slug.md").write_text(...)`) — the test was simulating spawn-failure; rewrite the test setup to omit the marker write entirely and verify the test still validates whatever it was checking (likely a stub-config assertion). At line 972 (`real_sc.discover_active_worktrees(worktrees)`) update to the new signature: pre-build `home_tasks` and `branch_prefix` and pass them in. In `test-millpy-claim.py`: every `sc.write_active_marker.return_value = None` (lines 210, 330, 395, 449, 509, 569, 624, 680) is removed. Every `sc.write_active_marker.assert_called_once()` and `sc.write_active_marker.call_args` assertion (lines 237, 252-254, 428-431, 717-722) is removed along with the surrounding lines that introspect the call. Update the file docstring at lines 6 and 196 (`Happy path calls claim_in_wiki, write_active_marker, write_initial_status`) to drop the `write_active_marker` reference.
- **Commit:** `test(spawn,claim): drop write_active_marker mock assertions`

### Card 18: update discovery callers to pass `home_tasks` and `branch_prefix`

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/millpy-inspect.py`
  - `plugins/mill/scripts/millpy-migrate-layout.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each of the five files, before the `_spawn_core.discover_active_worktrees(...)` call, ensure `home_tasks` and `branch_prefix` are loaded. `home_tasks` is loaded as `home_tasks = _tasks_md.parse((wiki_path / "Home.md").read_text(encoding="utf-8"))` (where `wiki_path = _paths.resolve_wiki_path(git_root)` if not already in scope). `branch_prefix` is `cfg.get("spawn", {}).get("branch_prefix", "")` — the file must load cfg via the same path the file currently uses (or via `_review_common.load_config(wiki_path, mill_dir)` / equivalent). Then update each call site to pass the three arguments: `_spawn_core.discover_active_worktrees(worktrees_dir, home_tasks, branch_prefix)`. Specific call sites: `millpy-vscode.py:100` and `:110`; `millpy-terminal.py:59` and `:66`; `millpy-status.py:34`; `millpy-inspect.py:48`; `millpy-migrate-layout.py:227`. In `millpy-inspect.py`, the existing Home.md parse at line 64 can be hoisted above line 48 to feed the discover call (the current later parse fed `home_marker_map`; reuse the same parsed list). Update each file's module docstring if it mentions the marker file or the old signature.
- **Commit:** `refactor(discovery-callers): pass home_tasks and branch_prefix to discover_active_worktrees`

### Card 19: update `test-millpy-vscode.py` and `test-millpy-terminal.py`

- **Context:**
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
  - `plugins/mill/unit_tests/test-millpy-terminal.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace each `_write_active_marker(...)` setup helper call (around lines 64, 65, 108, 111, 112, 151, 190, 227, 285 across both files) with state built via `_make_task_worktree` or by writing a Home.md and creating a per-worktree branch directly. The patched discover return shape `(path, slug, title)` stays the same. The `patch("mill_<x>._spawn_core.discover_active_worktrees", return_value=[])` lines (e.g. `test-millpy-terminal.py:156, 331, 380`; `test-millpy-vscode.py:329, 378, 413, 447, 477`) keep their patch path; the patched function returns the same tuple shape, so test assertions don't need to change. Delete the local `_write_active_marker` function definition at the top of each test file (around line 36 in both). Drop `import _active` from both test files. Tests that exercise the discover-on-real-state path (vs the mocked path) need the real flow to work with `_make_task_worktree`; verify those still set up Home.md + branched git repos.
- **Commit:** `test(vscode,terminal): replace marker-write fixtures with _make_task_worktree`

### Card 20: rewrite `millpy-cleanup.py` (hub-check, in-place resolver, marker delete, discover ordering)

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Five distinct rewrites in this single file, all reaching the new APIs:
  1. **Hub-check (line 471).** Replace `if (Path.cwd() / ".millhouse" / "active.slug.md").exists():` with: get current branch via `_subprocess_util.run(["git", "-C", str(Path.cwd()), "branch", "--show-current"])`; capture `branch = result.stdout.strip()`; load Home.md tasks via the same `_tasks_md.parse((wiki_path / "Home.md").read_text(encoding="utf-8"))` pattern as elsewhere; strip `branch_prefix = cfg.get("spawn", {}).get("branch_prefix", "")` from the branch; if the resulting slug is in Home.md as `phase == "active"`, exit with the same `Error: mill-cleanup must run from the hub, not from a worktree.` message. NOTE: this hub-check fires before `cfg` and `wiki_path` are resolved further down in `main()`; either hoist those resolutions above the check (preferred — they're cheap), or reorder so the check runs after resolution. Pick the hoist approach.
  2. **`build_plan` marker-data block (lines 102-119).** The loop reads the active marker's `slug` and `branch` per worktree. Replace with: derive `slug` from each `wt_path`'s checked-out branch via `_subprocess_util.run(["git", "-C", str(wt_path), "branch", "--show-current"])`, strip `branch_prefix`, look up in `home_tasks` (already in scope at line 89: `marker_by_slug = {t.slug: t.phase for t in home_tasks}` — adjust to also keep the full Task list). Skip the worktree (continue) when branch is empty, prefix doesn't match, or slug isn't in `home_tasks`. Drop the stub-read block at lines 103-110 entirely. Drop the `_active.read_all(hub_mill_dir)` call. Set `branch = branch_proc.stdout.strip()` directly.
  3. **`_resolve_inplace_mode` marker read (line 246).** Replace `_active.read_all(hub_root / ".millhouse")` with: derive `slug_for_record = _marker.slug_from_branch(hub_root, wiki_path, cfg)` wrapped in `try/except _marker.MarkerError: return ("worktree", "")`. The `task_branch = active_data.get("branch", "")` line becomes `task_branch = subprocess capture of "git branch --show-current"`. The subsequent `_inplace.is_inplace(active_data, hub_root, cfg)` becomes `_inplace.is_inplace(record.slug, hub_root, cfg)`. Pass `wiki_path` and `cfg` into `_resolve_inplace_mode` if they aren't already in scope (verify against the function signature). The `prompt_stale_worktree` branch (line 266) keeps its existing logic.
  4. **In-place marker delete (line 362).** Delete the entire `marker_path = hub_root / ".millhouse" / "active.slug.md"; if marker_path.exists(): marker_path.unlink(); print(...)` block in `_apply_inplace_record`. The `# Remove the active marker file.` comment goes too.
  5. **Discover-ordering at line 480.** Hoist the `home_text = (wiki_path / "Home.md").read_text("utf-8"); home_tasks = _tasks_md.parse(home_text)` block (currently at lines 483-484) to ABOVE the `_spawn_core.discover_active_worktrees(...)` call (line 480). Then update the call to `_spawn_core.discover_active_worktrees(container_path / "wts", home_tasks, cfg.get("spawn", {}).get("branch_prefix", ""))`. The `cfg` resolution at line 487 must be hoisted similarly so `branch_prefix` is in scope at the discover call.
  Drop `import _active` if it becomes unused. Add `import _marker` if needed by `_resolve_inplace_mode`.
- **Commit:** `refactor(cleanup): branch+Home.md throughout; drop marker reads, writes, and delete`

### Card 21: update `test-cleanup.py` for cleanup rewrite

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the `_write_active_marker(wt_path, slug, branch)` helper at line 51 with a per-worktree branch checkout via `git checkout -b <branch>` (or use `_make_task_worktree`). Every callsite that uses the helper (lines 121, 149, 175, 196, 218, 237, 295, 645, 674, 703, 774, 802) becomes a "create real git repo + checkout task branch + write Home.md entry" sequence. Drop the marker-deletion assertions at lines 384-386 and 631-633 (`Expected active.slug.md to be deleted`); replace with the inverse — assert no marker file exists at the start, after cleanup the `<wts>/<slug>/` directory is gone (existing assertion). Update the `(mill_dir / "active.slug.md").write_text(f"slug: {slug}\n", encoding="utf-8")` line at 741 to a no-op (or replace with the equivalent branch+Home.md setup). Drop `_active.write(...)` calls at lines 320, 552. Update mocks of `mill_cleanup._inplace.prompt_stale_worktree` (line 586) — patch path stays the same since `_inplace` module is unchanged. Drop `import _active` if unused after the refactor. Verify each test still exercises its target scenario after the fixture change.
- **Commit:** `test(cleanup): replace marker fixtures with branch+Home.md state`

### Card 22: update `millpy-abandon.py`, `millpy-color.py`, `millpy-implement.py`, `millpy-implement-holistic.py`, `millpy-merge-in-subagent.py`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/millpy-color.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each file, replace `import _active` with `import _marker`. Replace `_active.read_slug(mill_dir)` with `_marker.slug_from_branch(git_root, wiki_path, cfg)` (each script already resolves `git_root`/`wiki_path`/`cfg` before the call; verify per file). Replace `except _active.ActiveError as exc:` with `except _marker.MarkerError as exc:`. Specific call sites: `millpy-abandon.py:40` (the existence-check `if not (mill_dir / "active.slug.md").exists()` becomes a try/except around `_marker.slug_from_branch` returning sys.exit on failure; combine with the `try: slug = _active.read_slug(mill_dir)` at line 45 into a single try/except); `millpy-color.py:97` (the `try/except _active.ActiveError: pass` swallow becomes `try/except _marker.MarkerError: pass`); `millpy-implement.py:87` (replace direct call); `millpy-implement-holistic.py:72` (replace direct call); `millpy-merge-in-subagent.py:84` (replace existence-check call). Update each file's module docstring if it mentions the marker file. Drop the now-unused `mill_dir = ... / ".millhouse"` line in any script that used it only for `_active.read_slug` (verify each file individually after the change).
- **Commit:** `refactor(consumers): switch _active.read_slug callers to _marker.slug_from_branch`

### Card 23: update tests for the consumer scripts in card 22

- **Context:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/millpy-color.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-abandon.py`
  - `plugins/mill/unit_tests/test-millpy-color.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-abandon.py`: drop the `(mill_dir / "active.slug.md").write_text(f"slug: {slug}\n", ...)` lines (46, 259) and the `_active.write(...)` calls (47, 103, 260) — replace with `_make_task_worktree` setup or equivalent inline branch+Home.md state. The "(b) hub check: no active.slug.md" test (lines 167-176) becomes "(b) hub check: not on a task branch" — set up an empty git repo with `main` branch and verify mill-abandon exits non-zero. Drop `import _active` if unused. In `test-millpy-color.py` / `test-millpy-implement.py` / `test-millpy-implement-holistic.py`: each file currently uses `mock.patch` to stub `_active` access. Update the patch target from `mill_color._active` (or whichever `<script>._active`) to `mill_color._marker` (matching the production-side import change in card 22). Replace `_active.ActiveError` references with `_marker.MarkerError` inside test setup (the patched module's exception type). In `test-millpy-merge-in-subagent.py`: drop the `(millhouse_dir / "active.slug.md").write_text("test-slug", ...)` line (41) and replace with branch+Home.md setup. Drop `import _active` if unused. Each test's existing assertions should pass once setup uses the new state-building.
- **Commit:** `test(consumers): adapt to _marker.slug_from_branch via real branch+Home.md`

### Card 24: delete `_active.py` and `test-active.py`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_active.py`
  - `plugins/mill/unit_tests/test-active.py`
- **Requirements:** Delete both files. Before deletion, verify (via `grep -r "import _active" plugins/mill/`) that no source file in `plugins/mill/scripts/` or `plugins/mill/unit_tests/` still imports `_active`. The integration tests under `plugins/mill/integration_tests/` are updated separately in Batch 3 — they import `_active` today but `run-all.py` does NOT discover them, so deletion in this card does not break Batch 2's verify. After deletion, the unit test suite must still pass via `run-all.py`.
- **Commit:** `refactor: delete _active module and test-active.py`

### Card 25: drop `_yaml_writer.quote_scalar` import in `_active.py` … (placeholder removed)

This card number is reserved to keep card numbering monotonic; no work is required.

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Requirements:** Skip — implementer takes no action for card 25. Card numbering preserved for downstream integrity.
- **Commit:** none

### Card 26: documentation review of internal docstrings updated by this batch

- **Context:**
  - `plugins/mill/scripts/_marker.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Each module's top-level docstring may still reference `active.slug.md`, `_active`, the marker file, `write_active_marker`, or the old signatures from steps above. Sweep each docstring (the `"""…"""` block at the top of each module) and update prose to reference `_marker` and the new signatures. Specifically: `_paths.py`'s `resolve_active_worktree` docstring (lines 56-65); `_inplace.py`'s module docstring (`Public API:` block); `_spawn_core.py`'s module docstring's `Public API` listing; `_review_common.py`'s module docstring lines 14-15; `millpy-spawn.py`'s flow description (lines 4-19); `millpy-claim.py`'s comment at line 299; `millpy-cleanup.py`'s docstring lines 75 (reference to `discover_active_worktrees`) and 79, 225, 290 (active marker references). No code changes in this card — docstrings only.
- **Commit:** `docs: update module docstrings post-_active removal`

## Batch Tests

`verify` = `python plugins/mill/unit_tests/run-all.py`. The full unit suite must pass. Specific tests covering the changes in this batch:

- `test-marker.py` (added in Batch 1, exercised here transitively).
- `test-paths.py` — `resolve_active_worktree` / `resolve_active_hub` happy path, in-place hit, slug-mismatch (`ActiveWorktreeSlugMismatch`), not-found (`ActiveWorktreeNotFound`).
- `test-inplace.py` + `test-mill-merge-inplace.py` — `is_inplace` simplified signature.
- `test-spawn-core.py` — `discover_active_worktrees` new signature, multiple-phase Home.md tasks, subfolder-install layout via branch.
- `test-review-common.py` + flow tests — `find_active_slug` / `load_task_title` via branch+Home.md.
- `test-millpy-validate-plan.py` — `find_active_slug` mock signature parity.
- `test-millpy-spawn.py` + `test-millpy-claim.py` — spawn/claim flow without marker writes.
- `test-millpy-vscode.py` + `test-millpy-terminal.py` — discovery callers with `home_tasks` + `branch_prefix`.
- `test-cleanup.py` — full cleanup flow (hub-check, in-place mode, worktree mode, marker-delete absent).
- `test-abandon.py`, `test-millpy-color.py`, `test-millpy-implement.py`, `test-millpy-implement-holistic.py`, `test-millpy-merge-in-subagent.py` — direct consumer migrations.
- `test-active.py` is deleted; its test surface is subsumed by `test-marker.py`.

The integration tests under `plugins/mill/integration_tests/` are NOT exercised by `run-all.py`. They are updated in Batch 3 to keep them runnable, but their breakage during Batch 2 does not block the verify.
