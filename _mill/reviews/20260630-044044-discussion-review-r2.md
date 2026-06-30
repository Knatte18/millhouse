MILL_REVIEW_BEGIN
# Review: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] Q&A log contradicts subprocess-incomplete-resume decision
**Section:** Q&A log (line 148) vs Decisions/`subprocess-incomplete-resume` + Scope (line 37) + Q&A line 154
**Issue:** Q&A line 148 still answers that subprocess `incomplete` routes "To the existing `commits_made > 0` handling (resume via `--resume` / skip-to-cleanliness)" — the exact skip-to-cleanliness branch the `subprocess-incomplete-resume` decision and line 154 explicitly forbid (it auto-ships the partial batch, the #574 false-success).
**Fix:** Update/remove the stale line-148 auto-pick so the Q&A log matches the corrected decision (auto-`--resume` once, never skip-to-cleanliness).

### [NOTE] commit_sha attachment guards key on literal "transient"
**Section:** Decisions/`reclassify-rename-all-callers`; verify against `_implementer_common.py`
**Issue:** Each `_reclassify_verify_failure` call is followed by `if gate_result.get("stuck_type") in ("verify", "transient"): ... commit_sha` (lines 888, 1047, 1131, 1215). Renaming `transient`->`incomplete` makes these guards stop matching, so reclassified `incomplete` envelopes silently lose `commit_sha`. The discussion enumerates `commits_made`/`session_id` on the incomplete dict but is silent on `commit_sha` and on whether these four membership checks must add `"incomplete"`.
**Fix:** State whether incomplete envelopes need `commit_sha` (and thus whether the four guards add `"incomplete"`) or that dropping it is intentional.

### [NOTE] Agent-mode fresh-re-dispatch fallback may re-do committed cards
**Section:** Decisions/`warm-session-resume-recovery`, `warm-resume-mechanism`
**Issue:** When no `agentId` is retained or the resumed agent again stops, the fallback is "fresh re-dispatch." A fresh dispatch over a batch whose committed cards (e.g. Card 15) are already done risks re-doing them — the precise outcome warm-resume exists to prevent — yet the fallback's behavior toward already-committed cards is unspecified.
**Fix:** Specify how the fresh-re-dispatch fallback avoids re-doing committed cards (e.g. brief notes completed cards, or fallback uses `--resume` semantics) or acknowledge the re-do as accepted.

## Verdict

GAPS_FOUND
One unreconciled routing contradiction in the Q&A log; two coherence points to clarify.
MILL_REVIEW_END
