MILL_REVIEW_BEGIN
# Review: _plan_validate context-completeness: further false-positive/false-negative gaps, round 3

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-23
```

## Findings

### [BLOCKING:design] `_compute_declared_symbols_union` doesn't need line-join-refactor
**Section:** Scope > In (bullet 2) / Technical context (`_compute_declared_symbols_union` bullet)
**Issue:** Both claim this function "shares `_check_context_completeness`'s per-line backtick-scanning pattern" and is touched by `line-join-refactor`. Read source: it already calls `_BACKTICK_RE.finditer(requirements_text)` once over the full joined `_requirements_fence_aware_body` output, with no `.splitlines()`/per-line loop anywhere in the function — it is already doing exactly what the refactor wants. It also calls no exemption helper, so none of the offset-table/clause-cap/line-field machinery the Decision describes applies to it either.
**Fix:** Drop `_compute_declared_symbols_union` from the line-join-refactor's touched-function list; the refactor is `_check_context_completeness`-only.

### [BLOCKING:consistency] Testing item (d)'s empty-union example contradicts whole-plan Decision
**Section:** Testing (resolution-scope-rework fixture bullet, item d)
**Issue:** Item (d) frames the empty-plan-wide-cited-files-set case as "the first card of the first batch, before any card's `Context:`/`Edits:`/etc. has accumulated anything into the plan-wide union" — language describing incremental, order-dependent accumulation. But Decision `resolution-scope-rework` and the Q&A log both state the set is a whole-plan union built by unioning `_card_own_reference_set` over every card, "computed once per `run()` call" — i.e. every card's refs (including later cards) are already in the set before any card is checked. Under that design the set is empty only when literally no card in the entire plan has any Context/Edits/Creates/Deletes/Moves entries, not merely because it's "the first card."
**Fix:** Rewrite item (d)'s parenthetical to describe the real trigger (a plan where every card's own reference fields are empty), or drop the misleading "first card, before accumulation" framing.

## Verdict

REQUEST_CHANGES
Two findings rest on a false premise about current source behavior or contradict the whole-plan-union Decision.
MILL_REVIEW_END
