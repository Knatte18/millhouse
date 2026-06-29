MILL_REVIEW_BEGIN
# Review: Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-29
```

## Findings

### [GAP] content==0 + verify-fail contradicts "no reordering" + test (b)
**Section:** Decisions › partial-batch-verify-reclassification (Precedence); Testing #570 guard (b)
**Issue:** The decision says a zero-content batch whose verify fails should "fall through to the existing no-content / start-batch-only gates (stuck_type: logic)" with "no gate reordering required," and test guard (b) asserts `stuck_type: logic`. But in `_forward_output` the verify gate returns early (`millpy-implement` flow at `_implementer_common.py` L745-757) **before** the no-content/start-batch checks (L761-795); a failed verify on a zero-content batch currently emits `stuck_type: verify`, never reaching the logic gate. Merely "declining to reclassify" leaves it as `verify`, not `logic`.
**Fix:** State that the reclassification site must also route content==0 (HEAD==start_sha or start-batch-only) to the no-content `stuck_type: logic` emit -- i.e. the no-content check must run ahead of the verify emit -- or accept `stuck_type: verify` for content==0 and correct test guard (b) and the "no reordering" claim accordingly.

### [NOTE] Existing completeness gate keeps raw-count off-by-one
**Section:** Decisions › partial-batch-verify-reclassification (Content-commit counting); Out
**Issue:** The new path counts *content* commits (raw minus housekeeping), but `_batch_completeness_stuck` (`_implementer_common.py` L77-101, verify_cmd-None path) still uses the raw `git rev-list --count`. Result: the two stuck/transient emitters report different `commits_made` for the same one-card-short situation (content N-1 vs raw N), and a one-card-short no-verify batch (raw==card_count) is never flagged by the existing gate due to the same off-by-one.
**Fix:** Either align `_batch_completeness_stuck` to content-commit counting, or explicitly document the divergence as intentionally out of scope and note that `commits_made` semantics differ between the two emitters.

## Verdict

GAPS_FOUND
One reachability gap between the precedence decision and test guard (b); one counting-consistency note.
MILL_REVIEW_END