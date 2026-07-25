# Batch: review-common-load-config-dedup

```yaml
task: "Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise"
batch: "review-common-load-config-dedup"
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-config.py
depends-on: []
```

## Batch Scope

This batch delivers `discussion.md` §Scope-In's second, independent bug fix:
`_review_common.py` carries a second, independently-maintained copy of `load_config`
(`_review_common.py:1842-1912`) that never received `_config.load_config`'s 2026-05-31
cache-lag augmentation (`_config.py:220-231`), so it still false-positives `[config]
unknown key: ...` for keys that have landed in the worktree/hub template but not yet in
the installed plugin cache. This batch deletes the duplicate and replaces it with a thin
delegating wrapper that calls `_config.load_config` for the core merge (automatically
inheriting the augmentation and any future fixes to that shared logic) while preserving
`_review_common`'s two review-specific behaviors on top: raising `ReviewError` when no
config source exists at all, and warning on stale top-level `review:` keys in
`config.local.yaml`. The wrapper's public signature (`load_config(hub_root: Path,
mill_dir: Path) -> dict`) is unchanged, so none of its eight callers
(`millpy-abandon.py`, `millpy-implement.py`, `millpy-fix.py`,
`millpy-merge-in-subagent.py`, `millpy-review-code.py`, `millpy-review-discussion.py:92`,
`millpy-review-plan.py`, `millpy-validate-plan.py`) or `_review_common.py`'s own internal
self-call at line 376 need to change. No batch-local decisions beyond `## Shared
Decisions` in the overview.

## Cards

### Card 5: Delete the duplicate `load_config`, delegate to `_config.load_config`

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In the `from _config import (...)` block (`_review_common.py:67-72`), remove
     `_apply_dispatch_shim`, `apply_env_overrides`, and `warn_unknown_keys` — after this
     card they have no remaining callers in the file (grep-confirmed, both used only by
     the `load_config` implementation being replaced) — and add `load_config as
     _core_load_config`. Keep `resolve_plugin_template_path` and `resolve_repo_config_path`
     (still needed by the wrapper's own existence check).
  2. Remove the now-unused `import copy` (`_review_common.py:50`) — grep-confirmed its
     sole use in the file is `copy.deepcopy(cfg)` inside the `load_config` implementation
     being replaced.
  3. Delete the private `_deep_merge` function (`_review_common.py:1829-1839`) —
     grep-confirmed it has no callers outside the `load_config` implementation being
     replaced (it is not imported by any other module).
  4. Replace the body of `load_config(hub_root: Path, mill_dir: Path) -> dict`
     (`_review_common.py:1842-1912`) with a thin delegating wrapper, keeping the exact
     same signature:
     - `worktree_root = mill_dir.parent`.
     - Perform the missing-source check independently of the delegate's return value
       (`_config.load_config` never raises and returns `{}` both when nothing is found and
       when a legitimately-present source is empty — `_config.py:215`'s `yaml.safe_load(...)
       or {}` — so "missing" must never be inferred from an empty dict):
       `template_path = resolve_plugin_template_path("mill-config.yaml")`;
       `mill_cfg_path = resolve_repo_config_path(hub_root, worktree_root)`; if `not
       template_path.exists() and mill_cfg_path is None`, raise `ReviewError(f"Missing
       config: searched plugin template at {template_path} and mill-config.yaml in hub,
       main worktree, or task worktree")` — identical message to today's
       `_review_common.py:1882-1885`.
     - Delegate the core template/repo/local merge to `cfg = _core_load_config(hub_root,
       worktree_root)`.
     - Preserve the stale-`review:`-key warning as the wrapper's own read-only peek (the
       delegate does its own internal local-config read without exposing it, so this
       cannot be inferred from `cfg`): `local_path = mill_dir / "config.local.yaml"`; if it
       exists, load it with `yaml.safe_load`, and if its `"review"` key is truthy, print
       `f"[load_config] warning: {local_path} contains stale 'review:' keys (orphaned:
       {orphaned}); remove them or update to 'roles:'"` to `sys.stderr` — identical wording
       to today's `_review_common.py:1895-1899`, with `orphaned = sorted(stale_review.keys())`.
     - `return cfg`.
     - Update the function's docstring to state it delegates the core merge (including the
       2026-05-31 cache-lag augmentation) to `_config.load_config`, and layers the two
       review-specific behaviors (missing-source `ReviewError`, stale `review:`-key
       warning) on top.
  5. Do not change the module-level docstring's one-line `load_config()` mention (line 34),
     the docstring note at lines 355-361, or the internal self-call `cfg =
     load_config(hub_dir, hub_dir / ".millhouse")` at line 376 — the public signature is
     unchanged so all three remain correct as-is.
  6. This delegation knowingly inherits two `_config.load_config` behaviors the current
     `_review_common.load_config` does not have: step 7's `_interpolate_env(cfg)`
     (`_config.py:271`), which can raise `ConfigError` for an unset `${VAR}` with no
     default, and step 3's `[_config] note: no repo-layer mill-config.yaml found...`
     stderr print (`_config.py:243-246`) when the template exists but no repo-layer config
     does. Both are acceptable: mill configs don't use `${VAR}`/`${VAR:-default}` patterns
     today (so `_interpolate_env` is a no-op in practice), and the note is informational,
     matching this task's stated goal of inheriting `_config.load_config`'s current and
     future fixes rather than re-diverging from it.
