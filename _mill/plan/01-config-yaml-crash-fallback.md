# Batch: config-yaml-crash-fallback

```yaml
task: "Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure"
batch: "config-yaml-crash-fallback"
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
depends-on: []
```

## Batch Scope

Fixes #706: `_config.load_config` crashes with a raw, unhandled `yaml.YAMLError` when either of its two git-tracked YAML reads (`plugins/mill/scripts/_config.py:239` repo-layer read, `plugins/mill/scripts/_config.py:229` cache-lag source-tree-template read) hits literal merge-conflict markers. Both sites get a `try/except yaml.YAMLError` guard that falls back to treating that source as absent (never crashes), per `_mill/discussion.md`'s `config-yaml-crash-fallback (#706)` Decision. No other batch touches `_config.py` or `test-config.py`; this batch is fully self-contained and has no external interface the next batch consumes. `_review_common.load_config`'s missing-source strictness check needs no production edit (Card 5 is regression-test-only, confirming existing behavior).

## Cards

### Card 1: Guard the repo-layer `yaml.safe_load` call against parse failure

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `load_config` (`plugins/mill/scripts/_config.py:193`), wrap the repo-layer read at line 239 (`repo_cfg = yaml.safe_load(mill_cfg_path.read_text(encoding="utf-8")) or {}`) in `try/except yaml.YAMLError`. On `yaml.YAMLError`, print a stderr warning naming `mill_cfg_path` and the exception (e.g. `f"[_config] warning: failed to parse {mill_cfg_path}: {e} -- skipping repo-layer config"`), set `repo_cfg = {}`, and continue (do not `deep_merge` a broken value into `cfg`, do not re-raise). `source_label = "mill-config.yaml"` still gets set in this branch (a broken-but-present file is still "found", per the `_review_common` strictness check — see Card 5). Do not change the `else` branch (mill_cfg_path is None) at lines 242-246.
- **Commit:** `fix(config): fall back instead of crashing on unparseable repo-layer mill-config.yaml (#706)`

### Card 2: Guard the cache-lag template-augmentation `yaml.safe_load` call, preserving fall-through

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the same `load_config` function, wrap the cache-lag loop's read at line 229 (`_cand_cfg = yaml.safe_load(_candidate.read_text(encoding="utf-8")) or {}`, inside the `for _candidate in (worktree_root / ..., hub_root / ...)` loop starting at line 224) in `try/except yaml.YAMLError`. On `yaml.YAMLError`: print a stderr warning naming `_candidate` and the exception, and `continue` the loop (do NOT `break`, do NOT call `deep_merge`) — a candidate that exists but fails to parse must be treated exactly like `.exists()` being false for that candidate, falling through to try the next tuple entry. Only a candidate that exists, differs from `template_path`, AND parses successfully reaches `deep_merge(template_cfg, _cand_cfg)` and `break`s the loop. This is the exact trigger shape described in `_mill/discussion.md`'s round-3 Q&A log entry: a task worktree mid-conflict has markers in its own copy of the source-tree template while the hub's copy (on a clean branch) parses fine — the hub candidate must still get a chance to augment `template_cfg`.
- **Commit:** `fix(config): fall through instead of crashing when the cache-lag template candidate is unparseable (#706)`

### Card 3: Test the repo-layer YAML-crash fallback

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `test_load_config_repo_layer_yaml_crash_falls_back` to `plugins/mill/unit_tests/test-config.py`, following the existing helpers `_setup_plugin_template`, `_write_yaml`, `_git_init` already in this file. Write a fixture repo-layer `mill-config.yaml` containing literal git conflict markers (e.g. `"spawn:\n<<<<<<< HEAD\n  branch_prefix: a\n=======\n  branch_prefix: b\n>>>>>>> other\n"`, guaranteed invalid YAML). Call `_config.load_config` with `patch("sys.stderr", new=io.StringIO())` (the module already imports `io` and `unittest.mock.patch`) to capture stderr. Assert: (a) `load_config` does not raise, (b) the returned `cfg` carries the template default for the overridden key (`cfg.get("spawn", {}).get("branch_prefix") == ""`, matching the pattern in `test_load_config_no_hub_overlay_returns_template`), (c) the captured stderr contains the path of the broken fixture file. Also add `test_load_config_repo_layer_clean_yaml_unaffected`: a clean, valid repo-layer `mill-config.yaml` (e.g. `"spawn:\n  branch_prefix: clean_value\n"`) still merges normally (`cfg.get("spawn", {}).get("branch_prefix") == "clean_value"`, no stderr warning about a parse failure) — a regression check that Card 1's `try/except` does not change the non-crash path's behavior. Append both new function names to the `tests = [...]` list in this file's `main()` so `python test-config.py` actually runs them.
- **Commit:** `test(config): cover repo-layer mill-config.yaml parse-failure fallback (#706)`

