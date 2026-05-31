# Batch: fixer-inferred-success

```yaml
task: mill-go / mill-merge / plan-validator follow-up bugs (round 2)
batch: fixer-inferred-success
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py
depends-on: []
```

## Batch Scope

This batch fixes #398: when `millpy-fix.py` dispatches a holistic fixer session that commits work but exits without emitting the final JSON report, `_forward_output` falls through to `stuck_type: logic / no structured report`. The fix has two parts: (1) extend `_forward_output` in `_implementer_common.py` with a no-snapshot inferred-success branch that fires when `start_sha` is given but `snapshot_path` is None, and (2) capture `start_sha` in `millpy-fix.py` before the fixer session and pass it to `_forward_output`. Three new tests cover the new `_forward_output` branch; one new test covers the `millpy-fix.py` wiring.

## Cards

### Card 4: _implementer_common.py — extend _forward_output for no-snapshot inferred-success (#398)

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `_forward_output`, the current inferred-success check (the `try:` block after the JSON-regex path) begins with:
  ```python
  if start_sha is not None and snapshot_path is not None and snapshot_path.exists():
  ```
  Change this condition to `if start_sha is not None and snapshot_path is not None and snapshot_path.exists():` (unchanged) for the existing snapshot-based path, and add a new `elif start_sha is not None and snapshot_path is None:` branch immediately after the existing `if` block's closing logic (still inside the same `try/except Exception: pass` wrapper). The new `elif` branch must:
  1. Run `_subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)`.
  2. If returncode == 0 and `result.stdout.strip() != start_sha` (HEAD advanced):
     a. Run `_subprocess_util.run(["git", "-C", str(project_root), "status", "--porcelain", "--untracked-files=no"])`.
     b. If `result_full.stdout.strip()` is empty (clean tree): print `json.dumps({"status": "success", "commit_sha": head, "session_id": session_id or "unknown", "inferred": True})` and return 0.
     c. If tree is dirty: fall through (do not print stuck; let the sentinel below handle it).
  3. If HEAD has not advanced or returncode != 0: fall through.

  The existing `print(json.dumps({"status": "stuck", "stuck_type": "logic", "reason": "no structured report"}))` sentinel at the bottom is unchanged.
- **Commit:** `fix(_implementer_common): inferred-success path when start_sha given but no snapshot (#398)`

### Card 5: millpy-fix.py — capture start_sha before fixer session (#398)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In the shared dispatch tail of `millpy-fix.py` (the section after the batch/holistic branch, beginning with `try:` and `_implementer_claude.run(...)`), immediately before the `try:` block, add:
  ```python
  _sha_result = _subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)
  start_sha = _sha_result.stdout.strip() if _sha_result.returncode == 0 else None
  ```
  Then change the final `return _forward_output(output, project_root, session_id=session_id)` call to:
  ```python
  return _forward_output(output, project_root, start_sha=start_sha, session_id=session_id)
  ```
  No other changes to `millpy-fix.py`.
- **Commit:** `fix(millpy-fix): capture start_sha and pass to _forward_output (#398)`

### Card 6: test-implementer-common.py — three new tests for no-snapshot inferred-success (#398)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add three new test cases to the existing `main()` function in `test-implementer-common.py`, following the existing `with tempfile.TemporaryDirectory() as tmpdir:` pattern. Each test uses `_setup_fixture` (already defined in the file) to create a git repo and a base SHA.

  **Test A — no-snapshot inferred success:** After `_setup_fixture`, write and commit a new file so HEAD advances past base_sha. Call `_forward_output("", project_root, start_sha=base_sha)`. Assert return code is 0 and stdout JSON has `status == "success"` and `inferred == True`.

  **Test B — no-snapshot, HEAD unchanged:** Call `_forward_output("", project_root, start_sha=base_sha)` immediately after `_setup_fixture` (no new commit). Assert return code is 0 and stdout JSON has `status == "stuck"` and `stuck_type == "logic"`.

  **Test C — no-snapshot, HEAD advanced but dirty tree:** After `_setup_fixture`, write and commit a new file (HEAD advances). Then modify an already-tracked file WITHOUT committing — specifically `(project_root / "README.md").write_text("dirty", encoding="utf-8")` — so the modification appears under `git status --porcelain --untracked-files=no`. Call `_forward_output("", project_root, start_sha=base_sha)`. Assert return code is 0 and stdout JSON has `status == "stuck"` and `stuck_type == "logic"`.

  Each test increments `errors` on assertion failure and prints a descriptive message. Follow the exact error-counting pattern used in existing tests.
- **Commit:** `test(_implementer_common): cover no-snapshot inferred-success paths (#398)`

### Card 7: test-millpy-fix.py — new test for start_sha capture (#398)

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Read the existing `test-millpy-fix.py` to understand its mock/fixture approach. Add one new test that verifies `start_sha` is captured and forwarded.

  The test must mock `_subprocess_util.run` (or the relevant git subprocess) to return a known SHA for `git rev-parse HEAD` and also intercept the `_forward_output` call to assert that `start_sha` equals that known SHA. Use `unittest.mock.patch` if the existing file already uses it; otherwise follow the existing mocking pattern.

  If `test-millpy-fix.py` does not have an existing fixture for running `main()`, create a minimal one that covers only the `start_sha` capture: mock out the expensive calls (`_implementer_claude.run`, config loading, slug resolution) and assert that `_forward_output` receives a non-None `start_sha` keyword argument. Because `millpy-fix.py` imports `_forward_output` via `from _implementer_common import _forward_output`, patch the local binding: `unittest.mock.patch.object(millpy_fix, "_forward_output", side_effect=...)` to capture the `start_sha` kwarg — do NOT patch `_implementer_common._forward_output`, which would leave the local binding unaffected.

  Increment `errors` on failure, return 0 on success.
- **Commit:** `test(millpy-fix): verify start_sha is captured and passed to _forward_output (#398)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-fix.py`

Covers cards 4–7 directly. The `run-all.py --only` flag limits the run to the two affected test files; the full suite is not needed because the changed helpers (`_forward_output`, `millpy-fix.py`) have no other tests that would regress from this batch.
