MILL_REVIEW_BEGIN
# Review: mill-implementer: commit_sha transcription/truncation and final-status-line reliability — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude (Sonnet 5, model id claude-sonnet-5)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [NIT:consistency] New test methods reuse an already-taken `test_20_` prefix
**Location:** Batch 3 / Card 6 (`test-millpy-merge-in-subagent.py`)
**Issue:** `TestMillpyMergeInSubagent` already has `test_20_recompute_baseline_missing_status_md` (verified in the current file); Card 6's `test_20_conflicts_finalize_emits_pre_merge_head` and `test_21_...` collide with this file's established one-number-per-test convention even though the full method names differ enough to not raise a Python error.
**Fix:** Name the two new tests `test_21_...` / `test_22_...` (or reuse the file's `test_2x_` prefix already used for un-numbered additions) instead of restarting at 20.

### [NIT:consistency] `_forward_output`'s docstring leaves the new parameter undocumented
**Location:** Batch 3 / Card 3 (`_implementer_common.py`, `_forward_output`)
**Issue:** Every existing keyword parameter of `_forward_output` (verify_cmd, module_wide_verify_cmd, card_ids, task_dir, git_root, cwd_override, batch_verify_baseline, etc.) gets a prose sentence in its docstring; Card 3's Requirements add `commit_sha_field_name` to the signature but only mandate a docstring entry on `finalize_from_output`, leaving `_forward_output` inconsistent with its own established per-parameter documentation convention.
**Fix:** Add one sentence describing `commit_sha_field_name` to `_forward_output`'s docstring, mirroring the style already used for its sibling parameters.

## Verdict

APPROVE
Plan is source-grounded and internally consistent; only two cosmetic NITs found, no BLOCKING issues.
MILL_REVIEW_END
