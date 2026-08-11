MILL_REVIEW_BEGIN
# Review: mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (per environment info; self-assessed as consistent with a Sonnet-class model, exact minor version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Cumulative holistic-round glob risks the exact batch-name collision the repo already fixed
**Section:** Technical context (bullet 1) / `prior-blocking-digest-is-cumulative-and-cross-scope`
**Issue:** The new digest's holistic-scope scan must cover "every prior holistic round" (an unbounded round range, 1..H-1), described only as `*-code-review-r{H}.md`/"glob". `mill-go/SKILL.md` line 1220 documents this exact pattern as unsafe when the round segment isn't pinned to one known value: a batch named e.g. `retry-fix` produces `...-code-review-retry-fix-r1.md`, which an unanchored `*-code-review-r*.md` glob wrongly matches as holistic. `_review_common.RE_SIMPLE`/`RE_BATCH` exist specifically to avoid this (RE_SIMPLE checked first, RE_BATCH only on non-match). The cited "existing crash-recovery glob patterns" (e.g. `mill-go/SKILL.md:1019`, `:658`) are safe only because they pin one already-known round number — they never scan an unbounded round range the way the new cumulative digest must, so the analogy doesn't establish safety for the new use case.
**Fix:** Specify that the new helper reuses `_review_common.RE_SIMPLE`/`RE_BATCH` (or iterates per pinned known round number, never an unpinned `r*` wildcard) for file classification, and add a fixture with a batch name starting with `r` to the Testing section to lock this in.

### [NIT:consistency] Handoff dispatch site line citation no longer matches source
**Section:** Scope / `symmetric-batch-and-holistic-application` / Q&A round 3
**Issue:** All three cite the Handoff "Nit-enforcement gate" self-resolve dispatch at "~line 1247-1262"; in the current `mill-go/SKILL.md` that range is the unrelated Terminal cleanliness gate. The actual Nit-enforcement gate dispatch text is at ~lines 1211-1226.
**Fix:** Update the citation to ~1211-1226 (or drop the line numbers and rely on the heading name, which is still accurate).

## Verdict

REQUEST_CHANGES
One BLOCKING: new digest's file-scan spec needs an anchored-match instruction to avoid a known collision bug.
MILL_REVIEW_END
