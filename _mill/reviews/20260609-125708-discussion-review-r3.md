Confirmed: discussion-review prepare call site (line 89/118) uses positional args `(cfg, slug, mill_dir, project_root, wiki_root, max_rounds=...)`, and finalize (line 119-121) takes NO `scope` or `git_root` — exactly as the discussion's caution states. Comment on line 117 even confirms the Gap C re-invocation rationale.

My verification is complete. All technical claims are accurate. I found one internal contradiction and a couple of minor notes.

MILL_REVIEW_BEGIN
# Review: agent-pipeline-reliability

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-09
```

## Findings

### [GAP] session-id decision contradicts merge-in scope-out
**Section:** Decisions / session-id-via-cli-arg (vs. Scope, Scope-Out, Q&A)
**Issue:** The decision says "Add `--session-id` to the finalize stage of `millpy-fix.py` **and `millpy-merge-in-subagent.py`**," but Scope "In" never lists merge-in-subagent, and Scope-Out + Q&A (review gap 2, r2 gap 1) place conflicts mode entirely out of scope ("conflicts finalize is correct as-is. No changes needed"). A plan writer cannot tell whether merge-in-subagent finalize gets `--session-id` or not.
**Fix:** Strike `and millpy-merge-in-subagent.py` from the session-id decision so it scopes only to `millpy-fix.py`, consistent with the rest of the discussion.

### [NOTE] start_sha capture line numbers slightly stale
**Section:** Technical context / emit_prepare signature change (Ordering invariant)
**Issue:** The invariant cites "line 305 rev-parse, line 314 emit_prepare"; actual is line 305 rev-parse, line 314 the `--stage prepare` guard, line 318 `emit_prepare`. The ordering (rev-parse precedes prepare early-return) is correct, but the cited line for emit_prepare is off.
**Fix:** Reference the structure ("rev-parse in shared dispatch tail before the prepare early-return") rather than exact line numbers, or update 314->318.

### [NOTE] discussion-review prepare uses keyword-only max_rounds
**Section:** Technical context / Discussion-review finalize differs from code/plan
**Issue:** The note describes the prepare call site as "positional args"; it is positional for `cfg, slug, mill_dir, project_root, wiki_root` but `max_rounds` is keyword-only (`prepare(..., max_rounds=args.max_rounds)`). Minor imprecision only.
**Fix:** Clarify "positional except `max_rounds` (keyword)" so the implementer mirrors the existing call exactly.

## Verdict

GAPS_FOUND
One scope contradiction (session-id on merge-in-subagent) must be resolved before planning.
MILL_REVIEW_END
