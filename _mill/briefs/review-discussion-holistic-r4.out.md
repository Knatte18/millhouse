MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Resume housekeeping commit can re-inflate the commit count
**Section:** `start-sha-preserving-resume` / Technical context (gotcha at millpy-implement.py line 123)
**Issue:** The resume refreshes `implementer_session` in status.md (so status.md is dirty and must be committed per the #563 discipline), yet the scope leaves undecided whether resume makes a second `"mill-go: start batch"` housekeeping commit. `_content_commit_count` subtracts only the *oldest* such commit (`subjects[-1]`), so a second one mid-range is counted as content — inflating the count and re-introducing a #574-class false-success (e.g. a resumed 2/3 batch counts 3 >= card_count -> success).
**Fix:** Decide explicitly: either the resume prepare makes no housekeeping commit (and how the refreshed status.md is committed without dirtying the tree), or `_content_commit_count` must subtract *all* `"mill-go: start batch"` commits in range (not just the oldest) — and add a test asserting a partial resumed batch with a second housekeeping commit still emits `incomplete`.

### [NOTE] SendMessage-failure edge in warm-resume not enumerated
**Section:** `warm-session-resume-recovery` / `warm-resume-mechanism`
**Issue:** The fallback triggers on "no retained `agentId`" or "resume stops without JSON again," but not on `SendMessage` itself erroring because the background agent already terminated after its completion notification (the #574 stop was `status: completed`).
**Fix:** Add that a `SendMessage` error/failure (agent no longer addressable) also routes to the `start-sha`-preserving fresh re-dispatch fallback.

### [NOTE] Fixer self-check must target the current round's housekeeping commit
**Section:** `fixer-brief-commit-guard`
**Issue:** On multi-round fixes, history holds several `mill-go: fixing batch ... round N` / `mill-go: holistic fix round N` commits; a prefix match alone could compare HEAD against an earlier round's commit, which always differs and silently defeats the no-commit check.
**Fix:** Specify the self-check compares HEAD against the *most recent* (current-round) housekeeping commit.

## Verdict

GAPS_FOUND
One correctness gap: the resume housekeeping commit can inflate `_content_commit_count` and re-create false-success.
MILL_REVIEW_END
