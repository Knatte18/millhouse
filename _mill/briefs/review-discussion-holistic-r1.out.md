MILL_REVIEW_BEGIN
# Review: mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Uncommitted round artifacts can't be restored
**Section:** Decisions — "Detection query and restore granularity" / "Closing the Agent-mode bracketing gap"
**Issue:** Round-fresh brief/`.out.md`/review-file writes stay untracked until each round's own end-of-round commit (confirmed: `_agent_dispatch.write_brief` and `_review_common.write_review_file` never commit; mill-start step 5 and mill-plan steps 4c/4d commit reviews_dir+briefs/ only at round-end, or at Handoff on first-round APPROVE) — so `git checkout HEAD --` can't restore them, and a deleted untracked file leaves zero `git status --porcelain` trace. The new post-finalize check can neither detect nor recover loss of exactly the content created inside the Agent-mode window this task adds coverage for, contradicting the "everything is committed before a round starts" safety rationale used to justify whole-subtree restore.
**Fix:** State whether this is an accepted residual risk or requires mitigation (e.g., committing brief/review-file writes immediately rather than deferring to end-of-round); the planned unit tests (all against pre-committed fixtures) don't exercise this case either.

### [NOTE] Wrong function blamed for os.remove in ruled-out list
**Section:** Technical context — "Other candidate deletion mechanisms ruled out"
**Issue:** The bullet attributes real `os.remove` calls to `_cleanliness.revert_out_of_scope_drift`, but that function (lines 324-452) only does `git checkout HEAD --` reverts of tracked modifications; the actual `os.remove` caller is a different function, `clean_ephemeral_scope_violations` (lines 243-321), which also isn't on the review-loop path.
**Fix:** Correct the bullet to name `clean_ephemeral_scope_violations` as the `os.remove` caller — the "ruled out" conclusion itself still holds.

### [NOTE] `timestamp` semantics unclear when `record=False`
**Section:** Testing — "Record shape"
**Issue:** The dict contract fixes `restored_paths`/`timestamp` under `record=True` but doesn't say whether `timestamp` is still populated when `record=False` and `triggered=True` — time-of-check vs. time-of-audit-write are conflated.
**Fix:** Clarify `timestamp` reflects the check's wall-clock time regardless of `record`, independent of whether the status.md append happens.

## Verdict

GAPS_FOUND
One GAP: mid-round uncommitted artifacts are unrestorable and undetectable by the new safeguard.
MILL_REVIEW_END
