MILL_REVIEW_BEGIN
# Review: mill-go-base: orchestration robustness gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (best-effort self-assessment; exact point version not directly knowable to me)
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:design] 1031 speculative baseline launch precedes `## Batches` seeding
**Section:** Decision `1031-parallel-entry-baseline`
**Issue:** The speculative `--stage baseline` launch fires during the Entry-gate wait, which by construction happens strictly before mill-go's own `## Prepare` step (`_status.init_batches`, `SKILL.md` "## Prepare") has ever run for this task — the wait only triggers on phases that precede `planned`, and `## Batches` is only created once `planned` is reached. So `## Batches` does not exist on disk at speculative-launch time. `millpy-implement.py`'s `_run_baseline_stage` persists each batch's result via `_status.set_batch_field(status_path, name, "verify_baseline_failures", failures)` (line 454), and `_status.py`'s `set_batch_field` (line 949-980) raises `ValueError` when the batch name isn't already present in `## Batches` — caught by the surrounding `except Exception` (line 450-457), so every batch is silently recorded as `errored`, and the checkout + verify-command work the speculative launch just paid for is discarded with zero per-batch caching benefit (only the module-wide substage, which never touches `## Batches`, actually persists). This is the opposite of the Decision's stated rationale that the speculative job's output is "safe to simply consume later, never re-run" — that holds for the module-wide half only.
**Fix:** State explicitly whether the speculative launch should (a) run module-wide-only until `## Batches` exists, or (b) run both substages but document that the per-batch half is expected to no-op/error and be redone later (by 0.6's recapture or 0.5's own strict-fallback), so the plan writer doesn't build against a false "the whole cached JSON is reusable" premise.

## Verdict

REQUEST_CHANGES
1031's speculative baseline launch silently loses its per-batch caching benefit because `## Batches` isn't seeded until Prepare, which runs after the wait.
MILL_REVIEW_END
