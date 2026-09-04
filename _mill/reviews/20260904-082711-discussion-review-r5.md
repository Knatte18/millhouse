MILL_REVIEW_BEGIN
# Review: mill-go: concurrency, silently-ignored fields, and bookkeeping bugs in execution/handoff

```yaml
duration_s: 253.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #973 "audit-trail Decision" names no recording mechanism
**Section:** Scope › #973 ("prunes the batch's entry ... and records an audit-trail Decision + commit"). **Issue:** No helper exists anywhere in `_status.py` (checked: `set_blocked`, `append_phase`, `append_recovery_log`, `append_inferred_success_log`, `append_fork_fallback_log`, `append_fixer_fork_fallback_log` — none record a "Decision"), status.md has no `## Decisions` section (only `## Timeline`), and no other mill-go-base skill appends new `### Decision:` blocks to `discussion.md` at runtime — every existing reference to a discussion.md Decision is read-only citation. "Decision" is otherwise this discussion's own vocabulary for a discussion-phase artifact, so its reuse here as a runtime audit record is undefined and ambiguous. **Fix:** State explicitly which artifact/mechanism `/mill-descope-batch` writes to (a new `_status.py` helper mirroring `append_phase`, or an explicit statement that it appends to `discussion.md`), so the plan writer isn't inventing a new audit-trail convention unsupervised.

### [BLOCKING:design] #906 card-insertion collision path leaves write-order/revert undecided
**Section:** Scope › #906, card-numbering collision handling. **Issue:** The decision says to reuse `_check_card_numbering(batch_files)` verbatim (confirmed at `_plan_validate.py:908-962`: it re-parses every batch file from disk via `read_text`/`_parse_cards`, it does not accept a candidate number as an argument), which means the candidate `### Card N:` heading must already be written into the target batch file on disk before the collision check can detect it via this function. On collision, the discussion says to report `stuck_type: logic` and escalate, but never says whether the just-written speculative card heading is reverted before that report — leaving a dirty/invalid card in the batch file when escalating is exactly the class of bookkeeping bug this task exists to fix. **Fix:** State explicitly whether the candidate insertion is validated in-memory before any disk write (bypassing literal reuse of `_check_card_numbering`), or written-then-reverted-on-collision before the `stuck_type: logic` report.

## Verdict

REQUEST_CHANGES
Two undecided bookkeeping mechanisms (#973 audit record, #906 collision write/revert order) need explicit disposition.
MILL_REVIEW_END
