MILL_REVIEW_BEGIN
# Review: Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-08
```

## Findings

### [BLOCKING] Card 2 Requirements cite wiki/_client.py, absent from Context
**Location:** batch 2 / Card 2 (`test-millpy-claim.py`) **Issue:** Requirements name `_ensure_daemon` and cite `wiki/_client.py:620-662` as the hang root cause, but `wiki/_client.py` is not listed in Card 2's `Context:` (`millpy-claim.py`, `test-millpy-spawn.py`) or `Edits:`. **Fix:** Add `plugins/mill/scripts/wiki/_client.py` to Card 2's `Context:` list.

## Verdict

REQUEST_CHANGES
One BLOCKING context-completeness gap in Card 2; all other claims verified accurate against source.
MILL_REVIEW_END
