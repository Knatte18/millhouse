# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure — 03-llm-rate-limit

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 03-llm-rate-limit
date: 2026-05-04
```

## Findings

### [NIT] `rate_limited` computed on every exit path, including success

**Step:** Card 12
**Issue:** Plan places `rate_limited = _scan_rate_limit(result.stdout or "")` **before** the `if result.returncode != 0:` branch, so it runs on every successful call (the common case).
**Fix:** Move the computation inside the `if result.returncode != 0:` block where it is consumed; zero-exit path never needs it.

### [NIT] Card 11 doesn't name `_scan_rate_limit` in the import update

**Step:** Card 11
**Issue:** The Modifies list and requirements text don't explicitly state that `_scan_rate_limit` must be added to the `from _llm_claude import (...)` block in the test file.
**Fix:** Add a one-line note in Card 11's requirements: "Add `_scan_rate_limit` to the existing `from _llm_claude import (...)` block in `test-llm-claude.py`."

## Verdict

APPROVE — no blocking issues; two minor clarity/efficiency nits.