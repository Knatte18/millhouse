5 commits match all 5 cards (8, 9, 10, 11, 12) declared in the batch. All complete: 5 of 5 cards committed.

{"status":"success","commit_sha":"3e600c24924e335bac41962d1bb22e48894e7c22","session_id":"8beb742b-cfe8-4771-9a31-9c954966c784","cards_done":[8,9,10,11,12]}

Summary of work completed (5 of 5 cards committed):

- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/scripts/_status.py` — added `get_baseline_parent_sha`/`set_baseline_parent_sha`
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/scripts/_verify_baseline.py` — added `compute_batch_baseline_on_demand`
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/scripts/_implementer_common.py` — `_run_verify_gates` now computes a batch's baseline on demand when uncached
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/scripts/millpy-implement.py` — `_run_baseline_stage` simplified to module-wide-only plus a cheap `baseline_parent_sha` pin; removed `--module-wide-only` and dead per-batch enumeration code
- `/home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/plugins/mill/skills/mill-go-base/SKILL.md` — updated docs for the single-JSON-line contract and removed the obsolete per-batch recapture section
- Corresponding test files updated: `test-status.py`, `test-verify-baseline.py`, `test-implementer-common.py`, `test-millpy-implement.py` (the latter had ~844 lines of obsolete per-batch/shared-checkout tests replaced with a smaller, focused set covering the new contract)

`verify:` ran clean (all 4 target test files pass); working tree is clean.
