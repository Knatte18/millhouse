MILL_REVIEW_BEGIN
# Review: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnetxhigh
reviewed_file: plan/
date: 2026-07-29
```

## Findings

### [NIT] Batch 2 scope prose mislabels the shared prepare() call site
**Location:** 02-review-code-soft-fail.md, Batch Scope paragraph / Card 8
**Issue:** Batch Scope says the fix "routes only the `Context:`-only refs at `_review_code.py`'s holistic `prepare()` call site" through the soft-fail path, but `prepare()` is the single shared entry point for both per-batch and holistic code review (`scope=None` vs `scope="<name>"`); Card 8's own Requirements correctly patch the shared ref-collection block with no scope guard, so the fix actually applies to both scopes, not just holistic.
**Fix:** Reword the Batch Scope sentence to drop "holistic" or clarify it applies to `prepare()` regardless of scope, so the description matches Card 8's actual (correct) scope-agnostic implementation.

## Verdict

APPROVE
All 12 cards verified against source; helper signatures, call shapes, and fixtures match actual code exactly.
MILL_REVIEW_END
