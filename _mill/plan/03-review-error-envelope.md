# Batch: review-error-envelope

```yaml
task: '66 (A) -- Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv'
batch: review-error-envelope
number: 3
cards: 7
verify: python plugins/mill/unit_tests/test-review-cli-error-envelope.py
depends-on: []
```

## Batch Scope

Unify the exit-code contract across the three reviewer CLIs (#338). Engine-internal failures inside `run()` (parse_verdict, LLMError) MUST return a `ReviewResult` with `verdict: "ERROR"` so the CLI emits a JSON envelope on stdout and exits 0. Pre-launch failures (config load, slug derivation, registry validation, plan validator findings, --extra-file resolution) keep their current behaviour: print human-readable line on stderr + JSON envelope on stdout + exit 1.

The conceptual contract becomes: **exit 0 + envelope** = "the engine ran a round" (success OR retryable failure); **exit 1 + envelope** = "the engine never ran" (operator must intervene). mill-go's ERROR-only-aggregate retry path triggers on top-level `verdict: "ERROR"` regardless of exit code; aligning the exit codes removes a category of false-positive operator panic.

Discussion-review additionally converts its `except LLMError: raise ReviewError` branch to return a `verdict: ERROR` ReviewResult, mirroring `_review_code.run`'s existing LLMError branch.

Plan-review is VERIFY/ADJUST ONLY: the per-batch path (`_review_plan.py` line 251) and the holistic path (line 607) already catch `ReviewError` from `parse_verdict` and emit `verdict: ERROR` entries. Card 7 confirms the entry-shape parity with the Shared Decisions "ReviewResult ERROR shape" and aligns dict keys only if drift is found.

External interface: the three CLI scripts (`millpy-review-{discussion,plan,code}.py`) keep their JSON envelope shape on stdout. Only the exit code changes for engine-internal errors. mill-go's polling loop already extracts the JSON line from the bg log -- the script's exit code is not load-bearing for that polling path.

## Cards

### Card 5: `_review_discussion.run` -- catch LLMError + parse_verdict ReviewError, return verdict:ERROR

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_discussion.run`:

  1. Replace the existing LLMError branch (currently lines 116-119):
     ```python
     try:
         raw, session_id = _reviewer_single.run(spec, prompt_text)
     except LLMError as exc:
         raise ReviewError(f"All sub-reviews failed: {exc}") from exc
     ```
     with the verdict-ERROR-return shape: catch `LLMError`, build the canonical ERROR review entry per the Shared Decisions "ReviewResult ERROR shape" with `scope="holistic"` and `session_id=None`, and `return ReviewResult(type="discussion", round=round_n, verdict="ERROR", blocking_count=0, reviews=[<entry>])`. The `from exc` chain is no longer needed since the value lives in the entry's `error` field; do not preserve the `raise`.
  2. Wrap the `verdict = parse_verdict(raw)` call (currently line 122) in `try/except ReviewError as exc:` and on catch, build the same ERROR entry (`scope="holistic"`, the `raw` text is NOT included in the entry but IS written to disk via `write_review_file(reviews_dir, "discussion", round_n, raw)` before the return so the operator can inspect the malformed reviewer output; pass `session_id` from the just-succeeded LLM call into the entry's `session_id` field). Return `ReviewResult(type="discussion", round=round_n, verdict="ERROR", blocking_count=0, reviews=[<entry>])`.
  3. After both changes, the only `raise ReviewError` calls remaining in this function are the pre-LLM-call guards at lines 65-67 (round-cap check) and lines 76-77 (reviewer-null check). Those stay as-is -- they are pre-launch errors.

  Import `ReviewResult` is already in the existing import block at lines 20-34; no new imports required.
- **Commit:** `fix(review-discussion): return verdict:ERROR ReviewResult for engine-internal failures`

### Card 6: `_review_code.run` -- catch parse_verdict ReviewError around both call sites

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** `_review_code.run` already catches `LLMError` at two sites (lines 320-334 for the initial call, lines 359-373 for the NEED_CONTEXT resume retry) and returns verdict-ERROR ReviewResults. The remaining gap is `parse_verdict`:
  1. Wrap `verdict = parse_verdict(raw)` at line 336 in `try/except ReviewError as exc:`. On catch, write the raw output to disk via `write_review_file(reviews_dir, "code", round_n, raw, scope=batch_name)` (same call shape as the success path at lines 378-384), build the canonical ERROR entry per the Shared Decisions "ReviewResult ERROR shape" with `scope=scope_label`, `session_id=session_id`, and return `ReviewResult(type="code", round=round_n, verdict=_aggregate_top_verdict([<entry>], "REQUEST_CHANGES"), blocking_count=0, reviews=[<entry>])`. The `_aggregate_top_verdict` helper (lines 68-74) collapses all-ERROR to top-level `"ERROR"`, so this single-entry list aggregates to top-level `"ERROR"` correctly.
  2. Wrap `verdict = parse_verdict(raw)` at line 374 (post-NEED_CONTEXT resume retry) in the same `try/except ReviewError as exc:` with the same entry-build pattern; the `session_id` in scope is the one from the resume call.

  Do not add a try/except around `parse_blocking_count` (line 377) -- it returns 0 on a malformed input and never raises.
- **Commit:** `fix(review-code): return verdict:ERROR ReviewResult when parse_verdict raises`

### Card 7: `_review_plan.py` -- verify-and-adjust ERROR entry shape to match Shared Decisions

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Open `_review_plan.py`. Locate the two existing `verdict: "ERROR"` return sites:
  1. Per-batch path (currently lines 251-260): `except ReviewError as exc: return {"scope": ..., "round": ..., "verdict": "ERROR", "blocking_count": 0, "file": None, "error": str(exc), "session_id": None}`.
  2. Holistic path (currently lines 607-617): `except ReviewError as exc: ... reviews.append({"scope": "holistic", "round": ..., "verdict": "ERROR", "blocking_count": 0, "file": str(path), "error": f"parse_verdict failed: {exc}", "session_id": session_id})`.

  Apply these adjustments:
  - Per-batch entry (a): align the `error:` field's value to a plain `str(exc)` (it already is) and confirm `file: None` matches the Shared Decisions shape. No change needed if it already matches; no-op is the expected result.
  - Holistic entry (b): keep the `file: str(path)` value (the raw output IS written to disk in this path, which is preferable to `None`); align the `error:` prefix to a bare `f"parse_verdict failed: {exc}"` (it already is). No change needed if it already matches.
  - Keep the existing `round:`, `blocking_count:` fields in both entries -- they are part of the plan-review per-entry contract that pre-dates the unified ERROR shape and the aggregator at line 622 reads `round:` from per-entry dicts.
  - Confirm the aggregator block at lines 619-621 collapses all-ERROR to top-level `"ERROR"`. If it does (it currently does), no change.

  Net effect: this card is expected to result in zero or minimal diff to `_review_plan.py`. If the implementer finds genuine drift (e.g. a key was renamed in a later commit), align the dict shape to Shared Decisions "ReviewResult ERROR shape" exactly and update the commit message to mention what was aligned. If no drift is found, commit only this card's no-op `git commit --allow-empty` is forbidden; instead skip the card's commit and proceed to the next card. (mill-go's per-card commit machinery handles "no diff" gracefully; if the implementer's commit-once-per-card pattern blocks a no-op, the implementer adds a brief inline comment to `_review_plan.py` documenting the entry-shape parity check date and includes that single comment-line change in the commit. The decision is the implementer's; both outcomes are acceptable.)
- **Commit:** `chore(review-plan): verify verdict:ERROR entry shape parity with shared decision`

### Card 8: `millpy-review-discussion.py` -- only pre-launch failures exit 1

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/scripts/_review_discussion.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** No structural change is required to `millpy-review-discussion.py` -- the existing top-level `try/except ReviewError as exc: print_error_envelope(...); return 1` block at lines 61-63 already handles every ReviewError the CLI sees. After Card 5, `_review_discussion.run` no longer raises `ReviewError` on engine-internal failures (it returns `verdict: ERROR` ReviewResult instead), so the only `ReviewError`s reaching this except block are PRE-LAUNCH errors raised inside `find_active_slug` or `run`'s pre-LLM-call guards (round-cap, reviewer-null) -- both legitimately exit 1.

  Add a one-line comment immediately above the `except ReviewError as exc:` block at line 61 reading: `# Pre-launch errors only -- engine-internal failures return verdict:ERROR via run() (#338).`

  Verify by re-reading the full file that no other code path produces an envelope-less exit 1. No imports change.
- **Commit:** `docs(millpy-review-discussion): note pre-launch-only ReviewError catch`

### Card 9: `millpy-review-code.py` -- only pre-launch failures exit 1

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Same shape as Card 8. The existing `except ReviewError as exc: print_error_envelope("code", str(exc)); return 1` at lines 106-108 handles pre-launch ReviewError. After Card 6, `_review_code.run` only raises pre-launch ReviewErrors (path-resolution failures, round-cap, reviewer-null at lines 213-282; the `parse_verdict` failures are now caught inside `run`). Add a one-line comment immediately above the `except ReviewError as exc:` block at line 106 reading: `# Pre-launch errors only -- engine-internal failures return verdict:ERROR via run() (#338).`

  Confirm `--extra-file not found` (line 88) and `_reviewers.ReviewerError` (line 78) keep their exit 1 paths -- both are pre-launch.
- **Commit:** `docs(millpy-review-code): note pre-launch-only ReviewError catch`

### Card 10: `millpy-review-plan.py` -- only pre-launch failures exit 1

- **Context:**
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Same shape as Cards 8-9. The existing `except ReviewError as exc: print_error_envelope("plan", str(exc)); return 1` at lines 116-118 handles pre-launch ReviewError. `_review_plan.py` already catches `parse_verdict` failures internally (per-batch line 251, holistic line 607) and returns `verdict: ERROR` entries -- no Card-6-equivalent change is required to the backend (Card 7 only verifies entry-shape parity).

  Add a one-line comment immediately above the `except ReviewError as exc:` block at line 116 reading: `# Pre-launch errors only -- engine-internal failures return verdict:ERROR via run() (#338).`

  Confirm the plan-validator findings path at lines 98-103 keeps its `print(json.dumps({"errors": errors, ...})); return 1` shape -- validator findings are intentionally exit 1 (not retryable; the plan needs human edit).
- **Commit:** `docs(millpy-review-plan): note pre-launch-only ReviewError catch`

### Card 11: unit test for CLI exit-code contract across all three review CLIs

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- **Deletes:** none
- **Requirements:** Create a `unittest.TestCase` test file that exercises the exit-code contract for all three reviewer CLIs without invoking a real LLM. Use `unittest.mock.patch` to stub every pre-launch dependency AND the backend's `run` function, then assert the contract for three paths:
  1. **Engine-internal failure path**: when `<backend>.run` is patched to return `ReviewResult(type="discussion", round=1, verdict="ERROR", blocking_count=0, reviews=[{"scope": "holistic", "verdict": "ERROR", "file": None, "error": "synthetic", "session_id": None}])`, the CLI's `main(argv)` MUST return 0 AND stdout MUST parse as JSON whose top-level `verdict` field equals `"ERROR"`.
  2. **Pre-launch failure path**: when `find_active_slug` (imported INTO the CLI module) is patched to raise `ReviewError("pre-launch test")`, the CLI's `main(argv)` MUST return 1 AND stdout MUST parse as JSON whose top-level `verdict` field equals `"ERROR"` (via `print_error_envelope`) AND stderr MUST contain `ERROR: pre-launch test`.
  3. **Success path**: when `<backend>.run` is patched to return `ReviewResult(type="discussion", round=1, verdict="APPROVE", blocking_count=0, reviews=[{"scope": "holistic", "verdict": "APPROVE", "file": "/tmp/x.md", "session_id": "abc"}])`, the CLI's `main(argv)` MUST return 0 AND stdout MUST parse as JSON whose top-level `verdict` field equals `"APPROVE"`.

  **Pre-launch dependency patches (applied for every test case):** the three CLI `main()` functions all call several module-level helpers BEFORE reaching `find_active_slug` or the backend `run()`. In a bare temp/test directory these calls fail and the CLI would short-circuit to a pre-launch envelope, masking the assertions. Patch each of the following with a no-op or canned return so execution reaches the backend dispatch:
  - `_paths.resolve_wiki_path` -> returns a dummy `Path` (e.g. `Path(tempdir)`).
  - `_review_common.load_config` -> returns a minimal cfg dict containing at least `{"paths": {...}, "roles": {...}}` (the patched value need not satisfy schema; the engine call is patched too).
  - `_reviewers.load` -> returns `{}` (empty registry).
  - `_reviewers.validate_role_refs` -> no-op (`MagicMock(return_value=None)`).
  - `Path.cwd` -> returns the tempdir so `project_root` resolves to a writable location.

  Each CLI imports these names locally inside `main()` (e.g. `from _paths import resolve_wiki_path`). The patches must target the binding in the CLI module's namespace AFTER the import line executes -- the conventional `unittest.mock.patch("millpy_review_discussion._paths.resolve_wiki_path")` style does not work because the CLIs use bare-name imports. Instead, patch the source module directly: `unittest.mock.patch("_paths.resolve_wiki_path", return_value=Path(tempdir))`. This works because Python's import system caches the lookup at the module table, and the CLI's local-import in `main()` re-binds to the patched value on each call.

  If a particular CLI fails to reach `find_active_slug` despite the patches above, debug by adding `print(f"reached {checkpoint}", file=sys.stderr)` lines in the test to identify which pre-launch step is short-circuiting, and add the missing patch. Do not paper over failures with broad `unittest.mock.patch.object` blanket patches.

  Parameterise across the three CLIs via a helper method `_run_cli(self, cli_module_name, backend_module_name, backend_run_return, *, raise_find_slug=False)` or by subclassing -- minimise duplication. The test captures stdout/stderr via `io.StringIO` patched into `sys.stdout`/`sys.stderr`; do NOT spawn subprocesses.

  Note for the implementer: the three CLIs differ in their backend imports (`_review_discussion.run` vs `_review_code.run` vs `_review_plan.run`) and in the second pre-launch path (`millpy-review-plan.py` has the plan-validator gate at lines 95-103 that emits a non-ERROR-envelope JSON shape -- exclude the validator from this test by patching `_plan_validate.run` to return `[]` (empty errors list); the validator's own tests cover it separately).

  Standalone-runnable (`python plugins/mill/unit_tests/test-review-cli-error-envelope.py`) and via `run-all.py`.
- **Commit:** `test(review-cli): cover exit-0-with-envelope contract for engine-internal failures`

## Batch Tests

`verify:` runs `test-review-cli-error-envelope.py`. The three cases (engine-internal ERROR, pre-launch ERROR, APPROVE) across three CLIs give nine assertion combinations -- enough coverage that a future regression on either the exit code or the envelope shape will trip the test.

Manual smoke: after this batch is merged, run any one of the three reviewer CLIs against a discussion or plan that has a known-good fenced-yaml verdict block (e.g. the discussion in this very task). Confirm the CLI exits 0 with the APPROVE envelope on stdout. Then induce a parse failure by temporarily corrupting the reviewer output (e.g. via a unit fixture, not in production) and confirm exit 0 with ERROR envelope.
