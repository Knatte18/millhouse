# Batch: config-resolution-fixes

```yaml
task: "Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps"
batch: "config-resolution-fixes"
number: 3
cards: 5
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py test-millpy-fix.py test-abandon.py test-merge-in-subagent.py test-millpy-validate-plan.py"
depends-on: []
```

## Batch Scope

Closes #728: `millpy-implement.py`, `millpy-fix.py`, `millpy-abandon.py`, and `millpy-merge-in-subagent.py` each call `_review_common.load_config(...)` with the outer git-repo root instead of the resolved hub root, silently missing the hub's own `mill-config.yaml` whenever the hub lives in a subdirectory of the git repo. `millpy-validate-plan.py` has the inverse-shaped instance of the same bug, discovered during investigation and included per `discussion.md`'s `load-config-validate-plan-included` decision. Four of the five files (all but `validate-plan`) additionally reload a stale `cfg` after their own later, more-precise `_paths.resolve_active_hub()` root correction, per `cfg-reload-after-active-hub`. Each card pairs one script's fix with its own regression-test extension, since the fix and its fixture are the same unit of review. This batch is independent of Batches 1 and 2 (no shared files, no `wiki/` or `mill-resume` involvement).

External interface: none of these five files are imported by any other file in this task's scope — each is a standalone CLI entrypoint invoked by `mill-go`/`mill-plan`. No downstream batch depends on this one.

## Cards

