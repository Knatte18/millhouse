MILL_REVIEW_BEGIN
# Review: mill-plan review severity counting and validation schema gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] implementer-brief.md's commit_sha requirement conflicts with all-Commit:-none batches
**Section:** Scope (implementer-brief.md bullet) / Technical context (Validation call graph)
**Issue:** `implementer-brief.md` line 111 states "`commit_sha` MUST be a real content commit distinct from the batch start commit," but a batch composed entirely of `Commit: none` cards (explicitly contemplated in Technical context's no-content-commit-gate discussion) legitimately produces zero content commits, so the implementer has no value it can honestly put there — the Scope's implementer-brief.md bullet lists only the commit-skip instruction (~line 57), Resume-after-incomplete matching (~line 52), and Card-count self-check (~line 100) as needing updates, and omits this Report-section instruction (~line 111).
**Fix:** Add an explicit Report-section rule for the all-`Commit: none`-batch case (e.g., permit `commit_sha` to equal the batch-start SHA when every declared/remaining card is `Commit: none`, mirroring the code-derived exemption already planned for the backend gate) to `_plan_validate` Scope's implementer-brief.md bullet list.

## Verdict

GAPS_FOUND
One unaddressed instruction conflict in implementer-brief.md's Report section for all-Commit:-none batches.
MILL_REVIEW_END
