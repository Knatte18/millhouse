I have enough context. Let me compose the review.

# Review: 34 (A) — Config schema cleanup + reviewer registry

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-09
```

## Findings

### [NOTE] `_review_plan.run` at-least-one validation not acknowledged
**Section:** § Decisions — "Roles section replaces `review:` umbrella"
**Issue:** `_review_plan.py:315-320` explicitly raises `ReviewError` when both batch and holistic reviewers are null. Under uniform skip semantics, both-null silently skips plan review entirely instead of raising — a behavior regression not called out in the discussion.
**Fix:** Add one sentence stating whether the at-least-one check is removed (consistent with null=skip) or adapted (e.g. raised in `validate_role_refs`); the plan writer needs to know which way to go.

### [NOTE] Cluster dispatch routing architecture left open for task 13
**Section:** § Decisions — "Cluster dispatch raises until task 13 lands"; § Technical context — `_reviewer_single.py`
**Issue:** The discussion says cluster detection lives "inside `_reviewer_single.run` (or a small wrapper at the resolver layer)" — both options are structurally different interface contracts. If task 13 adds `_reviewer_cluster.run`, it either modifies `_reviewer_single.run` (wrong abstraction) or adds a new dispatch wrapper (changes all call sites). Task 34 bakes in whichever choice is made here.
**Fix:** Pick one: cluster detection stays in `_reviewer_single.run` (task 13 modifies it) OR a `_reviewers.dispatch(spec, ...)` wrapper is added in this task (task 13 fills in the cluster branch). Remove the parenthetical ambiguity.

## Verdict

APPROVE
Two notes; neither blocks plan writing. Discussion is accurate against source, decisions are complete with rationale, test strategy is explicit.