MILL_REVIEW_BEGIN
# Review: _review_common/_review_plan: verdict/count consistency and path-suppression gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version not independently knowable)
reviewed_file: _mill/discussion.md
date: 2026-08-10
```

## Findings

### [BLOCKING:design] mill-plan has one loop, not two, contradicting the #798 loop-site count
**Section:** Decisions > `review-loop-min-rounds-and-demoted-predicate`; Technical context (loop-termination sites)
**Issue:** The Decision claims "mill-plan's batch and holistic plan-review loops" as two independently-terminated loop sites (part of "6 loop sites total across 3 SKILL.md files, since batch/holistic are independently configured scopes"). `plugins/mill/skills/mill-plan/SKILL.md` line 38 reads only `roles.plan-review.holistic.rounds` into `max_review_rounds`, and `### Phase: Plan Review` (lines 258-497) is a single `Loop up to max_review_rounds rounds` construct with one shared round counter N, dispatching batch+holistic together per round via one `millpy-review-plan.py` call (steps 4a-4d branch on the aggregate verdict/blocking_count, not per-scope). This is structurally unlike mill-go, which genuinely has two separate SKILL.md sections (`Execute` step's per-batch loop ~line 731, `## Holistic code review` ~line 1151) each with its own round counter. Actual loop-site count is 4 (mill-start:1, mill-plan:1, mill-go:2), not 6.
**Fix:** Correct the Decision and Technical Context to state mill-plan has a single SKILL-level loop gated by `holistic.rounds`; either scope `min_rounds`/demoted-predicate to `holistic` only for mill-plan (batch never independently reaches SKILL-level termination logic in the current architecture), or add an explicit sub-decision on how a per-scope `min_rounds` is meant to interact with mill-plan's single shared round counter when batch review is enabled.

## Verdict

REQUEST_CHANGES
mill-plan's loop-site count/structure premise for #798 is false and needs resolution before plan writing.
MILL_REVIEW_END
