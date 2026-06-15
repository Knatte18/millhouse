MILL_REVIEW_BEGIN
# Review: Fix millpy-review-plan validator gaps and resolve_ref_paths path-doubling — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-15
```

## Findings

### [BLOCKING] Test 24/25 shadow the outer `errors` counter

**Location:** `plugins/mill/unit_tests/test-review-plan-flow.py:1259` and `:1306`
**Issue:** `errors = validate_run(...)` overwrites the outer integer `errors` counter (which tracks test failures for the whole `main()` function) with the list returned by `_plan_validate.run`. If the subsequent assertion fails, `errors += 1` raises `TypeError: can only concatenate list (not "int") to list`; if the assertion passes, `errors` remains a list, making the final `if errors:` guard always truthy when any validator finding was returned, falsely failing the entire test run.
**Fix:** Use a different local variable name (e.g. `validate_errors`) for the `validate_run(...)` return value in both tests.

### [BLOCKING] Tests 24/25 bypass the `--stage prepare` CLI path (Card 8 unfulfilled)

**Location:** `plugins/mill/unit_tests/test-review-plan-flow.py:1252-1283` and `:1291-1331`
**Issue:** Card 8 explicitly requires: "MUST invoke the CLI entry point `main(["--stage", "prepare", "--holistic-only"])` ... Do NOT reuse the `plan_run` harness for these two cases — it would exercise the `--stage full` backend and miss the prepare gate entirely." Both tests call `_plan_validate.run` directly, proving only that the validator function detects errors, NOT that `millpy-review-plan.main(["--stage", "prepare", ...])` correctly wires the validator gate. The #465 surface (prepare-stage gate) remains untested.
**Fix:** Invoke `main(["--stage", "prepare", "--holistic-only"])` (via `runpy` or subprocess as the plan prescribes) and assert on exit code, JSON envelope keys (`errors` vs `stage`), and brief file presence/absence.

### [NIT] `_plan_validate` git_root threading: negative test case omitted

**Location:** `plugins/mill/unit_tests/test-review-plan-flow.py:1241-1283`
**Issue:** The plan (Card 5) says "Add a contrasting assertion that omitting `git_root` (the default `None`) in that same subfolder-cwd layout still mis-resolves (documents why the thread is required) — or, if simpler, assert only the positive case and note the negative in a comment." Neither a contrasting assertion nor a comment exists; the negative case is silently absent with no note.
**Fix:** Add a one-line comment in test 24 explaining that the negative case (omitting `git_root`) is not tested here because the test calls the validator directly, not via the CLI, then cross-reference test-plan-validate.py for the underlying function coverage.

## Verdict

REQUEST_CHANGES
Two blocking bugs: outer `errors` counter clobbered in tests 24/25, and Card 8's `--stage prepare` CLI path is untested.
MILL_REVIEW_END
