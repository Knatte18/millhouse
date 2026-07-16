MILL_REVIEW_BEGIN
# Review: Miscellaneous small tooling and doc/template accuracy gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-16
```

## Findings

### [NIT] Card 1 import-cycle rationale is factually off
**Location:** Batch 1 / Card 1
**Issue:** The card states "`_review_common` only references `_reviewers` inside function bodies today," but `_review_common.py:66` is a top-level `import _reviewers`, so the `_agent_dispatch -> _review_common -> _reviewers` edges already exist at import time and a top-level import in `_reviewers` would close a live cycle, not merely a "future-fragile" one.
**Fix:** Reword the rationale to note the cycle is already active via the top-level import at `_review_common.py:66`; the prescribed local-import action is correct and unchanged.

### [NIT] Card 10 omits `_plan_validate.py` from Context
**Location:** Batch 4 / Card 10
**Issue:** The card's replacement prose asserts behavior of `_plan_validate.py`'s `all-files-touched-mismatch` and `parallel-modifies-overlap` checks, but neither `_plan_validate.py` is in `Context:`; for a doc-accuracy fix the implementer cannot verify the claim. (Both check names do exist there — the claim is correct.)
**Fix:** Add `plugins/mill/scripts/_plan_validate.py` to Card 10's `Context:`.

## Verdict

APPROVE
Plan is accurate, complete, and well-sequenced; two minor wording/context nits only.
MILL_REVIEW_END
