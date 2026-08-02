MILL_REVIEW_BEGIN
# Review: pipeline.autonomous_mode warns as unknown config key on every mill invocation — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (Sonnet 5 per harness label)
reviewed_file: plan/
date: 2026-08-02
```

## Findings

### [BLOCKING] Card 2's new unit test is vacuous — passes with or without Card 1's fix
**Location:** Batch 01, Card 2 (`test_pipeline_autonomous_mode_does_not_trigger_unknown_key_warning`)
**Issue:** `_setup_plugin_template` (test-config.py:56-84) writes a synthetic template with no top-level `pipeline` key at all. In `walk_unknown_keys` (`_config.py:89-110`), the recursion into a nested dict only happens via the `elif` branch when `key` IS present in `template` as a dict; since `template_cfg` here has no `pipeline` key, the `if key not in template` branch fires at the *top level*, so `walk_unknown_keys` reports the unknown path as `"pipeline"`, never `"pipeline.autonomous_mode"`. `warn_unknown_keys` then prints `[config] unknown key: pipeline (in ...)` — a warning that is emitted regardless of whether `"pipeline.autonomous_mode"` is in `deprecated_keys`, since that suppression check only matches the exact string `"pipeline.autonomous_mode"`. The test's assertion (`assert "unknown key: pipeline.autonomous_mode" not in stderr_output`) therefore passes trivially — the substring it checks for is never produced by this synthetic-template scenario in the first place, with or without Card 1's fix applied. (I traced `load_config`'s merge: `cfg = deep_merge(template_deepcopy, repo_cfg)` sets `cfg["pipeline"] = repo_cfg["pipeline"]` wholesale since `template_deepcopy` lacks `pipeline`; `template_cfg` used for the unknown-key check is never augmented in this test because the cache-lag augmentation candidates at `worktree_root/hub_root / plugins/mill/templates/mill-config.yaml` don't exist under the tmp dir.) Note the real installed template (`plugins/mill/templates/mill-config.yaml:119-128`) DOES have a top-level `pipeline:` key with several sibling subkeys, so Card 1's production fix is correct and will work correctly in the wild — only the *test* as specified fails to exercise that path.
**Fix:** Add a `pipeline:` section with at least one unrelated key (mirroring the real template's `pipeline.auto_merge`, `pipeline.done_gate`, etc.) to the synthetic template written by `_setup_plugin_template`, or use a dedicated synthetic template for this one test that includes a `pipeline` dict, so `walk_unknown_keys` recurses into it and actually produces `"pipeline.autonomous_mode"` for the assertion to meaningfully check.

## Verdict

REQUEST_CHANGES
Card 2's new test is vacuous against its own synthetic template and doesn't verify the suppression it claims to.
MILL_REVIEW_END
