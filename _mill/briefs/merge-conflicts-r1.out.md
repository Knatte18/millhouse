Resolved conflict markers in all 3 listed files and staged them:

- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/scripts/_implementer_common.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-implementer-common.py
- /home/hanf/Code/millhouse/wts/baseline-uses-worktree-not-checkout/plugins/mill/unit_tests/test-verify-baseline.py

Summary of resolutions:

1. `_implementer_common.py` (6 conflict blocks):
   - Deleted the on-demand baseline-compute prelude in `_run_verify_gates` (HEAD's intent: this task removes it per Decision `delete-corroboration`/`eager-not-lazy`).
   - Kept main's new `card_commit_messages` parameter (an independent, unrelated #1061 feature) on `finalize_from_output`/`_forward_output` while dropping `batch_name`/`git_name`/`git_email` from both signatures, docstrings, and forwarding calls (this task's Decision `start-sha-parameter` removes them as dead forwarding).
   - Collateral fix (not under conflict markers, but broken by the combination): main's new `_fixer_logic_ancestor_override` function and its call site forwarded `start_sha`/`status_path`/`batch_name`/`git_name`/`git_email` into `_run_verify_gates`, which no longer accepts them post-merge. Removed those four dead parameters from `_fixer_logic_ancestor_override`'s signature, docstring, and its `_run_verify_gates` call, and from its call site in `_forward_output` — same "forwarding chain that exists only to reach it" rationale the brief already applies elsewhere. Left `start_sha` alone since the function uses it directly for `_content_commit_count`.

2. `test-implementer-common.py` (1 conflict block): main added test cases 83 (on-demand baseline computation), 84 (`_fixer_logic_ancestor_override`), 85 (`card_commit_messages` fallback), 86 (on-demand progress line). Dropped cases 83 and 86 (they exercise `compute_batch_baseline_on_demand`/`_status.set_baseline_parent_sha`, both deleted by this task). Kept cases 84 and 85 verbatim (they test surviving, unrelated functionality and already call the trimmed APIs correctly).

3. `test-verify-baseline.py` (2 conflict blocks): main added case (n) (`compute_batch_baseline_on_demand` checkout/teardown) and case (o) (`NONZERO_EXIT` signature synthesis, #1060). Dropped case (n) (tests deleted on-demand-checkout functionality; not even imported at module top). Kept case (o), fixed its `compute_batch_baselines(...)` calls to the branch's already-updated 2-arg `(commands, cwd)` signature (dropped the stale `project_root` positional arg), and added a short module-docstring paragraph documenting it for consistency with the file's existing per-case doc style.

Verification performed:
- No conflict markers remain in any of the 3 files (`grep` clean).
- All 3 files compile (`python3 -m py_compile`).
- No stale references to deleted symbols (`batch_name`, `git_name`, `git_email`, `baseline_parent_sha`, `compute_batch_baseline_on_demand`) remain in any of the 3 files.
- Ran the actual batch verify commands: `test-verify-baseline.py` + `test-worktree.py`, `test-implementer-common.py` + `test-fix-finalize.py` + `test-millpy-fix.py` + `test-status.py` — all pass.
- Ran the full unit suite (`run-all.py`): 113/115 pass. The 2 failures (`test-mill-go-base-agent-only.py`, `test-millpy-validate-plan.py`) are unrelated to the 3 files I resolved — they concern `mill-go-base/SKILL.md` prose and a `_plan_validate.py`/`millpy-validate-plan.py` `done_gate` kwarg mismatch, neither of which was in my assigned conflict list or touched by my edits. Left untouched, out of scope for this brief.

Nothing was discarded that reflects a genuine loss of intent — the dropped test cases (83, 86, n) all exercised functionality this task's own Scope/Decisions explicitly delete, and this is a straightforward application of "this branch's intent overrides" rather than an ambiguous judgment call.

{"status":"success"}
