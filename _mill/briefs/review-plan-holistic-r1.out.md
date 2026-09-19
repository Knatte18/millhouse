MILL_REVIEW_BEGIN
# Review: _config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: plan/
date: 2026-09-19
```

## Findings

### [BLOCKING:design] Card 1's new tests can't produce the dotted keys RENAMED_KEY_HINTS needs
**Location:** Batch 01, Card 1 — `test_renamed_key_hints_named_in_warning`, `test_unrelated_unknown_key_no_hint_bleed`
**Issue:** Both new tests are specified to reuse `test-config.py`'s `_setup_plugin_template` fixture (lines 57-85), whose template has only `spawn`/`git`/`roles` — no `pipeline` key at all. Verified against `_config.walk_unknown_keys` (lines 88-109 of `_config.py`): recursion into a nested dict only happens `elif isinstance(actual_val, dict) and isinstance(template.get(key), dict)` — when `key` ("pipeline") is entirely absent from `template`, the function hits the `if key not in template: unknown.append(current_path)` branch at the top level and appends the single path `"pipeline"`, never descending to `"pipeline.max_review_rounds"`/`"pipeline.max_discussion_review_rounds"`. `RENAMED_KEY_HINTS.get(path)` in Card 1's own `warn_unknown_keys` change looks up the dotted key, so it will never match `"pipeline"` and the hint text (`"roles.plan-review.holistic.rounds"` etc.) never reaches stderr in this fixture — both new tests will fail their assertions. The real plugin template (`plugins/mill/templates/mill-config.yaml`) does have a `pipeline:` key, so production behavior is fine — this is purely a test-fixture mismatch.
**Fix:** Have Card 1 add a `pipeline:` key (with some placeholder sub-key, or none) to the template used by these two new tests — either a local one-off template write inside each new test (matching how `test_worktree_template_augments_template_cfg` builds its own custom templates instead of `_setup_plugin_template`), or state explicitly that `_setup_plugin_template` itself is being extended with a `pipeline:` key and confirm that doesn't perturb the ~15 other existing tests that already assert against its exact merged output.

## Verdict

REQUEST_CHANGES
Card 1's two new tests rest on a fixture that can't produce the dotted unknown-key path the hint lookup requires.
MILL_REVIEW_END
