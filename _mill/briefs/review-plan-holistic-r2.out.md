MILL_REVIEW_BEGIN
# Review: mill-go-base: orchestration robustness gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5)
reviewed_file: plan/
date: 2026-09-18
```

## Findings

### [BLOCKING:design] Card 4 directs new baseline-CLI test into a file with no matching fixture convention
**Location:** batch 02-status-helpers-baseline.md, Card 4
**Issue:** Requirements tell the implementer to add `test_stage_baseline_module_wide_only_skips_per_batch_loop` to `test-verify-baseline.py` and to "first read the existing test functions in that file to identify its fixture conventions for invoking `--stage baseline` (config, worktree, status.md fixtures) and match them." Verified against source: `test-verify-baseline.py` has zero tests that invoke `--stage baseline`, `main()`, or `_run_baseline_stage` — its existing tests call `_verify_baseline.compute_baseline`/`compute_batch_baselines`/`_link_dependency_dirs` directly with mocked `_subprocess_util.run`, no config/worktree/status.md fixture at all. The actual established convention for exactly this (CLI-level `--stage baseline` invocation, loaded via `importlib.util.spec_from_file_location("millpy_implement", ...)`, with `main(argv)` called in-process against tempdir config/worktree/status.md fixtures) lives in `plugins/mill/unit_tests/test-millpy-implement.py` (already has multiple `self._run_main(["--stage", "baseline"])` cases), a file not named in Card 4's Context/Edits or the plan's `All Files Touched`.
**Fix:** Either retarget Card 4's new test into `test-millpy-implement.py` (matching its `_run_main`/fixture conventions) and add it to Edits/verify/`All Files Touched`, or explicitly instruct the implementer to build the CLI-invocation scaffold from scratch in `test-verify-baseline.py` rather than claiming a matching convention exists there.

### [NIT:consistency] `clear_baseline_preflight_log` told to mirror a less-direct template than the one already in the file
**Location:** batch 02-status-helpers-baseline.md, Card 3
**Issue:** Requirements say to mirror `append_phase`'s inline `blocked_reason:`-row-deletion scan (embedded in a larger function) rather than the closer, already-existing analog `clear_module_verify_baseline` (same file, same "safe to call unconditionally, no-op if absent" contract for a standalone top-level scalar field) — verified both exist in `_status.py` and `clear_module_verify_baseline` is the more literal template match for a new `clear_baseline_preflight_log` function.
**Fix:** Point the Requirements at `clear_module_verify_baseline` as the primary template instead of (or in addition to) `append_phase`'s inline scan.

## Verdict

REQUEST_CHANGES
Card 4's new test targets a file lacking the CLI-invocation fixture conventions it claims to reuse.
MILL_REVIEW_END
