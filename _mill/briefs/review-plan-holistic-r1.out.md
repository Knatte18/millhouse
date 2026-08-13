MILL_REVIEW_BEGIN
# Review: mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5), self-assessed
reviewed_file: plan/
date: 2026-08-13
```

## Findings

### [BLOCKING:design] Batch 3 Card 6 Cases 73/74: HEAD==start_sha trips the no-content-commit gate first
**Location:** 03-finalize-batch-scoped-dirty-check.md, Card 6, Case 73 and Case 74
**Issue:** Both cases capture `start_sha`/`base_sha` as the CURRENT HEAD and never commit again before calling `_forward_output`, so `result.stdout.strip() == start_sha` is true at `_implementer_common.py:1702-1706` and the earlier no-content-commit gate fires (`stuck/logic`, reason "no content commit (HEAD == start_sha)") before the dirty-tree gate (lines 1758-1760) is ever reached. Case 73 asserts `status=="success"` (would actually be `stuck`); Case 74 asserts the reason mentions `README.md` (the no-content-commit reason never mentions the filename), so both assertions fail as specified.
**Fix:** Mirror the file's own existing Case 57 precedent (line ~3169-3185), which deliberately commits again after capturing the SHA specifically to make `HEAD != start_sha` and bypass this gate before dirtying the file.

### [BLOCKING:consistency] Batch 4 Card 10 CTD-6/ROOD-5 omit the mandatory status_porcelain mock
**Location:** 04-cleanliness-unresolvable-parent-diff.md, Card 10, new CTD-6 and ROOD-5 blocks
**Issue:** Requirements only say to patch `_cleanliness._parent_diff_names` to `return_value=None`, but every existing CTD-1..5 case (verified at `test-cleanliness.py:371-451`) also patches `_cleanliness._pygit2_util.status_porcelain` — and `status_porcelain` runs *before* the new `is None` check in both `compute_terminal_dirt` (line 174 vs. 177) and `revert_out_of_scope_drift` (line 360 vs. 363). Against the plain `tempfile.TemporaryDirectory()` these new cases use, `_pygit2_util.open_repo` raises `GitOpsError` (uncaught by either function), so CTD-6/ROOD-5 fail for the wrong reason instead of exercising the `None`-propagation path. The card's own claim of "mirroring the mocking convention every CTD-* case already uses" is thus not followed.
**Fix:** Also patch `_cleanliness._pygit2_util.status_porcelain` (e.g. `return_value=[]`) in both new blocks. For ROOD-5, note ROOD-1/2/3 use a bare tempdir+mocks fixture while ROOD-4 uses a real `git init` fixture — "the same tempfile git fixture the ROOD-* cases already share" is ambiguous between the two; specify ROOD-1/2/3's mocked-tempdir pattern explicitly.

## Verdict

REQUEST_CHANGES
Two regression-test fixtures (batch 3 Cases 73/74, batch 4 CTD-6/ROOD-5) would fail as specified due to gate-ordering/mocking gaps.
MILL_REVIEW_END
