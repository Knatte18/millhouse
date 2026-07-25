MILL_REVIEW_BEGIN
# Review: Batch review/verify pipeline doesn't account for cross-batch state changes

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] Decision 2 x Decision 4 composition unspecified
**Section:** Decisions 2, 3, 4
**Issue:** When `status_path` filters out a not-yet-approved later batch, it is unstated whether Decision 2's "strictly-later batch declares a removal" scan still considers that filtered-out batch — in mid-`mill-go` merge-in (batches 1-3 approved, batch 4 pending with `Deletes: tools/x/`), suppressing 1-3's verify on batch 4's not-yet-run deletion is wrong since `tools/x/` still exists on disk. This is exactly the partial-completion case Decision 4 advertises as its advantage.
**Fix:** State whether Decision 2's later-removal scan is restricted to surviving/approved batches (post-status-filter) or runs over all topo batches unconditionally.

### [GAP] Merge-in skip-reason counting mechanism missing
**Section:** Decision 5 (mill-merge-in bullet)
**Issue:** `iter_batch_verifies()` returns only surviving triples with no reason codes, so batches dropped for "not approved" / "target removed" never enter Step 4's loop; the millpy-fix bullet spells out the diff-and-reclassify mechanism, but the merge-in bullet only says "extend the existing skipped counter" without saying how a prose-driven skill obtains the two new per-reason counts.
**Fix:** Specify that Step 4 must independently diff `topo_order()`/frontmatter-verify batches against the returned triples and re-check Decision 2/4 conditions to attribute each dropped batch's reason (same as millpy-fix).

### [NOTE] Decision 1 rationale misquotes the docstring
**Section:** Decision 1 (Rationale)
**Issue:** The quoted "Callers... should treat [sources] the same way they treat `deletes_union`" is not in the docstring; the actual actionable sentence (`_review_common.py:725-727`) is about *targets*/`creates_union`. The decision is still grounded by the docstring's first sentence ("The source set mirrors the semantics of `compute_deletes_union`"), but the cited instruction is fabricated.
**Fix:** Cite the first docstring sentence as the support and drop the paraphrased "Callers should treat sources like deletes_union" claim.

### [NOTE] Exact-match tokenizer misses directory-containment removals
**Section:** Decision 2 (step d)
**Issue:** Exact normalized-token matching suppresses `go build ./tools/x/` vs `Deletes: tools/x/` (both normalize to `tools/x`), but not `go build ./tools/x/cmd/app` vs `Deletes: tools/x/` — a later batch deleting a whole directory won't suppress verifies referencing files under it. This limitation is unstated, unlike the explicitly scoped-out flag=value case.
**Fix:** State directory-containment matching as explicitly in or out of scope, mirroring the flag=value out-of-scope note.

### [NOTE] Malformed `## Batches` section error path unhandled
**Section:** Decision 4
**Issue:** `_status.read_batches()` raises `ValueError` on a malformed batches fence, but `iter_batch_verifies()` currently only catches `PlanDAGError` — a corrupt section would propagate an unhandled exception out of the finalize/merge-in verify path.
**Fix:** State whether the new `read_batches()` call inside `iter_batch_verifies()` should let `ValueError` propagate or be caught/degraded like the existing `PlanDAGError` handling.

## Verdict

GAPS_FOUND
Two decision-interaction/spec gaps must be resolved before plan writing; three notes recorded.
MILL_REVIEW_END
