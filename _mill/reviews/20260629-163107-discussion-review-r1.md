I've verified the discussion's claims against `millpy-implement.py`, `millpy-merge-in-subagent.py`, and `_implementer_common.py`. The CLI-parity claims (#568/#569), the `skip_start_commit` surface (#563), and the four verify-gate sites (#570) all check out. One substantive correctness gap surfaced in the #570 commit-counting semantics.

MILL_REVIEW_BEGIN
# Review: Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-29
```

## Findings

### [GAP] #570 commit count includes start-batch housekeeping commit
**Section:** Decisions › partial-batch-verify-reclassification + Technical context
**Issue:** `start_sha` is captured in prepare *before* the `mill-go: start batch` commit (millpy-implement.py L277 vs L313), so `git rev-list --count start_sha..HEAD` always counts that housekeeping commit; `commits_made` is therefore content+1. The boundary `0 < commits_made < card_count` then misses the most common partial case (one card short: content=N-1 → count=N, not `< N` → escalates instead of re-dispatch) and labels a zero-content batch as `commits_made=1` "partial" rather than no-content.
**Fix:** Specify whether to exclude the start-batch housekeeping commit from the count (e.g. subtract it / reuse `_is_only_start_batch_commit`) and state the intended N-1 and zero-content outcomes; note the #570 test must use a count that includes the housekeeping commit, else the discussion's `assert commits_made == k` masks the off-by-one.

### [NOTE] Reclassification precedes the existing no-content gate
**Section:** Decisions › partial-batch-verify-reclassification
**Issue:** In the parsed-success path the verify-gate failure (where #570 reclassifies, ~L748) runs *before* the no-content / start-batch-only checks (~L761-795), so a zero-content + failing-verify batch could be reported transient/partial rather than the existing stuck/logic "no content commit". The discussion does not state precedence between the new reclassification and these gates.
**Fix:** State intended precedence; this resolves automatically if `commits_made` excludes the housekeeping commit (count becomes 0 → no reclassification).

## Verdict

GAPS_FOUND
The #570 commit-count semantics must be pinned down before plan writing.
MILL_REVIEW_END