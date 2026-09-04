MILL_REVIEW_BEGIN
# Review: mill-implementer: commit_sha transcription/truncation and final-status-line reliability

```yaml
duration_s: 189.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:consistency] Scope text under-scopes #953 vs. Technical context/Testing
**Demoted-from:** BLOCKING
**Section:** Scope > In / Decisions > rename-conflicts-finalize-field vs. Technical context / Testing
**Issue:** Scope's In-list and the Decision's own summary name only `--mode conflicts --stage finalize` for the field rename, but Technical context (re: `_run_conflicts` full-mode return, `_forward_output(output, project_root)` at millpy-merge-in-subagent.py ~line 490, verified by reading) and Testing both require the same rename at the full-mode call site "for consistency" — and Technical context hedges with "re-check this call site during planning" rather than committing, so three sections disagree on whether it's decided.
**Fix:** Update the Scope > In bullet and the Decision's own text to explicitly list both call sites (finalize-stage `~397-424` and full-mode `~490`) as in-scope, and drop the "re-check during planning" hedge now that Technical context/Testing already settled it.

### [NIT:consistency] `_attach_commit_sha` reuse note doesn't match the actual edit site
**Section:** Technical context (first bullet)
**Issue:** States `_attach_commit_sha` "should be reused, not duplicated" by any new code, but the block actually being parameterized (`_implementer_common.py` ~1879-1889, verified) is a separate inline `git rev-parse HEAD` + `_is_valid_commit_sha` check that never calls `_attach_commit_sha`; that helper is used only by unrelated stuck-envelope call sites (retiering/completeness/incomplete) which are explicitly out of scope.
**Fix:** Clarify that only `_is_valid_commit_sha`/`_COMMIT_SHA_RE` apply to the new parameter's implementation; `_attach_commit_sha` is unrelated to this change and must not be touched.

## Verdict

APPROVE
One BLOCKING: #953's scope text conflicts with Technical context/Testing on whether the full-mode call site is in scope.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