- **Commit:** `refactor(review-common): delegate load_config to _config.load_config, drop duplicate merge logic`

### Card 6: Test coverage for the delegation

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `import _config` to this file's import block (it is not currently
  imported; `_config` module resolves via the same `sys.path.insert` at line 13 already
  used for `_review_common` and friends). Then add one new test block to the flat script,
  immediately after the existing "load_config hub_relative_path does not emit unknown-key
  warning" block (after line 878), following the same `with _test_helpers.safe_temp_dir()
  as tmpdir:` pattern used by the five existing `load_config` blocks in this file:
  proving the delegation actually inherits `_config.load_config`'s worktree-template
  cache-lag augmentation, mirroring `test_worktree_template_augments_template_cfg`
  (`test-config.py:749-833`).
  - Set up a fake cache template file missing `pipeline.max_cards_per_batch`, and patch it
    into BOTH references the code paths use: `patch.object(_config,
    "resolve_plugin_template_path", return_value=<cache_template_path>)` (drives the
    delegate's real merge inside `_core_load_config`) and `patch("_review_common.resolve_plugin_template_path",
    return_value=<cache_template_path>)` (satisfies the wrapper's own pre-delegate
    existence check against the same file) — both context managers active for the
    `load_config(...)` call.
  - Write a worktree-local template at `<tmpdir_path> / "plugins" / "mill" / "templates" /
    "mill-config.yaml"` containing `pipeline:\n  max_cards_per_batch: 10\n`, and a
    repo-layer config at `<tmpdir_path> / "mill-config.yaml"` also setting
    `pipeline:\n  max_cards_per_batch: 10\n`.
  - Call `load_config(tmpdir_path, mill)` under `contextlib.redirect_stderr` (reuse the
    `_io`/`_cl` aliases already imported locally in the stale-review-key block above, or
    add fresh `import io`/`import contextlib` locally to this block) and assert:
    `"unknown key: pipeline.max_cards_per_batch"` does NOT appear in the captured stderr,
    and `cfg["pipeline"]["max_cards_per_batch"] == 10`.
  - This is the regression test for #676/#670: the old duplicate `load_config` had no
    augmentation logic at all, so this exact scenario would have printed the unknown-key
    warning under the pre-refactor code.
  - Do not modify the five existing `load_config` test blocks (lines 751-878) — they
    continue to pass unmodified against the new delegating implementation (repo-config
    load + local override, missing-config `ReviewError`, stale `review:`-key warning +
    overlay-path mention, bare `roles:` key no-crash, `hub_relative_path` unknown-key
    exclusion). Confirm this by running the full file as part of this batch's `verify:`.
- **Commit:** `test(review-common): cover load_config delegation to _config's cache-lag augmentation`

## Batch Tests

`verify:` runs `test-review-common.py` (all `load_config` cases, including the new
delegation case) and `test-config.py` (the pre-existing
`test_review_common_load_config_container_layout` reference case at line 910, which
exercises `_review_common.load_config` through the container/wts layout path and must
also keep passing unmodified post-refactor). Scoped via `run-all.py --only` to these two
files rather than the full suite, since this batch's edits are confined to
`_review_common.py`'s `load_config`/`_deep_merge` and have no other callers beyond what
these two files already cover.
