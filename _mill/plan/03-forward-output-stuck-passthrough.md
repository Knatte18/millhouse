# Batch: forward-output-stuck-passthrough

```yaml
task: 'Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep'
batch: 'forward-output-stuck-passthrough'
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-json-contract.py test-agent-mode-dispatch.py test-millpy-merge-in-subagent.py
depends-on: []
```

## Batch Scope

Commit `6d92c82d` (2026-07-29, fixing #744) added strict `_is_valid_commit_sha` validation to
`_forward_output`'s corrective commit-SHA block, but that block runs unconditionally on every
non-`success`, non-`incomplete` code path that reaches it — including an already self-classified
`{"status": "stuck", "stuck_type": "transient"/"verify", ...}` envelope. If the corrective
`git rev-parse HEAD` call fails validation on that passthrough path, a correctly-classified stuck
report is silently corrupted into `stuck/logic`, misrouting mill-go's retry-vs-halt logic. Three
test files' fake commit-SHA constants (`"abc1234"`, `"def5678"`, short non-hex strings) currently
trip this same validation and surface the bug as 8 test failures. One production-code fix (gate the
block to `status == "success"` only) plus three test-file fixes plus one new regression test, all
tightly coupled to the same shared `_forward_output` contract — one batch, four cards.

## Cards

### Card 5: Gate `_forward_output`'s commit-SHA correction to the success path

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_forward_output()` (`_implementer_common.py:1559+`), the tail block at
  `:1790-1809` — beginning at `result = _subprocess_util.run(["git", "rev-parse", "HEAD"],
  cwd=project_root)` and ending at the `else` branch's `print(json.dumps(_correction_failure))` —
  currently runs unconditionally for any `parsed` that reached this point without an earlier
  `return 0` (i.e. any status other than the `"success"`-that-passed-every-gate case handled above
  it, and any status other than `"incomplete"` handled immediately above it). Gate this entire
  block behind `if parsed.get("status") == "success":` (checking the input's own top-level status
  at this point in the function, not a value derived from the earlier `if` branches), with an
  `else: print(json.dumps(parsed))` branch that emits the untouched envelope — no `git rev-parse`
  call, no `_is_valid_commit_sha` validation, no `commit_sha`/`scope_violations` mutation. Keep
  `return 0` unconditional immediately after the `if`/`else`. The success-path behavior inside the
  new `if` branch must remain byte-for-byte identical to today: a self-reported `commit_sha` is
  still replaced by the freshly-validated `git rev-parse HEAD` value, `scope_violations` is still
  attached the same way when `_cleanliness.compute_scope_violations` returns any, and validation
  failure still demotes to the existing `_correction_failure` dict
  (`{"status": "stuck", "stuck_type": "logic", "reason": "commit_sha correction failed: ...",
  "session_id": ...}`) unchanged.
- **Commit:** `fix(implementer): narrow _forward_output's commit-SHA correction to the success path only`

### Card 6: Fix success-path SHA mock and add stuck-passthrough regression test

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-bg-json-contract.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `test_forward_output_success_with_json_in_output` (`test-bg-json-contract.py:~117-136`),
    change the mocked `git rev-parse HEAD` stdout at `:126` (currently `"new_sha_123\n"`) to a
    well-formed 40-character lowercase hex string, e.g. `"a" * 40 + "\n"`, so `_is_valid_commit_sha`
    accepts it and the test's `status == "success"` assertion holds under Card 5's still-active
    success-path validation.
  - `test_forward_output_stuck_transient` (`:~144-162`) and `test_forward_output_stuck_verify`
    (`:~170-188`) need NO change: their inputs are already `{"status": "stuck", ...}`, so after
    Card 5's fix they no longer reach the SHA-correction block at all — their existing
    `"sha_123"`/`"sha_456"` corrective-rev-parse mocks become dead but harmless. Do not touch these
    two tests.
  - `test_forward_output_stuck_no_json_fallback` needs no change — it has no `git rev-parse` mock
    at all and never had a `"success"` status; it must keep emitting `stuck_type: "logic"`.
  - Add a new test function, `test_forward_output_stuck_verify_passthrough_survives_bad_corrective_sha`,
    that calls `_forward_output` with output containing an already-well-formed
    `{"status": "stuck", "stuck_type": "verify", "session_id": "fake-session"}` JSON body, mocks
    `_subprocess_util.run` so a `git rev-parse HEAD` call would return a non-hex/malformed stdout
    (e.g. `"not-a-sha\n"`) or a non-zero returncode, and asserts the parsed output's `stuck_type` is
    still `"verify"` (unchanged) and `status` is still `"stuck"`. This is the specific regression
    Card 5's narrower gating exists to prevent: an already-classified `stuck` envelope must never be
    corrupted by an unrelated corrective-SHA failure, because after Card 5's fix the mocked
    `git rev-parse HEAD` call is never even invoked on this path.
- **Commit:** `test: fix success-path SHA mock and add stuck-passthrough regression test in test-bg-json-contract.py`

### Card 7: Use well-formed hex SHA in test-agent-mode-dispatch.py's finalize-stage mock

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `TestImplementerModeParity.setUp` (`test-agent-mode-dispatch.py:~196-198`),
  change `self._finalize_head_sha` (currently `"def5678"`) to a well-formed 40-character lowercase
  hex string, e.g. `"d" * 40`. This is the value the mocked `git rev-parse HEAD` returns once
  `test_implementer_parity_finalize_stage` sets `self._in_finalize = True` (`:298`), and it is what
  `_forward_output`'s corrective rev-parse reads on the `status == "success"` path — it must pass
  `_is_valid_commit_sha` for that test's `self.assertEqual(data["status"], "success")` assertion
  (`:314`) to hold. Do not change `self._prepare_head_sha` (`"abc1234"`, `:197`) — it is only used
  for prepare-stage `start_sha` comparisons and is unrelated to the SHA-validation path. No
  assertion in this test checks the literal `commit_sha` string value
  (`self.assertIn("commit_sha", data)` only), so no other change is needed. This fixture is shared
  with `test_implementer_parity_prepare_stage`, which never sets `_in_finalize = True` and never
  exercises `_is_valid_commit_sha` — it is unaffected and must remain passing.
- **Commit:** `test: use well-formed hex SHA for finalize-stage rev-parse mock in test-agent-mode-dispatch.py`

### Card 8: Use well-formed hex SHA in test-millpy-merge-in-subagent.py's shared clean-gate mock

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the shared module-level helper `_clean_gate_side_effect`
  (`test-millpy-merge-in-subagent.py:~32-44`), change the `git rev-parse HEAD` stdout at `:43`
  (currently `"abc1234\n"`) to a well-formed 40-character lowercase hex string, e.g.
  `"a" * 40 + "\n"`. This helper is shared by `test_1_conflicts_success` (`:~142`),
  `test_15_stage_finalize_conflicts` (`:~508`), `test_16_conflicts_discarded_field_preserved`
  (`:~544`), `test_17_conflicts_success_no_discarded_is_clean` (`:~578`), and
  `test_19_finalize_conflicts_accepts_parity_flags` (`:~661`) — none of the 5 assert the literal SHA
  string, only `status == "success"` (plus, for tests 16/17, the `discarded` field), so this single
  edit fixes all 4 currently-failing tests. `test_19` never reaches this code path (it mocks
  `finalize_from_output` directly at `:654`) and remains unaffected. The fake self-reported
  `"commit_sha":"abc"`/`"xyz"` strings embedded in some tests' mocked agent JSON output (e.g. `:138`,
  `:499`) are separate and unrelated — they are overwritten by `_forward_output` on the success path
  and must not be changed.
- **Commit:** `test: use well-formed hex SHA in test-millpy-merge-in-subagent.py's shared clean-gate mock`

## Batch Tests

`verify:` runs all three affected test files together via `run-all.py --only
test-bg-json-contract.py test-agent-mode-dispatch.py test-millpy-merge-in-subagent.py`. Confirms:
`test_forward_output_stuck_transient`/`test_forward_output_stuck_verify` see `stuck_type:
"transient"`/`"verify"` (not `"logic"`); the new
`test_forward_output_stuck_verify_passthrough_survives_bad_corrective_sha` passes; the six
previously-failing success-path tests across the three files
(`test_forward_output_success_with_json_in_output`, `test_implementer_parity_finalize_stage`,
`test_1_conflicts_success`, `test_15_stage_finalize_conflicts`,
`test_16_conflicts_discarded_field_preserved`, `test_17_conflicts_success_no_discarded_is_clean`)
now see `status: "success"`; and `test_forward_output_stuck_no_json_fallback` continues to
correctly emit `stuck_type: "logic"`.
