# Batch: callsite-refactor

```yaml
task: (A) -- Add status_md to paths config + refactor 14 callsites
batch: callsite-refactor
number: 2
cards: 5
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
depends-on: [1]
```

## Batch Scope

This batch rewires every status.md call site in `plugins/mill/scripts/` to flow through `_paths.status_path` (the helper added in batch 1). It fixes three real bugs along the way -- `millpy-inspect.py:77` and `millpy-status.py:49` build `wt_path / "status.md"` (missing the `_mill/` segment, which is why `mill-inspect` reports `(no active tasks)` today), and `_review_code.py:220` calls `resolve_path("status.md", slug)` which is not a valid invocation of that function. It also threads `cfg` through `_spawn_core.write_initial_status` so the writer side stops hardcoding `_mill/status.md`. All other call sites that already route through `_paths.resolve_task_path(wt, "_mill/status.md")` get migrated to `_paths.status_path(wt, cfg)` for uniformity -- one helper name for one concept across the codebase.

Card 4 is the largest piece (3 files, signature change to `write_initial_status` plus the two callers). Cards 5-7 each fix a single-file bug. Card 8 is a mechanical uniformity sweep across four already-correct call sites. The cards are decoupled at the file level so a review finding on one card does not force re-work across the rest. After this batch lands, `mill-inspect` and `mill-status` work again, the latent `_review_code.py:220` bug is dead, the writer side reads from cfg, and the codebase has exactly one helper for resolving the status.md path.

## Cards

### Card 4: Thread `cfg` through `_spawn_core.write_initial_status` and its callers

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/_spawn_core.py`, modify `write_initial_status` (current signature at line 672: `write_initial_status(worktree_path, slug, title, ts, parent_branch, branch)`) by appending a required `cfg: dict` keyword-only parameter -- new signature: `write_initial_status(worktree_path, slug, title, ts, parent_branch, branch, *, cfg: dict)`. Inside the function body, replace the hardcoded path build at line 716 (`status_abs = worktree_path / "_mill" / "status.md"`) with `status_abs = _paths.status_path(worktree_path, cfg)` and replace the hardcoded git-add path at line 720 (`["git", "-C", str(worktree_path), "add", "_mill/status.md"]`) with the same path computed relative to `worktree_path`: `["git", "-C", str(worktree_path), "add", status_abs.relative_to(worktree_path).as_posix()]`. Update the function's docstring Args block to document the new `cfg` parameter (one-line: `cfg: Loaded mill config dict; supplies cfg["paths"]["status_md"] to _paths.status_path.`). Update the module-level "Public API:" docstring entry for `write_initial_status` to reflect the new signature.
  - In `plugins/mill/scripts/_spawn_core.py`, add `import _paths` to the imports block if not already present (check the existing imports near the top of the file -- `_status` is imported, `_paths` may or may not be; add it where alphabetic order places it).
  - In `plugins/mill/scripts/millpy-spawn.py`, update the call at line 240 (`status_abs = _spawn_core.write_initial_status(...)`) to pass `cfg=cfg` as the new keyword argument. The `cfg` local is already available in the calling scope earlier in `main` -- verify by reading the function. Also update the dry-run print at line 165 (`print(f"[DryRun] Status:   {worktree_path / '_mill' / 'status.md'}")`) to read `print(f"[DryRun] Status:   {_paths.status_path(worktree_path, cfg)}")`. Add `import _paths` to the imports block if not already present.
  - In `plugins/mill/scripts/millpy-claim.py`, update the call at line 300 (`status_abs = _spawn_core.write_initial_status(...)`) to pass `cfg=cfg` as the new keyword argument (verify `cfg` is in scope; load via the standard `_config.load_config(...)` pattern earlier in `main` if needed -- read the file to confirm). Also update the dry-run print at line 216 (`print(f"[DryRun] Status:  {resolve_hub_path() / '_mill' / 'status.md'}")`) to read `print(f"[DryRun] Status:  {_paths.status_path(resolve_hub_path(), cfg)}")`. Add `import _paths` (or change `from _paths import resolve_hub_path` to also pull `_paths` as a module) so the helper call resolves. ASCII-only per the overview's `ascii-only-log-strings` decision.
  - All three files: do not change any other functions or call sites. Each file's edit is scoped to the write-side path resolution and the two `write_initial_status` call sites; read-side call sites (e.g. status reads in `mill-inspect`, `mill-status`, etc.) are out of scope for this card -- they are handled in cards 5, 6, 7, 8.
- **Commit:** `refactor(spawn): thread cfg through write_initial_status; use _paths.status_path`

### Card 5: Fix `millpy-inspect.py` status-path bug

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-inspect.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/millpy-inspect.py`, replace line 77 (`sp = wt_path / "status.md"`) inside the `_collect` function's per-slug loop with `sp = _paths.status_path(wt_path, cfg)`. The `cfg` local is already in scope from line 47 (`cfg = _config.load_config(wiki, git_root)`); `_paths` is already imported (line 17). This is the root cause of `mill-inspect` reporting `(no active tasks)` for worktrees that actually hold a valid `_mill/status.md`.
  - Do not change anything else in the file. No other status.md reference exists in `millpy-inspect.py`.
