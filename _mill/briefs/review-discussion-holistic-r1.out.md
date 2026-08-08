MILL_REVIEW_BEGIN
# Review: Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-08
```

## Findings

### [GAP] Passthrough commit_sha enrichment: Decision vs Technical Context disagree
**Section:** Decisions § `_forward_output stuck-passthrough fix` vs Technical Context (`_attach_commit_sha` bullet)
**Issue:** The Decision says the non-success passthrough branch "should print unchanged, exactly as it did before commit `6d92c82d`" (no commit_sha enrichment). The Technical Context bullet on `_attach_commit_sha` instead says whether the passthrough branch should enrich with a commit_sha via that helper "is open to mill-plan's judgment; not decided here" — directly contradicting the Decision's "print unchanged" resolution.
**Fix:** Resolve to one statement — either the passthrough prints `parsed` unchanged with no commit_sha touch (per the Decision), or explicitly scope `_attach_commit_sha` enrichment as a plan-writer choice; as written a plan writer could reasonably implement either and cite discussion text for support.

### [NOTE] Phase-1 timeout figure in Problem §1 doesn't match source
**Section:** Problem, item 1 (`test-claude-sub.py` hangs)
**Issue:** Text states the real `_wait_for_idle_stable` loop runs "up to ~6 minutes (60s Phase-1 + up to 300s Phase-2 bulk-mode default)". Verified in `millpy-claude-sub.py`: `PROCESSING_WAIT_TIMEOUT_S = 15` (line 29), not 60; `RESPONSE_POLL_TIMEOUT_S["bulk"] = 300` (line 34) is correct. Actual worst case is ~315s (~5.25 min), not ~360s.
**Fix:** Correct "60s Phase-1" to "15s Phase-1" and "~6 minutes" to "~5.25 minutes"; doesn't change the fix decision, which is independent of the exact figures.

## Verdict

GAPS_FOUND
One GAP: reconcile the contradictory guidance on passthrough commit_sha enrichment before plan writing.
MILL_REVIEW_END
