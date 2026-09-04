MILL_REVIEW_BEGIN
# Review: _plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps

```yaml
duration_s: 241.0
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:scope] Test-file docstring update stated only in Technical Context, not Scope
**Section:** Technical Context (test-plan-validate.py bullet) vs Scope > In:
**Issue:** Technical Context says the test file's "Check coverage" docstring (line ~26, confirmed genuinely present and already missing `depends-on-batch-mismatch`/`requirements-quote-indent-drift`) "should gain `verify-batch-mismatch`", but Scope's `In:` list only names `_plan_validate.py`'s module docstring and `run()`'s docstring for doc updates, not this file's own docstring.
**Fix:** Add a Scope `In:` bullet (or fold into the existing tests bullet) explicitly covering the test file's "Check coverage" docstring update.

### [NIT:consistency] `run()`'s docstring is already stale; scope doesn't say whether to backfill
**Section:** Scope > In: ("Module docstring check-list updates ... both the header list and `run()`'s docstring")
**Issue:** Verified `run()`'s docstring (line ~2917) already omits several existing checks (`depends-on-batch-mismatch`, `context-completeness`, `requirements-quote-indent-drift`, `plugin-manifest-context-missing`, `verify-not-isolated`, `verify-full-suite`, `verify-malformed-cwd`); the discussion only commits to adding the two new entries, leaving ambiguous whether the plan should also backfill the pre-existing omissions while touching this docstring.
**Fix:** State explicitly that only the two new checks are added and the pre-existing staleness is out of scope (or bring it in scope), so a plan writer doesn't have to guess.

## Verdict

APPROVE
Claims cross-checked against source (line numbers, message text, function signatures, fix-table rows) all verified accurate; only minor doc-scope nits remain.
MILL_REVIEW_END