- **Commit:** `fix(inspect): resolve status.md via _paths.status_path (was wt_path/'status.md')`

### Card 6: Fix `millpy-status.py` status-path bug

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/millpy-status.py`, replace line 49 (`sp = wt_path / "status.md"`) inside `_build_rows`'s per-slug loop with `sp = _paths.status_path(wt_path, cfg)`. The `cfg` local is already in scope from line 26 (`cfg = _config.load_config(wiki, git_root)`); `_paths` is already imported (line 17). Same shape of bug as card 5 -- the `wt_path / "status.md"` build misses the `_mill/` segment and silently feeds `None` (from the swallowed `ValueError`) into the status table column.
  - Do not change anything else in the file.
- **Commit:** `fix(status): resolve status.md via _paths.status_path (was wt_path/'status.md')`

### Card 7: Fix `_review_code.py` status-path bug + import

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/scripts/_review_code.py`, replace line 220 (`status_path = resolve_path("status.md", slug)`) with `status_path = _paths.status_path(project_root, cfg)`. Both `project_root` and `cfg` are already in scope at this call site (the function is invoked with both available; verify by reading the surrounding function signature). The current call is broken: `resolve_path`'s signature is `(role, repo_root)`, so passing `"status.md"` and `slug` is a category error that would raise at runtime if this branch were ever reached on a fresh `_review_code` invocation with `batch_name` set.
  - Add `import _paths` to the imports block at the top of the file. The current imports pull `resolve_path` from `_review_common` (lines 38-60 of the file). Add `import _paths` as a top-level module import alongside the other module imports near the top of the file. Do not remove `resolve_path` from the `_review_common` import block -- lines 189 and 190 still use it for `plan_dir` and `reviews_dir`.
  - Do not change any other call site in the file. Lines 189-190's `resolve_path` calls are out of scope for this task (they operate on different cfg keys and a different role contract).
- **Commit:** `fix(review): resolve status.md via _paths.status_path (was broken resolve_path call)`

