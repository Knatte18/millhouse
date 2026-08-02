# Batch: bug1-holistic-verify-subshell-wrap

```yaml
task: Verify/build gates leak shell state and ignore nested Go modules
batch: bug1-holistic-verify-subshell-wrap
number: 1
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-fix.py"
depends-on: []
```

## Batch Scope

Fixes #752: `_resolve_holistic_verify` in `millpy-fix.py` joins every
contributing batch's `verify:` command into one shell invocation with
plain `" && ".join(...)`. An unscoped `cd` in one batch's command leaks
its cwd change into every subsequent `&&`-joined batch command, since
they all run in one shell process. This batch wraps each contributing
command in its own subshell (`f"({command})"`) before joining, so a
`cd` (or any other cwd/env-mutating construct) in one batch's `verify:`
can never leak into the next, while preserving `&&` short-circuit
semantics between batches and the existing single-combined-output
failure-reporting shape. No external interface changes; this batch has
no downstream consumer within this plan (batch 2 is independent).

## Cards

### Card 1: Wrap each joined verify command in its own subshell

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_resolve_holistic_verify` (`plugins/mill/scripts/millpy-fix.py`),
  change the join line from:
  ```
  joined_command = " && ".join(command for _, command, _ in batch_verifies)
  ```
  to:
  ```
  joined_command = " && ".join(f"({command})" for _, command, _ in batch_verifies)
  ```
  Each batch's original `command` text is preserved verbatim inside its
  own parenthesized subshell segment; segments are still joined with
  `" && "` in the same order as `batch_verifies`. No other line in
  `_resolve_holistic_verify` changes — the cwd-conflict detection above
  it (`cwd_to_batch_name` / the `ValueError` raise) and the two call
  sites (`plugins/mill/scripts/millpy-fix.py` around line 451 and around
  line 574) are unaffected and require no edits.
- **Commit:** `fix(millpy-fix): wrap each holistic-verify batch command in its own subshell`

### Card 2: Unit-test the subshell-wrap join behavior

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-millpy-fix.py`, class `TestMillpyFix`,
  add two new test methods immediately after
  `test_holistic_scope_mixed_cwd_raises_value_error_naming_batches` (the
  method ending with the `self.assertIn("batch2", message)` assertion)
  and before `test_finalize_stage_batch_not_found_cwd_override_stays_none`.
  `_resolve_holistic_verify` is pure (no I/O), so both tests call
  `millpy_fix._resolve_holistic_verify(...)` directly — no CLI
  invocation, no fixture files beyond the class's existing `setUp`.

  1. `test_resolve_holistic_verify_wraps_each_command_in_own_subshell`:
     call `millpy_fix._resolve_holistic_verify([("batch-a", "cd plugins/prowler && go test ./...", None), ("batch-b", "bash plugins/prowler/scripts/selftest.sh", None)])`,
     capturing the returned `(joined_command, cwd_override)`. Assert
     `joined_command == "(cd plugins/prowler && go test ./...) && (bash plugins/prowler/scripts/selftest.sh)"`
     and `cwd_override is None`.
  2. `test_resolve_holistic_verify_single_batch_still_wrapped`: call
     `millpy_fix._resolve_holistic_verify([("batch-a", "echo hi", None)])`,
     assert the returned `joined_command == "(echo hi)"` (a single
     contributing batch is still wrapped in parens, no bare `&&` needed)
     and `cwd_override is None`.
- **Commit:** `test(millpy-fix): cover _resolve_holistic_verify's per-batch subshell wrap`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-millpy-fix.py` in full
(the entire `TestMillpyFix`/`TestMillpyFixBriefSizeGuard` suite already
runs in well under a minute — it is a single in-process unittest file
with no real LLM/network calls) so the two new tests run alongside the
existing `_resolve_holistic_verify`-adjacent coverage
(`test_holistic_derived_verify_cmd_two_batches_failing/passing`,
`test_holistic_scope_mixed_cwd_raises_value_error_naming_batches`) that
already exercises the same function's cwd-conflict path.
