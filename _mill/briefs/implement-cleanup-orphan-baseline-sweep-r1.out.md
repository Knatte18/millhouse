2 of 2 cards committed — both Card 3 and Card 4 have matching commits in the log. All complete.

Summary of work: implemented Card 3 (orphan baseline dir scan + sweep in `plugins/mill/scripts/millpy-cleanup.py`) and Card 4 (unit tests in `plugins/mill/unit_tests/test-cleanup.py`). Both cards committed as declared (`feat(cleanup): sweep orphaned .scratch/verify-baseline-* dirs` at 99311efe, `test(cleanup): cover the orphaned verify-baseline dir sweep` at 7d613fd7). The batch verify command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanup.py`) passed with exit 0, all 62 assertions/PASS lines printed including the new `_scan_orphan_baseline_dirs` and `_apply_orphan_baseline_dir` cases. Working tree is clean (no uncommitted tracked changes).

Relevant files:
- `/home/knatte/Code/millhouse/wts/mill-go-windows-baseline-teardown-and-bg-liveness/plugins/mill/scripts/millpy-cleanup.py`
- `/home/knatte/Code/millhouse/wts/mill-go-windows-baseline-teardown-and-bg-liveness/plugins/mill/unit_tests/test-cleanup.py`

{"status":"success","commit_sha":"7d613fd798fe83f2b71981b69faeb15e2fde8ec4","session_id":"85fbb65c-3e5e-4c69-a671-f24aa58a6e61","cards_done":[3,4]}
