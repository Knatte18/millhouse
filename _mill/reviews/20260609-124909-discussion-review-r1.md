I have enough to assess. The conflicts dispatch in merge-in SKILL (line 48) references the generic Agent-mode dispatch pattern which uses "the same standard arguments" in finalize. For Gap D, the finalize must receive `--start-sha`/`--session-id` which come from the prepare envelope, not from the original `<args>`. The generic Agent-mode dispatch step 5 ("same standard arguments") does not account for prepare-envelope-derived args being threaded into finalize. This is the same documentation ambiguity that affects fix and review.

Let me confirm the prepare envelope inferred-success for conflicts. There's a subtle issue: conflicts mode uses `git merge --continue` AFTER `{"status":"success"}` — meaning at finalize time, HEAD has NOT yet advanced (the merge isn't committed until after finalize returns success). The inferred-success path requires `HEAD != start_sha`. But the conflict resolver only stages resolutions; the merge commit happens after finalize. So inferred-success (head moved + tree clean) may never fire for conflicts mode because the tree is intentionally dirty (staged but uncommitted) at finalize time. Let me verify this concern by re-reading the conflicts flow. The resolver edits files to resolve conflicts but does NOT commit (the SKILL runs `merge --continue` after success). So at finalize, HEAD == start_sha and tree is dirty -> inferred-success cannot trigger. This is a feasibility gap for Gap D's stated fix.

I have sufficient grounding. Let me compose the review.

MILL_REVIEW_BEGIN
# Review: agent-pipeline-reliability

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-09
```

## Findings

### [GAP] emit_prepare must change but is declared out-of-scope
**Section:** Scope ("Out"), Decision persist-start-sha-via-cli-arg
**Issue:** Fix/merge-in prepare envelopes go through shared `_implementer_common.emit_prepare()` (millpy-fix.py:318, millpy-merge-in-subagent.py:242), which has no `start_sha` param and is also called by implement.py:260; the discussion lists `_implementer_common.py` as needing no changes yet emitting `start_sha` in the prepare envelope requires touching it.
**Fix:** Decide and state: add optional `start_sha`/role-gated param to `emit_prepare`, or bypass it with an inline envelope for fix/merge — and confirm the implement envelope shape is unaffected.

### [GAP] Conflicts-mode inferred-success cannot fire (HEAD unchanged at finalize)
**Section:** Scope (Gap D), Decision persist-start-sha-via-cli-arg
**Issue:** The conflict resolver only stages resolutions; the merge commit is created by `git merge --continue` in mill-merge-in/SKILL.md:48 *after* finalize returns success — so at finalize time HEAD == start_sha and the tree is dirty, and `_forward_output`'s elif branch (requires HEAD != start_sha AND clean tree) never triggers. Adding `--start-sha` to conflicts finalize fixes nothing.
**Fix:** Confirm whether inferred-success is even applicable to conflicts mode; if not, scope Gap D to session_id only or redefine the success signal (e.g. staged-resolution check) rather than reusing the commit-based fallback.

### [GAP] reviews_dir derivation helper named imprecisely
**Section:** Decision round-via-cli-arg-for-review-finalize; Q&A "How should reviews_dir be obtained"
**Issue:** The discussion says derive `reviews_dir` from `cfg['paths']['reviews_dir']` via `_paths.resolve_task_path`, but the existing call is `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)` (_review_code.py:204) which adds `<SLUG>` substitution + active-hub resolution; raw `_paths.resolve_task_path(project_root, ...)` skips both and would mis-resolve.
**Fix:** Specify `_review_common.resolve_path(cfg["paths"]["reviews_dir"], slug)` as the helper, not `_paths.resolve_task_path` directly.

### [NOTE] Conflicts-mode start_sha not captured in prepare
**Section:** Technical context (Gap D), Scope
**Issue:** `_run_conflicts` (millpy-merge-in-subagent.py:222-260) has no pre-commit and no `git rev-parse HEAD`; unlike fix it must add new capture logic, which the Decision's "after the pre-commit" phrasing does not cover.
**Fix:** State explicitly that conflicts prepare adds a `git rev-parse HEAD` capture with no pre-commit step.

### [NOTE] Finalize args not in "standard arguments" set
**Section:** Technical context (prepare->Agent->finalize pattern); Scope SKILL updates
**Issue:** mill-go/SKILL.md:125 step 5 passes "the same standard arguments" to finalize, but `--start-sha`/`--session-id`/`--round` originate from the prepare envelope, not the original invocation args; the generic pattern does not describe threading envelope fields into finalize.
**Fix:** Have the SKILL update amend the Agent-mode dispatch pattern (step 5) to thread named prepare-envelope fields into finalize, not just the original args.

## Verdict

GAPS_FOUND
Shared emit_prepare scoping and conflicts-mode inferred-success feasibility must resolve before planning.
MILL_REVIEW_END
