Clean working tree, all four cards committed and pushed, verify passes.

{"status":"success","commit_sha":"1dbf35f3","session_id":"d044d6f3-bf03-4e5a-ab78-9bc7eb673123"}

Summary of changes:
- `C:\Code\millhouse\wts\nested-layout-fixes\plugins\mill\scripts\millpy-review-plan.py` — `briefs_dir` now resolves under `project_root` (hub root) instead of `git_root`; removed the stale comment describing the old (buggy) intent.
- `C:\Code\millhouse\wts\nested-layout-fixes\plugins\mill\scripts\millpy-review-code.py` — identical fix.
- `C:\Code\millhouse\wts\nested-layout-fixes\plugins\mill\unit_tests\test-review-plan-flow.py` — added `_make_nested_plan_fixture` helper and Test 28, invoking the `millpy-review-plan.py` CLI's `--stage prepare --holistic-only` via subprocess against a nested-hub-layout fixture (hub_root one level under git_root), asserting `brief_path` resolves under hub_root, not git_root.
- `C:\Code\millhouse\wts\nested-layout-fixes\plugins\mill\unit_tests\test-review-code-flow.py` — added `_make_nested_code_fixture` helper, a `json` import, and Test 22, symmetric CLI-level nested-layout regression test for `millpy-review-code.py`.

Verified both new tests actually catch the regression (temporarily reverted the two script fixes via `git stash` and confirmed both new tests fail with the exact wrong-path assertion, then restored the fix and re-ran green). All 5 pre-existing ruff findings in the touched files were confirmed pre-existing (identical before/after this batch's edits) and left untouched per scope discipline.
