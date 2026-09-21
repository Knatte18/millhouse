MILL_REVIEW_BEGIN
# Review: mill-plan/mill-start planning-process gaps, round 2

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-21
```

## Findings

### [BLOCKING:consistency] Scope > Out cites a rejected `verify_module:` field
**Section:** Scope > Out, last bullet **Issue:** The bullet says "the new `verify_module:` field for #1056 is per-plan overview frontmatter, not hub config" — but Decision `1056-cross-batch-build-break-check`'s own "Rejected" list states this exact field was the discussion's first draft and was corrected to reuse the *existing* `verify:` field instead (confirmed against `plan-overview.md` frontmatter line 39, which already carries `verify:` with the identical documented purpose). No `verify_module:` field exists anywhere in the final design. **Fix:** Update the Out bullet to read "...none of the eight fixes need one (#1056 reuses the existing per-plan overview `verify:` field, not a new one)" or remove the stale parenthetical entirely.

### [NIT:design] mill-descope-batch fit for #1086b left unverified despite being cheap to check now
**Section:** Technical context, `mill-descope-batch/SKILL.md` bullet **Issue:** The bullet defers confirming the skill's preconditions to implementation time, speculating it "may assume `phase: planned`"; reading `millpy-descope-batch.py` now shows it gates only on per-batch `status.md` state (`pending`), never on task `phase:`, so the pointer is actually a clean fit for a Plan-Review-time drift halt. **Fix:** Since this task's own Problem statement prioritizes source verification over speculation, resolve this now (state the confirmed per-batch-only gating) rather than deferring a check this cheap.

## Verdict

REQUEST_CHANGES
One stale cross-reference to a rejected config field must be corrected before plan writing.
MILL_REVIEW_END