### Card 8: Migrate already-correct call sites to `_paths.status_path` for uniformity

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Mechanical substitution across four files: replace every call of the form `_paths.resolve_task_path(<wt-expr>, "_mill/status.md")` with `_paths.status_path(<wt-expr>, cfg)`. The replacements are:
    - `plugins/mill/scripts/millpy-abandon.py` line 58: `status_path = _paths.resolve_task_path(active_hub, "_mill/status.md")` -> `status_path = _paths.status_path(active_hub, cfg)`. Verify `cfg` is in scope earlier in `main` (loaded via `_config.load_config`); if absent, add the load. Do not change any other line.
    - `plugins/mill/scripts/millpy-cleanup.py` line 130 (inside `build_plan`'s active-worktree iteration loop): `_paths.resolve_task_path(wt_path, "_mill/status.md")` -> `_paths.status_path(wt_path, cfg)`. `build_plan`'s current signature (line 73) does not carry `cfg`; rather than thread cfg through `build_plan` (which would require updating the lone caller at line 619-ish in `main` plus `test-cleanup.py`'s call expectations), load it inside `build_plan` via `cfg = _load_config(wiki_path, hub_root)` -- the helper `_load_config` already exists in this file (referenced at line 592 in `main`). `_load_config` lives in `millpy-cleanup.py` itself (search for `def _load_config` near the top of the file). No new `_config` import is needed.
    - `plugins/mill/scripts/millpy-cleanup.py` line 325 (inside `_apply_inplace_record` at line 302): `_paths.resolve_task_path(record.worktree_path, "_mill/status.md")` -> `_paths.status_path(record.worktree_path, cfg)`. Thread `cfg: dict` as a keyword argument through `_apply_inplace_record`'s signature -- new signature: `_apply_inplace_record(record, hub_root, task_branch="", *, cfg: dict)`. Update both call sites: line 520 (inside `_apply_pr_reap_record`) and line 549 (inside `apply_plan`) -- both already have `cfg` in scope (apply_plan loads it at line 535-ish; `_apply_pr_reap_record` must receive it via the same keyword-arg pattern if it isn't there yet -- verify by reading the function and add `cfg` to its signature if needed, updating its caller in `apply_plan` accordingly).
    - `plugins/mill/scripts/millpy-cleanup.py` line 353 (also inside `_apply_inplace_record`): `_paths.resolve_task_path(record.worktree_path, "_mill/status.md")` -> `_paths.status_path(record.worktree_path, cfg)`. Uses the same `cfg` keyword arg added by the line-325 change; no additional threading needed.
    - `plugins/mill/scripts/millpy-implement.py` line 93: `status_path = _paths.resolve_task_path(project_root, "_mill/status.md")` -> `status_path = _paths.status_path(project_root, cfg)`. Verify `cfg` is in scope.
    - `plugins/mill/scripts/millpy-implement-holistic.py` line 77: same shape -> `_paths.status_path(project_root, cfg)`. Verify `cfg` in scope.
  - Each substitution is a one-liner. No behaviour change is intended -- `_paths.status_path` returns identical paths to `_paths.resolve_task_path(wt, "_mill/status.md")` for the same input (the helper is literally a wrapper that supplies `cfg["paths"]["status_md"]` as the second argument). The compat fallback continues to fire for in-flight worktrees whose state still lives under `task/`.
  - If any file's `cfg` is not in scope at the call site, load it via the standard pattern (`cfg = _config.load_config(wiki, git_root)`) and add `import _config` if missing. Do not introduce a new pattern -- match the existing per-file conventions.
- **Commit:** `refactor(callsites): migrate _paths.resolve_task_path(_, "_mill/status.md") -> _paths.status_path`

## Batch Tests

Verify command: `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. The existing test suite covers `_status.py`, `_paths.py`, `_spawn_core.py` (via `test-spawn.py`), `millpy-cleanup.py` (via `test-cleanup.py`), `millpy-abandon.py` (via `test-abandon.py`), `millpy-implement.py` (via `test-millpy-implement.py`), `millpy-implement-holistic.py` (via `test-millpy-implement-holistic.py`), and `millpy-claim.py` (via `test-millpy-claim.py`). These tests already exercise the call sites this batch touches; any regression in the refactor should surface there. The new `test-paths-status.py` from batch 1 still passes (no changes to the helper). No new test surface is added in this batch -- the refactor is mechanical and the contract is unchanged.
