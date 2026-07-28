MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-28
```

## Findings

### [GAP] Holistic ReviewError-catch write-site omitted from site enumeration
**Section:** Decisions > nit-count-fix-mechanism / Technical context (site list)
**Issue:** `_review_plan.py:1014-1024` (the outer `except ReviewError as exc:` in `run()`'s holistic block) calls `write_review_file()` and appends to `reviews[]`, satisfying the Decision's own stated inclusion test ("write a NEW review file AND whose result reaches the returned `ReviewResult`") — verified by direct read: it writes at line 1015 and appends at 1016. It is not one of the "4 live sites," and unlike the resume-disk-scan site it gets no explicit exclusion + rationale. Its dict hardcodes `"blocking_count": 0` with no `"nit_count"` key at all, unlike `finalize()`'s parallel `except ReviewError` catch (`_review_plan.py:587-600`), which explicitly sets both `"blocking_count": 0` and `"nit_count": 0`. `.get("nit_count", 0)` will paper over the omission once the aggregate-sum fix lands, so this is not a runtime bug today, but it leaves exactly the kind of cross-dispatch-path schema asymmetry (Agent-mode explicit, subprocess-mode implicit) that this task's stated goal — "restoring schema consistency with the already-correct Agent-mode ... flow" — exists to eliminate, and it is invisible to anyone checking the Decision's "4 sites" list against a `grep write_review_file` count (5 hits in `run()`-reachable code, not 4).
**Fix:** Add this site to `nit-count-fix-mechanism` explicitly: either state why it's excluded from the `finalize_scope()` refactor (calling `finalize_scope()` here would just re-raise the same `ReviewError` that produced this branch) and require `"nit_count": 0` be added to its literal dict for parity with `finalize()`'s equivalent block, or fold it into the refactor scope outright.

## Verdict

GAPS_FOUND
One real gap: a 5th `run()`-holistic write-site reaching `ReviewResult` is unaccounted for in the site enumeration.
MILL_REVIEW_END
