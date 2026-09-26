MILL_REVIEW_BEGIN
# Review: Unify ask-parent into ask-thread: ask any named session, default parent

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] Direct mode is unreachable from the hub orch session
**Section:** Decisions > "Direct mode requires a mill task worktree"
**Issue:** Direct mode requires `status.md` to resolve, i.e. a task worktree with `_mill/`. The hub orch session (`MH:orch`, cited elsewhere in this same file) runs from the main worktree, which per Project shape has no `_mill/`. The operator's most natural place to type `/ask-thread <task-name>` to poke a running task thread — the orchestrator session — therefore cannot use direct mode at all.
**Fix:** State explicitly whether operator-invoked direct mode from the hub/orch session is in or out of scope, and if out, note the consequence (operator must attach to a task-phase session instead) rather than leaving it as an unstated side effect of the worktree-only decision.

### [BLOCKING:consistency] `grep -q` doesn't implement the "first non-empty line" invariant it's paired with
**Section:** Decisions > "Reply protocol" — asker's Monitor poll
**Issue:** The correlation guarantee ("a stale or mismatched file never ends the wait") rests on checking that `ask-id: <ask_id>` is specifically the file's *first non-empty line*. The stated mechanism, "poll with `grep -q` on that line instead of `[ -s ]`", matches the pattern anywhere in the file, not just line one — a match inside quoted/pasted content further down (e.g. an earlier `ask-id` line echoed in guidance text) would fire a false `READY`.
**Fix:** Specify a position-anchored check (e.g. `head -n1 file | grep -qx ...`) or otherwise state the poll enforces first-line position, not mere containment.

### [NIT:design] Batch size of 5 has no stated rationale
**Section:** Decisions > "Two entry modes, one mechanism"
**Issue:** "batches of at most 5" is asserted with no rationale for the number, unlike every other decision in this file.
**Fix:** One line of rationale (or "arbitrary, adjust in review") so a plan writer doesn't wonder if 5 is load-bearing.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps: orch-session direct-mode reachability, and a poll mechanism that doesn't match its own stated invariant.
MILL_REVIEW_END
