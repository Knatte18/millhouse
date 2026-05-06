# Batch: 01-bugfix-batch

```yaml
task: 23 (A) — mill infra bugfix-batch
batch: 01-bugfix-batch
cards: 6
verify: 'uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/unit_tests/run-all.py"'
depends-on: []
```

## Batch Scope

This batch fixes three independent bugs in the mill infra layer — bugs B, C, and D from the task description. Bug A (`_yaml_writer.quote_scalar width`) was already fixed in task 19 and is not touched here. The fixes are: (B) add `set_batch_fields` to `_status.py` for atomic multi-field batch updates, then use it in `millpy-implement.py`; (C) normalize `commit_sha` in `_forward_output` via `git rev-parse HEAD`; (D) replace `datetime.utcnow()` with `datetime.now(timezone.utc)` in `millpy-bg.py`. Cards 1–3 are the code fixes; cards 4–6 are the tests. Implement cards in order since card 2 depends on the `set_batch_fields` function introduced in card 1.

## Cards

### Card 1: Add `set_batch_fields` to `_status.py`

- **Reads:**
  - `plugins/mill/scripts/_status.py`
- **Modifies:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `set_batch_fields(status_path: Path, name: str, fields: dict[str, str | int | None]) -> None` immediately after the existing `set_batch_field` function. The function must: (1) validate every key in `fields` against `_BATCH_ALLOWED_KEYS` before any mutation — raise `ValueError` on unknown key; (2) if any field has key `"state"`, validate the value against `_BATCH_STATES` — raise `ValueError` on unknown state; (3) perform a single `read_batches → mutate all requested keys → _write_batches` cycle. If `name` is not found in the batches list, raise `ValueError("Batch {name!r} not present in {_BATCHES_HEADING}")` (same message as `set_batch_field`). This function is the atomic variant of `set_batch_field` for callers that need to update multiple fields at once without risking a partial write.
- **Commit:** `feat(_status): add set_batch_fields for atomic multi-field batch update`

### Card 2: Use `set_batch_fields` in `millpy-implement.py` + normalize `commit_sha`

- **Reads:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_status.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Three changes to `millpy-implement.py`:
  1. In the initial-dispatch path (the three consecutive `set_batch_field` calls for `state`, `start_sha`, and `implementer_session`), replace them with a single `set_batch_fields(status_path, args.batch_name, {"state": "running", "start_sha": start_sha, "implementer_session": session_id})` call. Import `set_batch_fields` from `_status` (it is already imported via `import _status` or the `from _status import ...` pattern — match whichever is present in the file).
  2. In the fix-cycle resume path (the three consecutive `set_batch_field` calls for `state`, `review_round`, and `review_file`), replace them with a single `set_batch_fields(status_path, args.batch_name, {"state": "fixing", "review_round": args.round, "review_file": str(review_file)})` call.
  3. Modify `_forward_output` to accept `project_root: Path` as a second parameter. After successfully extracting and parsing the JSON dict from the implementer output, run `subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=project_root)`. If the process exits with code 0, overwrite the `commit_sha` key in the parsed dict with `result.stdout.strip()` before printing `json.dumps(dict)`. If the process exits non-zero, forward the original JSON string unmodified (preserving the always-0 return contract). Update both call sites of `_forward_output` (one in the initial dispatch path, one in the fix-cycle path) to pass `project_root` as the second argument.
- **Commit:** `fix(millpy-implement): atomic batch-state writes + normalize commit_sha via git rev-parse`

### Card 3: Fix `datetime.utcnow()` in `millpy-bg.py`

- **Reads:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** On the line that imports `datetime` in the launcher section of `millpy-bg.py`, change `from datetime import datetime` to `from datetime import datetime, timezone`. On the line that calls `datetime.utcnow()`, change it to `datetime.now(timezone.utc)`. No other changes to the file.
- **Commit:** `fix(millpy-bg): replace deprecated datetime.utcnow() with timezone-aware form`

### Card 4: Tests for `set_batch_fields` in `test-status.py`