### Card 4: Test the cache-lag fall-through fix with a falsifiable assertion

- **Context:**
  - `plugins/mill/scripts/_config.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `test_worktree_template_crash_falls_through_to_hub_template` to `plugins/mill/unit_tests/test-config.py`, mirroring `test_worktree_template_augments_template_cfg` (`test-config.py:749`) in overall structure, with one deliberate deviation from that mirror: the existing test calls `_config.load_config(wt_root, wt_root)` with the SAME directory as both `hub_root` and `worktree_root`, but this new test MUST use two DISTINCT directories for `hub_root` and `worktree_root` — reusing one directory for both, as the mirrored test does, would mean breaking "the `worktree_root` candidate" and providing "the `hub_root` candidate" are the same file on disk, so breaking one breaks both loop candidates, `template_cfg` never gets the probe key from either, and assertion (c) below fails even against correctly-fixed code. As in the existing test: set up a cache template WITHOUT the new key (e.g. reuse `pipeline.max_cards_per_batch` or introduce a distinct test-only key, e.g. `pipeline.test_probe_key: 42`), write a `worktree_root / plugins/mill/templates/mill-config.yaml` that is broken (conflict markers) but would have introduced the new key had it parsed, write a `hub_root / plugins/mill/templates/mill-config.yaml` (here `wt_root`, matching the existing test's naming) that IS valid and DOES introduce the new key, and write the SAME key into the repo-layer `mill-config.yaml` (`hub_config_path`) as well — this second write is required per `_mill/discussion.md`'s round-5 Q&A log entry: `warn_unknown_keys` only walks keys present in `check_cfg`, which is derived from the returned `cfg`, and `template_cfg` (what the augmentation loop builds) never feeds `cfg` directly — only a key that ALSO reaches `cfg` via the repo-layer merge makes the "no unknown-key warning" assertion falsifiable. Capture stderr via `patch("sys.stderr", new=io.StringIO())`. Assert: (a) `load_config` does not raise, (b) stderr contains a parse-failure warning naming the broken `worktree_root` candidate path, (c) stderr does NOT contain `"unknown key: pipeline.test_probe_key"` (or whichever key name chosen) — this assertion is now falsifiable because the key reaches `check_cfg` via the repo-layer config regardless of the loop's outcome, so it only passes if Card 2's fall-through actually let the `hub_root` candidate augment `template_cfg`. Append the new function name to the `tests = [...]` list in this file's `main()`.
- **Commit:** `test(config): prove cache-lag fall-through with a key that also feeds check_cfg (#706)`

### Card 5: Regression test — unparseable repo-layer file still counts as "found" for `_review_common`'s strictness check

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `test_review_common_load_config_unparseable_repo_layer_does_not_raise` to `plugins/mill/unit_tests/test-config.py`, following the existing `test_review_common_load_config_container_layout` (`test-config.py:910`) pattern for constructing a container/wts layout and calling `_review_common.load_config(hub_root=..., mill_dir=...)`. Write a repo-layer `mill-config.yaml` in the primary clone containing literal conflict markers (invalid YAML, same fixture shape as Card 3). Assert `_review_common.load_config(...)` does NOT raise `_review_common.ReviewError` — the raise at `_review_common.py:2003` fires only on the conjunction `not template_path.exists() and mill_cfg_path is None`, and a present-but-unparseable repo-layer file makes `resolve_repo_config_path(hub_root, worktree_root)` (which feeds `mill_cfg_path`) return a non-`None` path regardless of parse success, so the conjunction is false and no raise occurs (the fixture's plugin template also exists, so the `template_path.exists()` half of the conjunction is independently false anyway). This documents existing behavior (verified against `_review_common.py:2001-2007`); no production edit to `_review_common.py` is needed or made by this card. Append the new function name to the `tests = [...]` list in this file's `main()`.
- **Commit:** `test(review-common): document that an unparseable repo-layer config still counts as found (#706)`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-config.py` directly (a single self-contained test module executed as a script, per its own `if __name__ == "__main__"` runner — not routed through `run-all.py`, matching how this file is already invoked elsewhere in the suite). Covers all five cards: Cards 1-2 are exercised by Cards 3-5's new tests plus every pre-existing test in this file (regression coverage for the unrelated merge-order/override tests already present).
