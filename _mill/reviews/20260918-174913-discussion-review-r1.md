MILL_REVIEW_BEGIN
# Review: Auto-approve on review-round cap

```yaml
duration_s: 177.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:design] Per-batch halt site isn't verdict-scoped to REQUEST_CHANGES
**Section:** Decisions — "Trigger condition: cap-exhausted with fixes already applied"; Technical context — mill-go-base per-batch.
**Issue:** The Decision states the flag "only ever fires on a round whose verdict is `REQUEST_CHANGES` and the round budget is exhausted," but the actual per-batch halt site (`mill-go-base/SKILL.md` step 5: "After `roles.code-review.batch.rounds` rounds without APPROVE") is verdict-agnostic. Step 4's `NEED_CONTEXT` branch never dispatches a fixer — it only appends `extra_files` and "increment[s] round and continue[s] the loop" — so a cap exhausted on a trailing `NEED_CONTEXT` round (no missing-file info yet exhausted) also lands on step 5, with no fix pass having run at all. This contradicts the Decision's stated premise and the holistic loop's own narrower step 7 condition ("`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned"), which correctly excludes this case.
**Fix:** State explicitly whether per-batch wiring must gate `auto_approve_on_cap` on last-round verdict == `REQUEST_CHANGES` (mirroring holistic step 7), leaving a `NEED_CONTEXT`-exhausted cap as today's hard halt regardless of the flag — or, if the flag is meant to cover that case too, define what "approved" means when no findings were ever addressed.

### [NIT:scope] Testing section gives only one flag-site acceptance scenario
**Section:** Testing — "Manual/integration verification".
**Issue:** Only `roles.code-review.holistic` gets a documented manual acceptance scenario; `roles.plan-review.holistic` and `roles.code-review.batch` (both also newly flagged) have none.
**Fix:** Note that the plan writer should generalize the given scenario to all three flag sites, or add one line each for plan-review and batch.

## Verdict

REQUEST_CHANGES
One design gap: per-batch halt condition isn't REQUEST_CHANGES-scoped, contradicting the stated trigger premise.
MILL_REVIEW_END
