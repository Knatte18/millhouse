# Batch: config-resolution-fixes-fix-and-merge

```yaml
task: "Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps"
batch: "config-resolution-fixes-fix-and-merge"
number: 4
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py test-merge-in-subagent.py"
depends-on: []
```

## Batch Scope

Second half of the #728 fix (see `03-config-resolution-fixes-implement-and-small.md` for the first half; the two batches were split from one oversized batch to stay under `pipeline.max_batch_context_tokens` -- `millpy-fix.py`'s own unit test file alone is ~1990 lines). Covers `millpy-fix.py` and `millpy-merge-in-subagent.py`: both call `_review_common.load_config(...)` with the outer git-repo root instead of the resolved hub root, and both reload a stale `cfg` after their own later, more-precise `_paths.resolve_active_hub()` root correction, per `cfg-reload-after-active-hub`. `millpy-merge-in-subagent.py` additionally needs its `project_root` computation itself fixed (it is `Path.cwd()` today, not hub-rooted at all), per `load-config-fix-mechanics`. Each card pairs one script's fix with its own regression-test extension. Independent of every other batch in this plan (no shared files).

External interface: neither of these two files is imported by any other file in this task's scope -- each is a standalone CLI entrypoint. No downstream batch depends on this one.

## Cards

### Card 15: `millpy-fix.py` -- load_config root fix + cfg reload after resolve_active_hub

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `millpy-fix.py:297` from `cfg = _review_common.load_config(git_root, mill_dir)` to `cfg = _review_common.load_config(project_root, mill_dir)` (arg1: `project_root`, already computed at line 290 via `_paths.resolve_hub_path()`). After line 329 (`mill_dir = project_root / ".millhouse"`, following the `_paths.resolve_active_hub()` call at lines 326-328), insert `cfg = _review_common.load_config(project_root, mill_dir)` -- a reload against the corrected root, placed before any of the file's downstream `cfg` reads (~lines 340, 342, 343, 359, 378, 628) so all of them observe the reloaded value. `_review_common.load_config(hub_root: Path, mill_dir: Path) -> dict` is the function signature (already imported in this file as `_review_common`). Extend `plugins/mill/unit_tests/test-millpy-fix.py` with the same two fixture shapes as `millpy-implement.py`'s fix (see `03-config-resolution-fixes-implement-and-small.md` Card 12 for the reference pattern): a hub-in-subdirectory fixture asserting the resolved `cfg` reflects the hub's own `spawn.branch_prefix`; and a bootstrap-vs-corrected-root-divergence fixture asserting the fixer's model/timeout/self-fix-rounds values downstream logic observes come from the reloaded config.
- **Commit:** `fix(fix): load_config uses hub root, cfg reloaded after resolve_active_hub`

### Card 16: `millpy-merge-in-subagent.py` -- fix project_root definition, call-site argument swap, cfg reload

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file needs two changes together (neither alone is sufficient -- see `discussion.md`'s `load-config-fix-mechanics`). First, fix `project_root = Path.cwd()` (line 337) to `project_root = _paths.resolve_hub_path()` -- cwd is not hub-rooted here today. Second, change line 345 from `cfg = _review_common.load_config(git_root, mill_dir)` to `cfg = _review_common.load_config(project_root, mill_dir)` -- today `git_root` (the outer git-repo root, computed at line 341) is passed as arg1, and `project_root` only feeds `mill_dir`; fixing only the `project_root` definition without also swapping this call's argument would leave arg1 as the outer git-repo root, the exact #728 bug pattern, unfixed. After line 360 (`mill_dir = project_root / ".millhouse"`, following the `_paths.resolve_active_hub()` call at lines 357-359), insert a reload: `cfg = _review_common.load_config(project_root, mill_dir)`, so downstream consumers (verify-cwd resolution, conflict handling, finalize dispatch) observe the corrected config. Extend `plugins/mill/unit_tests/test-merge-in-subagent.py` (which loads the module via `importlib` and patches `_paths`/`_review_common` functions with `unittest.mock` -- follow that established style) with: a hub-in-subdirectory fixture asserting the resolved `cfg` reflects the hub's own `spawn.branch_prefix`; a bootstrap-vs-corrected-root-divergence fixture asserting the merge model/timeout values downstream logic observes come from the reloaded config, not the bootstrap one.
- **Commit:** `fix(merge-in-subagent): project_root is hub-rooted, load_config uses it, cfg reloaded after resolve_active_hub`

## Batch Tests

`verify:` runs the two per-script unit test files this batch extends: `test-millpy-fix.py`, `test-merge-in-subagent.py`. Both new hub-in-subdirectory fixtures directly regression-guard the #728 failure mode, and both assert the *reloaded* config -- not the bootstrap one -- is what real hub-config-controlled downstream values actually observe, per `cfg-reload-after-active-hub`.
