MILL_REVIEW_BEGIN
# Review: mill-plan/mill-start planning-process gaps, round 2

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-21
```

## Findings

### [BLOCKING:consistency] Technical Context misstates plan-overview.md's current contents
**Section:** Technical context, `plugins/mill/templates/plan-overview.md` row (#1056)
**Issue:** Claims `verify_module:` should be documented "matching how `root:`/`skip_checks:`/`discussion_sha:` are already documented there" — but the actual template (read in full) documents only `root:` (HTML comment lines 10-12, frontmatter line 38); `skip_checks:` and `discussion_sha:` appear nowhere in the file, in the comment or the yaml block.
**Fix:** Correct the row to say only `root:` is precedented, or explicitly scope this task to also add doc comments for `skip_checks:`/`discussion_sha:` if that's actually intended — don't send the plan writer looking for a documented pattern that isn't there.

### [BLOCKING:design] New `verify_module:` field duplicates the overview's existing `verify:` field
**Section:** Decision `1056-cross-batch-build-break-check`
**Issue:** `plan-overview.md`'s top-level frontmatter already has a `verify:` field (`null` default) explicitly documented as "an OPTIONAL module-wide check run at each batch boundary" for exactly a whole-module build/compile command. The decision adds a second field, `verify_module: <string>`, holding essentially the same command (example given: `go build ./...`) purely to gate the new review-time check — with no rejected-alternative discussion of gating on the existing `verify:` field's presence/content instead.
**Fix:** Either gate `cross-batch-build-break` directly on the existing `verify:` field (e.g. a simple whole-module-command heuristic, or an explicit opt-in boolean rather than a duplicate command string), or add a rejected-alternative explaining why a second field is necessary despite the overlap.

## Verdict

REQUEST_CHANGES
Two BLOCKING grounding/design issues in the #1056 technical context and field design.
MILL_REVIEW_END
