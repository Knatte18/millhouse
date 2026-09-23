{"status":"success","commit_sha":"1c3a2e2639cf3d96b323410defe24eb8c134905c","session_id":"3a5acd11-dd98-4aba-8659-bf7df4c5f262","cards_done":[27,28,29]}

All 3 of 3 cards in batch 05-merge-in-baseline-recompute committed (verified via `git log <batch-start>..HEAD --oneline` matching each card's Commit: message exactly):

- Card 27 (commit 8b8b30bf): rewrote `_run_recompute_baseline` in `plugins/mill/scripts/millpy-merge-in-subagent.py` — unconditionally clears every batch's `verify_baseline_failures` first (via `_status.read_batches` + `_status.set_batch_field(..., None)`), removed the dead parent-branch resolution block, calls the new `_verify_baseline.compute_baseline(effective_cwd, module_wide_verify_cmd)` two-tuple signature, and applies the asymmetric "clean"-only caching per Decision `merge-in-recompute`. Also dropped the now-unused `_parent_branch` import.
- Card 28 (commit 57ea9890): rewrote recompute-baseline coverage in `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` — updated `test_21`/`test_22` for the new call shape, added `test_23`-`test_27` covering unconditional batch clearing across the clean/pre-existing-failures/no-module-wide-verify/malformed-verify-field paths and asserting `module_verify_baseline` is set from `compute_baseline`'s return value.
- Card 29 (commit 1c3a2e26): reworked `plugins/mill/integration_tests/test-baseline-waiver.py`'s docstring/comments. Note: this fixture already drove Step 1 through a standalone `--stage baseline` CLI call before any dispatch (i.e. it already matched the target "eager per-batch pre-flight" shape on `main`, unmodified by this task) — I verified this by running it before editing and it passed unchanged. I made the eager-capture framing and the no-checkout Decision reference explicit in the docstring/comments rather than fabricating an unneeded functional rewrite; Steps 2/3 (subset-diff waiver) are untouched as the plan specifies.

Batch verify: both sub-invocations pass — `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py` (42 tests, OK) and `PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-baseline-waiver.py` (3/3 steps PASS).

Pre-report self-check: `git status --porcelain --untracked-files=no` is clean (no uncommitted tracked changes). Ruff findings observed on both edited files are pre-existing and outside my edited line ranges (confirmed by diffing before/after my edits) — consistent with this repo's Shared Decision that lint debt is not gated.

Files touched:
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/millpy-merge-in-subagent.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/integration_tests/test-baseline-waiver.py
