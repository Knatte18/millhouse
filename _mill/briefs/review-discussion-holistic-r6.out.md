MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Same-file modify-then-delete can silently discard an uncommitted phase row
**Section:** Decisions: "Detection query and restore granularity" / "Closing the Agent-mode bracketing gap" (Ordering note) / Scope (Out) lossless-recovery claim.
**Issue:** mill-go's per-batch Code Review loop appends `reviewing-{batch_name}-r{N}` to status.md with no intervening commit (`mill-go/SKILL.md:357`, dispatch at `:378` — verified, no commit between them) before the new pre-prepare `check_and_restore` bracket runs. If the still-unidentified deletion mechanism hits status.md itself in that window (the exact file carrying the round's own in-flight append, and the exact file the original #726 incident deleted), `git checkout HEAD -- _mill/status.md` restores the last **committed** content, silently discarding this round's uncommitted phase-append. This contradicts Scope (Out)'s claim that recovery is "always a clean git checkout HEAD -- ... because that content is committed before a review round starts" — the append happens mid-round, before its own end-of-round commit, so that claim is false for this specific call site. Downstream, a wiped phase row also breaks the same loop's own `_status.phase_entry_timestamp(status_path, f"reviewing-{batch_name}-r{N}", occurrence=1)` freshness check (Crash-recovery step 1), which would then read `ref_ts=None` and mis-treat a genuinely fresh review file as stale. The round-2 regression test in the Testing section only exercises a *different* file being deleted alongside a modified one ("Legitimate uncommitted modification alongside a real deletion") — the same-file case is untested and unaddressed by any Decision.
**Fix:** Explicitly resolve the same-file case: either document it as a third named accepted residual risk (parallel to "Uncommitted round-fresh artifacts") with its concrete downstream consequence (lost phase row → stale freshness check), or require an immediate commit after this specific `append_phase` call so no uncommitted state is ever exposed to the bracket checkpoint.

## Verdict
GAPS_FOUND
One gap: same-file modify-then-delete interaction with check_and_restore is unaddressed and contradicts the stated lossless-recovery guarantee.
MILL_REVIEW_END
