The testing-feasibility claim is confirmed: `_forward_output` is exercisable with real git in `.scratch/`, no LLM. The `test-fix-finalize.py` plan is feasible.

I now have enough to write the review. Let me compile the findings. The main issue is the internal contradiction regarding merge-in-subagent conflicts: whether `emit_prepare` is invoked WITH `start_sha` for conflicts prepare or not, and the fact that conflicts prepare has no value to supply.

MILL_REVIEW_BEGIN
# Review: agent-pipeline-reliability

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-09
```

## Findings

### [GAP] Conflicts-prepare start_sha: scope self-contradicts
**Section:** Scope (In/Out), Decisions persist-start-sha-via-cli-arg, emit_prepare signature change
**Issue:** Scope-In line 25 and the `emit_prepare` section say merge-in-subagent conflicts prepare WILL pass `start_sha` ("for future use"), but Scope-Out (line 38), the decision rationale (line 46), and Q&A gap-2 (line 203) say conflicts mode is out of scope with "no changes needed." A plan writer cannot tell whether `_run_conflicts` prepare must be modified.
**Fix:** Pick one: either drop the "conflicts prepare passes start_sha" clause from Scope-In and the emit_prepare section, or explicitly list `millpy-merge-in-subagent.py` conflicts-prepare as an in-scope edit.

### [GAP] No start_sha source exists in conflicts prepare
**Section:** emit_prepare signature change; Decisions persist-start-sha-via-cli-arg
**Issue:** If conflicts prepare is meant to pass `start_sha`, there is no value to pass: `_run_conflicts` (millpy-merge-in-subagent.py:222-242) has no pre-commit and never calls `git rev-parse HEAD` in the prepare path (Q&A note-4 confirms "no pre-commit"). The discussion does not say where `start_sha` would come from.
**Fix:** State that conflicts prepare captures `start_sha = git rev-parse HEAD` before `emit_prepare`, or confirm conflicts prepare passes nothing (preferred, since the field is unused there).

### [NOTE] Discussion-review finalize signature differs from code/plan
**Section:** Decisions round-via-cli-arg-for-review-finalize; Key files
**Issue:** `_review_discussion.finalize` takes no `scope`/`git_root` params and its CLI `prepare()` uses a positional signature `(cfg, slug, mill_dir, project_root, wiki_root, ...)` unlike code/plan's keyword form. The "same as code review" scope wording (line 28) under-specifies this divergence.
**Fix:** Note that discussion-review's finalize wiring omits `scope`/`git_root` and that its prepare call site differs, so the round-derivation edit is not a literal copy of the code-review change.

### [NOTE] start_sha capture ordering in fix prepare is implicit
**Section:** Scope; Technical context
**Issue:** Fix prepare emits the envelope at millpy-fix.py:314 and `start_sha` is captured at :305 — correct today, but the discussion does not state the invariant that the rev-parse must precede `emit_prepare`. A plan that reorders the prepare early-return would silently break the envelope.
**Fix:** Record that `start_sha` must be captured before the `--stage prepare` early-return in the shared dispatch tail.

## Verdict
GAPS_FOUND
Conflicts-mode start_sha scope contradicts itself and lacks a value source; resolve before planning.
MILL_REVIEW_END