### Card 12: `millpy-implement.py` -- load_config root fix + cfg reload after resolve_active_hub

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `millpy-implement.py:236` from `cfg = _review_common.load_config(git_root, mill_dir)` to `cfg = _review_common.load_config(project_root, mill_dir)` (arg1: `project_root`, already computed at line 229 via `_paths.resolve_hub_path()` -- the bootstrap hub root, not the outer git-repo root `git_root`). After line 285 (`mill_dir = project_root / ".millhouse"`, the recomputation immediately following the `_paths.resolve_active_hub()` call at lines 282-284), insert `cfg = _review_common.load_config(project_root, mill_dir)` -- a reload against the corrected root, placed **before** line 287's `plan_dir = cfg.get("paths", {}).get("plan_dir", "_mill/plan/")` read so that `plan_dir` (287), `self_fix_rounds` (~325), `implementer_cfg`/`model_name` (~327-328), and `timeout` (~337) all observe the reloaded value instead of the stale bootstrap one. Extend `plugins/mill/unit_tests/test-millpy-implement.py`: (1) a hub-in-subdirectory fixture (mirroring issue #728's NORCE.Models repro -- `mill-config.yaml` lives in a subdirectory of the git root, not at the root) asserting `main()`'s resolved `cfg` contains the hub's own distinctive `spawn.branch_prefix` value rather than a template/primary-clone fallback; (2) a fixture where the bootstrap-resolved root and the `resolve_active_hub()`-resolved root genuinely differ, asserting that `self_fix_rounds`/`model_name`/`timeout` as actually used downstream come from the **reloaded** config, not the bootstrap one (e.g. patch `_paths.resolve_active_hub` to return a second fixture directory carrying a distinctly different `roles.implementer.model` value than the bootstrap directory's config, and assert the implementer dispatch uses the second value).
- **Commit:** `fix(implement): load_config uses hub root, cfg reloaded after resolve_active_hub`

### Card 13: `millpy-fix.py` -- load_config root fix + cfg reload after resolve_active_hub

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `millpy-fix.py:297` from `cfg = _review_common.load_config(git_root, mill_dir)` to `cfg = _review_common.load_config(project_root, mill_dir)` (arg1: `project_root`, already computed at line 290 via `_paths.resolve_hub_path()`). After line 329 (`mill_dir = project_root / ".millhouse"`, following the `_paths.resolve_active_hub()` call at lines 326-328), insert `cfg = _review_common.load_config(project_root, mill_dir)` -- a reload against the corrected root, placed before any of the file's downstream `cfg` reads (~lines 340, 342, 343, 359, 378, 628) so all of them observe the reloaded value. Extend `plugins/mill/unit_tests/test-millpy-fix.py` with the same two fixture shapes as Card 12: a hub-in-subdirectory fixture asserting the resolved `cfg` reflects the hub's own `spawn.branch_prefix`; and a bootstrap-vs-corrected-root-divergence fixture asserting the fixer's model/timeout/self-fix-rounds values downstream logic observes come from the reloaded config.
- **Commit:** `fix(fix): load_config uses hub root, cfg reloaded after resolve_active_hub`

### Card 14: `millpy-abandon.py` -- load_config root fix + cfg reload after resolve_active_hub

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_builder_lock.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/unit_tests/test-abandon.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `millpy-abandon.py:42` from `cfg = _review_common.load_config(git_root, mill_dir)` to `cfg = _review_common.load_config(hub_dir, mill_dir)` (arg1: `hub_dir`, already computed at line 40 via `_paths.resolve_hub_path()`). After line 55 (the `active_hub = _paths.resolve_active_hub(...)` call spanning lines 53-55), insert a recomputation of `mill_dir = active_hub / ".millhouse"` and a reload `cfg = _review_common.load_config(active_hub, mill_dir)` -- mirroring the mill_dir-recomputation-plus-reload pattern in Cards 12/13. This corrected `mill_dir` also becomes what `_builder_lock.read(mill_dir)` (~line 75) reads from, and the reloaded `cfg` is what `_status.read_branch(status_path, cfg=cfg, slug=slug)` (~line 114) uses for branch resolution -- both currently read the stale bootstrap `cfg`/`mill_dir`. Extend `plugins/mill/unit_tests/test-abandon.py` (which uses a trampoline subprocess pre-patching `sys.modules` with mock `_paths`/`_marker`/`_review_common`/`_subprocess_util` -- follow that same mocking style) with: a hub-in-subdirectory fixture asserting the resolved `cfg` reflects the hub's own `spawn.branch_prefix`; a bootstrap-vs-corrected-root-divergence fixture asserting the branch-name resolution used for the `git push origin --delete <branch>` call comes from the reloaded config, not the bootstrap one.
- **Commit:** `fix(abandon): load_config uses hub root, cfg and mill_dir reloaded after resolve_active_hub`

### Card 15: `millpy-merge-in-subagent.py` -- fix project_root definition, call-site argument swap, cfg reload

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file needs two changes together (neither alone is sufficient -- see `discussion.md`'s `load-config-fix-mechanics`). First, fix `project_root = Path.cwd()` (line 337) to `project_root = _paths.resolve_hub_path()` -- cwd is not hub-rooted here today. Second, change line 345 from `cfg = _review_common.load_config(git_root, mill_dir)` to `cfg = _review_common.load_config(project_root, mill_dir)` -- today `git_root` (the outer git-repo root, computed at line 341) is passed as arg1, and `project_root` only feeds `mill_dir`; fixing only the `project_root` definition without also swapping this call's argument would leave arg1 as the outer git-repo root, the exact #728 bug pattern, unfixed. After line 360 (`mill_dir = project_root / ".millhouse"`, following the `_paths.resolve_active_hub()` call at lines 357-359), insert a reload: `cfg = _review_common.load_config(project_root, mill_dir)`, so downstream consumers (verify-cwd resolution, conflict handling, finalize dispatch) observe the corrected config. Extend `plugins/mill/unit_tests/test-merge-in-subagent.py` (which loads the module via `importlib` and patches `_paths`/`_review_common` functions with `unittest.mock` -- follow that established style) with: a hub-in-subdirectory fixture asserting the resolved `cfg` reflects the hub's own `spawn.branch_prefix`; a bootstrap-vs-corrected-root-divergence fixture asserting the merge model/timeout values downstream logic observes come from the reloaded config, not the bootstrap one.
- **Commit:** `fix(merge-in-subagent): project_root is hub-rooted, load_config uses it, cfg reloaded after resolve_active_hub`

### Card 16: `millpy-validate-plan.py` -- fix project_root definition (closes three consumers at once)

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-validate-plan.py`
  - `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Fix `project_root = Path.cwd()` (line 38) to `project_root = resolve_hub_path()` (the name is already imported at line 34's `from _paths import resolve_git_root, resolve_hub_path, resolve_wiki_path`). Since `project_root` is now already hub-rooted, simplify line 44's `cfg = load_config(resolve_hub_path(), mill_dir)` to `cfg = load_config(project_root, mill_dir)`, removing the now-redundant second `resolve_hub_path()` call. No cfg-reload is needed in this file -- there is no `_paths.resolve_active_hub()` call anywhere in `millpy-validate-plan.py`. This single fix also corrects `find_active_slug(project_root, wiki_root, cfg)` (line 45, whose first parameter is named `hub_root` in `_review_common.py:306`) and `_plan_validate.run(plan_dir, project_root, ...)` (line 47, threaded to `_check_verify_not_isolated`, whose docstring at `_plan_validate.py:1455` documents `project_root` as doubling for `hub_root`), since both already consume this same now-corrected `project_root` variable -- no changes needed at their call sites. Extend `plugins/mill/unit_tests/test-millpy-validate-plan.py` (which loads the module via `importlib` and patches helpers with `unittest.mock` -- follow that established style) with a hub-in-subdirectory fixture (mirroring issue #728's repro) asserting `main()`'s resolved `cfg` reflects the hub's own `spawn.branch_prefix`, and that `find_active_slug`/`_plan_validate.run` are invoked with the hub-rooted `project_root`, not `Path.cwd()`.
- **Commit:** `fix(validate-plan): project_root is hub-rooted, closing load_config, find_active_slug, and _plan_validate.run in one fix`

## Batch Tests

`verify:` runs all five per-script unit test files this batch extends: `test-millpy-implement.py`, `test-millpy-fix.py`, `test-abandon.py`, `test-merge-in-subagent.py`, `test-millpy-validate-plan.py`. Each file's new hub-in-subdirectory fixture directly regression-guards the #728 failure mode (hub's own `mill-config.yaml` silently missed via `_config.py`'s primary-clone fallback); the four reload-bearing files (all but `validate-plan`) additionally assert the *reloaded* config -- not the bootstrap one -- is what real hub-config-controlled downstream values (model, timeout, self-fix-rounds, branch resolution) actually observe, per `cfg-reload-after-active-hub`.
