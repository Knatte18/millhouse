MILL_REVIEW_BEGIN
# Review: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-29
```

## Findings

### [BLOCKING] `_write_local_overlay` helper reimplemented identically in two batches
**Location:** `plugins/mill/unit_tests/test-review-discussion-flow.py:90-104` and `plugins/mill/unit_tests/test-review-plan-flow.py:173-187`
**Issue:** Batch `unit-tests-discussion` (Card 14) and batch `unit-tests-plan` (Card 16) each independently define a byte-for-byte identical `_write_local_overlay(mill_dir, **entries)` helper (write yaml-dumped entries to `.millhouse/agents.local.yaml`), rather than sharing one. Both files already import the shared `_test_helpers` module (which owns `safe_temp_dir`, `init_wiki_repo`, `seed_wiki_config`, etc.), the natural home for this helper. The plan-flow copy's docstring even claims to be "mirroring the local-overlay convention already established in test-review-discussion-flow.py and test-reviewers.py" — but `test-reviewers.py` uses a differently-shaped helper (`_load_with_overlay`, which takes raw yaml text and returns a loaded registry), so the cross-reference is also imprecise.
**Fix:** Move `_write_local_overlay` into `_test_helpers.py` (or `_test_registry.py`) and have both flow-test files import the shared version instead of each defining their own copy.

## Verdict

REQUEST_CHANGES
One cross-batch helper (`_write_local_overlay`) is duplicated verbatim between the discussion and plan test-flow files instead of shared.
MILL_REVIEW_END