- **Reads:**
  - `plugins/mill/unit_tests/test-status.py`
  - `plugins/mill/scripts/_status.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Import `set_batch_fields` alongside the existing imports from `_status`. Add four tests using the existing sequential-letter naming convention (continuing from the last letter in use). Each test uses a `tempfile.NamedTemporaryFile` or writes a real `status.md` via `render_initial` / `init_batches` (follow the pattern the existing set_batch_field tests use for setup). Tests to add:
  - Success path: call `set_batch_fields(sp, "foundation", {"state": "running", "implementer_session": "sess123", "start_sha": "abc"})`, then assert `read_batches(sp)[0]` has all three fields set correctly. Print `"PASS: set_batch_fields writes multiple fields atomically"`.
  - Unknown key: call `set_batch_fields(sp, "foundation", {"nope": "x"})`, assert `ValueError` is raised. Print `"PASS: set_batch_fields rejects unknown key"`.
  - Unknown state: call `set_batch_fields(sp, "foundation", {"state": "finished"})`, assert `ValueError` is raised. Print `"PASS: set_batch_fields rejects unknown state"`.
  - Unknown batch name: call `set_batch_fields(sp, "missing", {"state": "running"})`, assert `ValueError` is raised. Print `"PASS: set_batch_fields rejects unknown batch name"`.
- **Commit:** `test(_status): add set_batch_fields tests`

### Card 5: Tests for `_forward_output` SHA normalization in `test-millpy-implement.py`

- **Reads:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two new test methods to the existing `_ForwardOutputTests` class (or equivalent), continuing the numbered naming (`test_fo_7_*`, `test_fo_8_*`):
  - `test_fo_7_sha_normalized`: mock `subprocess.run` to return code 0 with stdout `"aabbccdd" * 5 + "\n"` (40-char SHA). Call `_forward_output('{"status":"success","commit_sha":"abc1234","session_id":"x"}', Path("/fake"))`. Assert the printed JSON has `"commit_sha"` equal to the 40-char SHA. Use `unittest.mock.patch("millpy_implement.subprocess.run", return_value=mock_result)`.
  - `test_fo_8_sha_git_failure`: mock `subprocess.run` to return code 1 with empty stdout. Call `_forward_output('{"status":"success","commit_sha":"abc1234","session_id":"x"}', Path("/fake"))`. Assert the printed JSON has `"commit_sha"` equal to `"abc1234"` (original preserved). Verify return code is still 0.

  Note: `_forward_output` now requires a second `project_root: Path` argument — update any existing `test_fo_*` tests that call `_forward_output` directly to pass a `Path` argument (e.g., `Path("/fake")`), and patch `millpy_implement.subprocess.run` to avoid real git calls.
- **Commit:** `test(millpy-implement): add SHA normalization tests for _forward_output`

### Card 6: Test for UTC-aware timestamp in `test-millpy-bg.py`

- **Reads:**
  - `plugins/mill/unit_tests/test-millpy-bg.py`
  - `plugins/mill/scripts/millpy-bg.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add one new test `(m)` to the launcher mode section, after the last existing launcher test. The test verifies that calling `_launcher_main` does not emit a `DeprecationWarning` about `utcnow`. Use `warnings.catch_warnings(record=True)` with `warnings.simplefilter("always")` inside the mock context. After the call, assert that no `DeprecationWarning` whose message contains `"utcnow"` is present in the recorded warnings. Print `"PASS (m): no DeprecationWarning from utcnow in launcher"`. The test must mock both `subprocess.run` (git rev-parse) and `subprocess.Popen` to avoid real processes, following the existing test pattern in the file.
- **Commit:** `test(millpy-bg): verify no DeprecationWarning from UTC timestamp generation`

## Batch Tests

The `verify:` command runs `run-all.py` which discovers and executes all `test-*.py` files in `plugins/mill/unit_tests/`. The three relevant files are `test-status.py`, `test-millpy-implement.py`, and `test-millpy-bg.py`. All tests must pass with exit code 0.
