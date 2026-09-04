# Batch: verify-full-suite-unit-tests

```yaml
task: "_plan_validate.py verify: command validation: false positives, missing escape hatches, and a doc/enforcement mismatch"
batch: verify-full-suite-unit-tests
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [1]
```

## Batch Scope

This batch adds unit test coverage in `plugins/mill/unit_tests/test-plan-validate.py` for the `_check_verify_full_suite` behavior changed by batch `verify-full-suite-check-fixes`: the compound-command false-positive fix (#961), the `go -C <dir> test` false-negative fix (#933), and the `done_gate` exemption (#950). Depends on batch 1 so `verify:` exercises the finished implementation, not the pre-fix code. Uses the existing `_make_verify_only_batch_text` and `_make_overview`/`_write_plan` test helpers already defined at the top of the file — no new test infrastructure.

## Cards

### Card 3: Add regression tests for go-test segment scoping and the done_gate exemption

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add five new test functions immediately after `test_check_verify_full_suite_go_test_dotdotdot_with_run_is_ok` (the existing "Clean: verify invokes 'go test ./...' with a -run filter" test) and before `test_check_verify_full_suite_dotnet_test_without_filter_is_error`, following the exact structure of the existing `test_check_verify_full_suite_go_test_dotdotdot_*` tests in this file (a `tempfile.TemporaryDirectory()` block, `_make_overview([{"name": "alpha", "file": "01-alpha.md"}])`, a batch built via `_make_verify_only_batch_text("alpha", "<verify_command>")`, `_write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])`, then `_plan_validate.run(plan_dir, project_root)` and asserting on `[e for e in result if e["check"] == "verify-full-suite"]`):

  1. `test_check_verify_full_suite_go_test_compound_command_scoped_dotdotdot_is_ok() -> int` — "Clean: compound command where ./... belongs to a later go vet invocation, not the earlier go test -> no verify-full-suite error (#961)." Batch verify command: `"go test ./internal/quarryengine/lsp/ && go vet -tags lsp ./..."`. Assert `check_full_suite` is empty (same shape as the existing `..._with_run_is_ok` clean-test pattern: print FAIL with the unexpected list and return 1 if non-empty, else print PASS and return 0).

  2. `test_check_verify_full_suite_go_dash_c_test_dotdotdot_without_run_is_error() -> int` — "Dirty: 'go -C <dir> test ./...' (Go 1.20+ nested-module form) without a -run filter -> one verify-full-suite error (#933)." Batch verify command: `"go -C plugins/prowler test ./..."`. Assert exactly one `verify-full-suite` finding and that its `message` contains `"go test ./..."` (same assertion shape as the existing `..._without_run_is_error` dirty test).

  3. `test_check_verify_full_suite_go_dash_c_test_dotdotdot_with_run_is_ok() -> int` — "Clean: 'go -C <dir> test ./...' with a -run filter -> no verify-full-suite error." Batch verify command: `"go -C plugins/prowler test ./... -run TestFoo"`. Assert `check_full_suite` is empty.

  4. `test_check_verify_full_suite_done_gate_exact_match_is_ok() -> int` — "Clean: verify command exactly equals the configured done_gate -> no verify-full-suite error even though it would otherwise match the go-test branch (#950)." Batch verify command: `"go test ./... && go test -tags integration ./..."`. Call `_plan_validate.run(plan_dir, project_root, done_gate="go test ./... && go test -tags integration ./...")` (the same string as the verify command, passed as the new `done_gate` keyword argument). Assert `check_full_suite` is empty.

  5. `test_check_verify_full_suite_done_gate_subset_still_flagged() -> int` — "Dirty: verify command is a scoped SUBSET of done_gate, not an exact match -> still flagged (exact-match only, not prefix/subset)." Batch verify command: `"go test ./..."`. Call `_plan_validate.run(plan_dir, project_root, done_gate="go test ./... && golangci-lint run")` (a done_gate that is a superset of the batch's own command, not equal to it). Assert exactly one `verify-full-suite` finding (same assertion shape as test 2 above).

  Each test function follows the file's established `try/except AssertionError` + `print("PASS ...")`/`print(f"FAIL ...", file=sys.stderr)` + `return 0`/`return 1` convention exactly as the neighboring existing tests do — do not introduce a different assertion style.

  Register all 5 new test functions in the module-level `tests = [...]` list inside `main()`, immediately after the existing `test_check_verify_full_suite_bare_pytest_no_python_marker_clean` entry and before the `# verify cwd mapping form (Cards 23-25 / #604)` comment, under a new comment line `# verify-full-suite: segment scoping + done_gate exemption (#933, #950, #961)`, listing the 5 function names in the same order they were defined above.
- **Commit:** `test(plan-validate): cover go-test segment scoping and done_gate exemption`

## Batch Tests

`verify:` runs the full `test-plan-validate.py` suite, which includes the 5 new tests added by Card 3 plus every pre-existing test (including the untouched `run-all.py`/dotnet/pytest/mapping-form/overview-level `verify-full-suite` tests, which regression-guard that this batch's additions did not disturb the unrelated branches).
