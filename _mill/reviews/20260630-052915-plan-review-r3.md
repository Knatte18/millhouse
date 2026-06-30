MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [BLOCKING] New <START_SHA> token breaks existing brief-render tests
**Location:** Batch 2, Card 6 (+ Card 8)
**Issue:** Card 6(b/c) injects `<START_SHA>` into the implementer-brief body; `_render.render` raises `KeyError` on any unresolved token, but existing tests pass fixed token dicts lacking START_SHA — `test-millpy-implement.py::test_real_brief_renders_parent_branch_token` (line 812) and `..._empty_when_unresolvable` (line 839), which live in Batch 2's own `verify:` file, so Batch 2 verify goes RED; `test-language-skills-directive.py:172` and `integration_tests/test-go-assets.py:64` also break.
**Fix:** Card 8 must update the two existing token dicts in `test-millpy-implement.py` (812, 839) to include `START_SHA`, and the plan must add the same fix to `test-language-skills-directive.py` and `test-go-assets.py`.

### [NIT] Internal count mismatch on Card 5 updated cases
**Location:** Batch 1, Card 5 vs. its Batch Tests prose
**Issue:** Card 5 enumerates seven cases to flip transient->incomplete (27a, 41, 43, 49f, 50g, 44a, 48e), but the Batch Tests summary says "The three updated cases (27a, 44a, 50g)" — an implementer could update only three.
**Fix:** Make the Batch Tests prose state all seven updated cases.

### [NIT] Card 7 cites `_cleanliness.capture_snapshot` without `_cleanliness.py` in Context
**Location:** Batch 2, Card 7
**Issue:** Requirements name `_cleanliness.capture_snapshot` (the call to skip) but Context lists only `_implementer_common.py`, `_render.py`, `_status.py`, `_agent_dispatch.py`; per the literal Context-completeness rule the defining file is absent (mitigated because the call site is in the Edits file `millpy-implement.py` and the rationale is fully inlined).
**Fix:** Add `_cleanliness.py` to Card 7 Context, or note the call-site-only reference is intentional.

## Verdict

REQUEST_CHANGES
One BLOCKING test-breakage in Batch 2; two minor consistency NITs otherwise sound.
MILL_REVIEW_END
