MILL_REVIEW_BEGIN
# Review: mill-go-base: orchestration robustness gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet, per system-reported model ID)
reviewed_file: plan/
date: 2026-09-18
```

## Findings

### [BLOCKING:design] `--module-wide-only` skip point doesn't reach the shared-checkout path
**Location:** Batch 2 (status-helpers-baseline), Card 4, `millpy-implement.py`
**Issue:** Requirements say to skip only the inner `for name, command, cwd in batches_needing_computation:` loop (`_run_baseline_stage`, line ~447). But `batches_needing_computation` is populated by `_enumerate_batch_verify_triples(plan_base, ...)` directly off every batch file's frontmatter (line 295-305) — independent of whether `## Batches` exists in `status.md` — so on the first speculative-launch invocation it is non-empty (this plan alone has 6 batches with non-null `verify:`). That forces `if not batches_needing_computation:` (Case A, line 313) to be False, so the code takes Case B (line 330+): parent-branch resolution, `_checkout_parent_branch`, `_link_dependency_dirs` per distinct cwd fragment (including per-batch-only fragments, line 355-357), and any `baseline_prepare_cmd` build step — all of which the card's own stated rationale ("avoids paying that verify-replay cost at all") claims is avoided, but is not.
**Fix:** Either force `batches_needing_computation` to be treated as empty (take Case A) when `--module-wide-only` is set, or explicitly extend the skip to the Case A/B branch selection and cwd-fragment computation, not just the inner loop body.

### [BLOCKING:design] Batch 7 verify's second assert is vacuously true today
**Location:** Batch 7 (handoff-worktree-guard), frontmatter `verify:` / Card 11, `handoff.md`
**Issue:** The check is `assert 'worktree_root' in t.split('mill-self-report')[0][-800:] or 'worktree_root' in t, 'worktree_root existence check not found near self-report step'`. `worktree_root` already appears 6 times in the current, unedited `handoff.md` (lines 9, 31, 65, 72, 86, 97 — all unrelated to step 6/self-report), so `'worktree_root' in t` is already `True` before Card 11's edit lands. The OR makes the whole assert pass regardless of whether the new existence check is ever actually placed near the self-report invocation — it only ever effectively tests `'already cleaned up' in t`.
**Fix:** Drop the `or 'worktree_root' in t` fallback; assert only on the windowed check (`t.split('mill-self-report')[0][-800:]`), or use a narrower, currently-absent literal (e.g. a full new sentence fragment) as the marker.

## Verdict

REQUEST_CHANGES
Batch 2's `--module-wide-only` flag and batch 7's verify marker both fail to achieve their stated purpose.
MILL_REVIEW_END
