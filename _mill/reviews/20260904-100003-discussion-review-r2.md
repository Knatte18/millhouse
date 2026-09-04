MILL_REVIEW_BEGIN
# Review: mill-plan: entry-gate, timeline, and script-portability bugs

```yaml
duration_s: 241.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Sonnet 5 (per environment metadata; not independently verifiable from within the session)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #938 capture point never fires for resumed /mill-plan sessions
**Section:** `discussion-drift-guard-938` **Issue:** The decision anchors `discussion_sha` capture to "Phase: Plan entry, immediately after reading the file" — but `mill-plan/SKILL.md`'s Entry step-4 table has three first-class re-entry rows (`phase: planning/plan-review-*/plan-fix-*` → re-enter Phase: Plan Review directly; the `--revise` pre-check's fallthrough; "Entry: resuming after a max-rounds block") that all fall through straight into Phase: Plan Review *without ever running Phase: Plan* in that process. Since `discussion_sha` is a session-local variable, any fresh `/mill-plan` invocation that resumes mid-review-loop (a very common case, including the exact blocked-resume flow this same discussion documents) never captures a baseline, so the guard is silently inert for most multi-invocation review loops — precisely the scenario #938's own incident (a stale rewrite discovered across separate sessions) concerns. **Fix:** Persist `discussion_sha` somewhere durable across invocations (e.g. write it into `00-overview.md`'s frontmatter at Phase: Plan's commit) so every Phase: Plan Review dispatch site, regardless of which `/mill-plan` invocation reaches it, can re-derive the baseline instead of relying on an in-session variable.

### [BLOCKING:design] #938 dispatch-site enumeration omits the Agent-mode validator-fix re-invocation
**Section:** `discussion-drift-guard-938` **Issue:** The decision states the check applies "before **every** Phase: Plan Review LLM-dispatch site — both step 2's initial per-round dispatch and step 3.5's ERROR-only-aggregate retry re-dispatch," presented as exhaustive. But `mill-plan/SKILL.md`'s "Agent-mode prepare-envelope handling" (~line 438) describes a third, distinct re-dispatch: on a validator-failure envelope, it commits a mechanical fix and then "re-invoke[s] the prepare stage via the same three-step Agent-mode dispatch (re-render brief, call Agent, finalize)" — a genuine LLM call that isn't step 2's first attempt nor step 3.5's ERROR retry. **Fix:** Either explicitly list this validator-fix re-invocation as a third checked site, or reword the decision to state the check happens immediately before *any* Agent/finalize call within the round (covering all three call shapes) rather than naming only two.

## Verdict

REQUEST_CHANGES
The blob-sha drift guard's capture point and dispatch-site enumeration have real coverage gaps that undermine #938's stated goal.
MILL_REVIEW_END
