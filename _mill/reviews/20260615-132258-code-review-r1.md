MILL_REVIEW_BEGIN
# Review: Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-15
```

## Findings

### [NIT] emit_prepare docstring describes pre-sanitization filename
**Location:** `plugins/mill/scripts/_implementer_common.py:110-112`
**Issue:** The docstring says the brief is written to `briefs_dir/<role>-<scope>-r<round_n>.md` but `write_brief` now sanitizes scope, so the actual on-disk filename is `<role>-<sanitized_scope>-r<round_n>.md`.
**Fix:** Update the docstring to say `<sanitized_scope>` or note that scope is sanitized for filename safety.

### [NIT] No direct unit test for parse_batch_refs fields= filtering
**Location:** `plugins/mill/unit_tests/test-review-common.py` (not in batch Edits/Creates)
**Issue:** Batch 2's verify runs `test-review-common.py` as a regression guard for the `fields=` parameter refactor, but none of the tests in that file call `parse_batch_refs` with a custom `fields=` tuple. The filtering behavior is covered only end-to-end via `test_context_excluded` in `test-language-skills-directive.py`.
**Fix:** Add one test to `test-review-common.py` that passes `fields=("Edits",)` and asserts Context tokens are excluded -- or accept end-to-end coverage as sufficient.

## Verdict

APPROVE
Implementation is correct end-to-end with two minor documentation/coverage gaps.
MILL_REVIEW_END
