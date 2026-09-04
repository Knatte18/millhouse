Clean tree. All checks pass.

{"status":"success","commit_sha":"a825efa46d424c926568fef482bbb4ec78b11066","session_id":"c7bf7f1a-be6b-4738-b4d2-313cbe30b2e1"}

Summary:
- Finding fixed (NIT:scope): `apply_plan`'s `dir_path.parent.parent -> cwd` derivation was untested — the two `test_apply_orphan_baseline_dir` sub-cases in `/home/knatte/Code/millhouse/wts/mill-go-windows-baseline-teardown-and-bg-liveness/plugins/mill/unit_tests/test-cleanup.py` (WorktreeLockedError and plain WorktreeError) only asserted on `REPORT:` stderr text, not on the `cwd` kwarg `remove_safe` actually received.
- Fix: replaced the bare `side_effect=<exception>` patches with fake `remove_safe` callables that record `(path, kwargs)` before raising, then assert `kwargs["cwd"] == wt_path` in both sub-cases, verifying `apply_plan`'s own `dir_path.parent.parent` derivation (source: `plugins/mill/scripts/millpy-cleanup.py:798`) independent of the earlier direct-call sub-case that passes `wt_path` explicitly.
- Verified via all five batch `verify:` commands (test-worktree.py, test-cleanup.py, test-bg-liveness.py, run-all.py --only test-implementer-common.py test-millpy-implement.py, test-implementer-common.py) — all pass.
- Committed as `a825efa46d424c926568fef482bbb4ec78b11066` and pushed; working tree clean.

{"status":"success","commit_sha":"a825efa46d424c926568fef482bbb4ec78b11066","session_id":"c7bf7f1a-be6b-4738-b4d2-313cbe30b2e1"}
