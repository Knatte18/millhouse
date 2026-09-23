All 9 cards (10-18) of batch implement-baseline-stage are committed (9 of 9 complete), verify passes, and the working tree is clean.

Summary of work:
- Card 10/11 (combined commit 6f604a2b): added `_baseline_exclusion_prefixes`, `_baseline_preflight_skip_reason` (Decision `preflight-precondition-guard`), `_porcelain_snapshot`, `_warn_new_dirt` (Decision `preflight-dirt-warning`) to `plugins/mill/scripts/millpy-implement.py`.
- Card 12 (3677e475): rewrote `_run_module_wide_standalone` for the new `compute_baseline(cwd, cmd, timeout_seconds=...)` signature, threading the preflight guard's result in as a parameter instead of resolving the parent branch itself; deleted `_relative_cwd_fragment` and `_pin_baseline_parent_sha`.
- Card 13/14/15 (combined commit 9f67c8c6, since the Card 13 function and the Card 14 rewrite are intertwined edits to the same block): added `_run_per_batch_baseline_standalone` (eager per-batch capture, `capture-set-equals-gate-set`/`per-batch-capture-driver`/`module-wide-verdict-source`/key-presence idempotence), rewrote `_run_baseline_stage` to call the preflight guard exactly once and drive both halves, and dropped the removed `baseline_prepare_cmd` parameter from `main()`'s call site.
- Card 16 (5be205de) / Card 17 (5b5b5b5d): removed `pipeline.baseline_prepare_cmd` from `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml`, keeping both in sync.
- Card 18 (f8614e3c): rewrote `plugins/mill/unit_tests/test-millpy-implement.py` -- deleted the obsolete pin tests and the cwd_override_relative-shape tests (replaced with absolute-cwd equivalents), updated every `compute_baseline` mock to the new tuple/positional shape, rewrote the "one JSON line" test into a two-substage-line test, deleted the now-obsolete `TestVerifyBaselineCwdOverrideRelative` class (it exercised the pre-batch-2 checkout API and duplicated coverage `test-verify-baseline.py` already owns), and added new coverage for two-half-stage-ownership, per-batch-capture-driver, capture-set-equals-gate-set, key-presence idempotence, module-wide-verdict-source seeding, preflight-precondition-guard (including the single-call-site git-call-count regression guard), and preflight-dirt-warning.

Verify command run: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py` -- 92 tests, all passing.

Relevant files:
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/millpy-implement.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-millpy-implement.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/mill-config.yaml
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/templates/mill-config.yaml

{"status":"success","commit_sha":"f8614e3c7b09257b195184c3527071f324196588","session_id":"4dcf9d83-bf55-4ab9-89a9-3d6d6878fade","cards_done":[10,11,12,13,14,15,16,17,18]}
