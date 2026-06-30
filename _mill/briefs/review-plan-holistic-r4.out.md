MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Findings

### [NIT] Card 8 repair of test-go-assets.py is incomplete
**Location:** Batch 2 / Card 8 part B
**Issue:** The token dict at `integration_tests/test-go-assets.py` (~line 62) is already missing `SESSION_ID`, `LANGUAGE_SKILLS`, and `PARENT_BRANCH` — all live body tokens in `implementer-brief.md` — so `_render.render` raises `KeyError` on those regardless; adding only `"START_SHA": ""` does not achieve the card's stated "else they raise KeyError" goal (and the test is not in any verify gate, so the breakage is silent).
**Fix:** Have Card 8 add `SESSION_ID`, `LANGUAGE_SKILLS`, `PARENT_BRANCH` and `START_SHA` to that dict (or explicitly note the test is pre-broken and out of scope).

### [NIT] Card 8 mischaracterizes the language-skills test render dicts
**Location:** Batch 2 / Card 8 part B
**Issue:** The card says one `tokens` dict at ~line 183 is "used by the renders at ~186 and ~221," but there are two separate dicts: line 172 renders `implementer-brief.md` (render 186, needs `START_SHA`) while line 207 renders `fixer-batch-brief.md` (render 221, which has no `<START_SHA>` token); only the first requires the new key.
**Fix:** Reword to target only the implementer-brief dict (~line 172); the catch-all grep instruction already covers correctness, so impact is cosmetic.

## Verdict

APPROVE
Plan is accurate and well-grounded; two low-impact NITs in the non-gated test-repair card only.
MILL_REVIEW_END
