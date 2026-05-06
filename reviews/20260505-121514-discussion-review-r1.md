I have sufficient grounding from the source files to write the review.

# Review: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-05
```

## Findings

### [GAP] "No push" rationale mischaracterizes existing policy

**Section:** `task-branch-push` Decision — Rationale
**Issue:** The rationale states "The 'no push' annotation in the existing mill-go skill applies to wiki commits only." This is factually wrong. Wiki commits always push (they go through `_wiki.write_commit_push`). The SKILL.md's "no push" applies to task-branch state-mutation commits — Prepare and Implement both carry explicit "(no push)" annotations, and Board Discipline reads "No push from per-card commits — mill-merge pushes the task branch at task end." Post-implementation, mill-go's own state commits (Prepare, Approve) would still be no-push while the CLI's commits push — an unexplained inconsistency. The `mill-go-skill-update` decision does not include updating the Board Discipline section.
**Fix:** Correct the rationale to acknowledge this changes the existing no-push policy for state-mutation commits and clarify whether mill-go's own state commits (Prepare, Approve) should also start pushing, and whether the Board Discipline section of mill-go's SKILL.md is in scope.

### [GAP] `LLMError` (non-session) behavior from CLI unspecified

**Section:** Failure Modes / `session-error-handling` Decision
**Issue:** The `session-error-handling` decision covers `LLMSessionError` (resume failure), but `_implementer_sonnet.run` can also raise bare `LLMError` (timeout, auth failure, non-zero exit without session context — see `_llm_claude.py:254–270`). This can happen on both initial dispatch and fix-cycle. Mill-go's current Stuck Escalation section catches `LLMError` and applies a one-retry policy; after the refactor, the Builder receives exit codes and JSON from the CLI instead. If the CLI lets `LLMError` propagate unhandled, it crashes with no JSON on stdout, breaking the Builder's parsing path. No test scenario covers this case.
**Fix:** Specify what the CLI emits and exits when `_implementer_sonnet.run` raises `LLMError` (not `LLMSessionError`): likely `{"status":"stuck","stuck_type":"transient","reason":"<message>"}` on stdout with exit non-zero, consistent with `LLMSessionError` handling.

### [NOTE] Exit-code table inconsistent with `LLMSessionError` path

**Section:** CLI surface — Exit codes
**Issue:** The table says exit 1 → "pre-launch error … message on stderr", but the `session-error-handling` decision and test scenario 5 both place JSON on stdout at exit 1. The table doesn't represent this third case.
**Fix:** Add a third exit-code row: `1 (runtime error)` — implementer session error; synthetic stuck JSON on stdout, details on stderr.

### [NOTE] `<ROUND>` token inconsistency between CLI surface and fix template

**Section:** CLI surface / Template tokens (`implementer-fix.md`)
**Issue:** The CLI surface section says `--round N` is "injected into fix prompt as context", implying a template token. The fix template token list only shows `REVIEW_FILE`, `BATCH_FILE`, `SELF_FIX_ROUNDS` — no `<ROUND>`.
**Fix:** Either add `<ROUND>` to the fix template token list, or remove "injected into fix prompt as context" and say the round number is only for the state-machine transition (no template injection needed).

## Verdict

GAPS_FOUND
Two gaps: "no push" rationale is factually wrong with post-implementation inconsistency unresolved; `LLMError` (non-session) CLI behavior is unspecified.