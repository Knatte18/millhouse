MILL_REVIEW_BEGIN
# Review: mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-07-25
```

## Findings

### [BLOCKING] Card 3's rewritten find_active_slug drops the single-marker fallback, breaking an existing test and a real recovery path
**Location:** Batch `on-disk-first-resolution`, Card 3 (`_review_common.find_active_slug`)
**Issue:** The new implementation's exception handler only special-cases `len(matches) > 1`; when `slug_from_branch` raises `MarkerError` and exactly one on-disk `.active` marker exists but the cheap branch check didn't confirm it (e.g. `hub_root` isn't a git repo, or the branch doesn't match), the function now falls straight to `raise ReviewError("no active task detected...")` instead of returning `matches[0].stem` as the pre-existing code did. This silently removes the "trust the lone on-disk marker when the daemon path fails" fallback that today's code has (and that the batch's own decision text claims is preserved: "Multi-match and zero-match handling is entirely unchanged from the original code" and "preserves every existing observable outcome exactly").
**Concretely:** this breaks the pre-existing, unmodified test `find_active_slug glob fallback: one .active file -> returns slug` in `test-review-common.py` (~line 2687-2714), which uses a plain (non-git) tmpdir with one `_mill/my-task.active` marker and patches `slug_from_branch` to raise `MarkerError`. Under the new code, `_pygit2_util.current_branch` raises `GitOpsError` (not a git repo) -> `branch=""` -> the branch-confirm check fails -> falls through to the daemon call (mocked to raise) -> lands in the `len(matches) > 1` branch (false) -> raises `ReviewError` instead of returning `"my-task"`. This test is in the batch's own `verify:` list (`test-review-common.py`) and is not modified by Card 5, so the batch as specified fails its own verify.
**Fix:** In the exception handler, re-add the single-match trust-fallback for the unconfirmed case (`if len(matches) == 1: return matches[0].stem`) before the final "no active task detected" raise, so the daemon-failure + lone-marker path is preserved exactly as today, with only the *confirmed* case now skipping the daemon call up front.

## Verdict

REQUEST_CHANGES
Card 3's fast path silently drops the single-marker fallback on daemon failure, breaking an existing, unmodified test.
MILL_REVIEW_END
