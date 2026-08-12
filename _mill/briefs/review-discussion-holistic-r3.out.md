MILL_REVIEW_BEGIN
# Review: millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:decision] error_kind top-level mirroring has no named code site
**Section:** Decisions > "error_kind field, not a new verdict value" (and its Scope bullets).
**Issue:** The decision states `error_kind` is "mirrored at the top level for single-scope agent-mode calls," but no Scope/Technical-context bullet names how. Direct read confirms `ReviewResult` (`_review_common.py:346-372`) has a fixed field set (`type, round, verdict, reviews, blocking_count, nit_count, findings`) with no `error_kind` field, and `to_dict()` (363-372) hard-codes its output keys — passing `error_kind=` to the `ReviewResult(...)` constructor in `_review_discussion.py::finalize`'s except-block (211-227) or `_review_code.py::finalize`'s analogous block would raise `TypeError` unless the dataclass itself gains the field, which Scope never says. Separately, `millpy-review-plan.py`'s finalize-stage success path (296-304, confirmed by direct read) hand-builds `result_dict` by copying specific keys off `review_entry` (`verdict`, `blocking_count`, `nit_count`, `findings`) — `error_kind` is not among them, so even after `_review_plan.py::finalize`'s except-block gains `error_kind: "reviewer"` per Scope, it stays nested in `reviews: [review_entry]` only, never mirrored to `result_dict`'s top level, contradicting the decision text.
**Fix:** Either state explicitly that `ReviewResult` gains an `error_kind: str | None` field (threaded into `to_dict()`) and that `millpy-review-plan.py`'s `result_dict` construction copies `review_entry.get("error_kind")` to the top level, or drop the "mirrored at the top level" claim from the decision since the retry-semantics decision only ever inspects `reviews[]` entries and does not need it.

## Verdict

REQUEST_CHANGES
One BLOCKING: the error_kind top-level-mirroring claim has no grounded implementation site in ReviewResult or millpy-review-plan.py.
MILL_REVIEW_END
