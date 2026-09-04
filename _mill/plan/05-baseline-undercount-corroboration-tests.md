# Batch: baseline-undercount-corroboration-tests

```yaml
task: 'millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting'
batch: baseline-undercount-corroboration-tests
number: 5
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: [4]
```

## Batch Scope

Split out of `04-baseline-undercount-corroboration` (round-5 plan review): combining this test card
with batches 4's implementation cards pushed that batch's context-token estimate to ~124,451 against
the 120,000 cap — `test-implementer-common.py` alone is ~238KB. This batch adds the unit tests for
the `start_sha`-checkout corroboration path Card 7 (batch 4) added to `_run_verify_gates`, and
depends on batch 4 having already landed (it patches/calls the new
`_corroborate_batch_failure`/`start_sha`/`status_path`/`batch_name` symbols and parameters Card 7
introduces — this card cannot be implemented or run against `main`, only against batch 4's own
commits). It needs only `_implementer_common.py` and `_status.py` as Context — not
`_verify_baseline.py`/`_worktree.py`/`millpy-implement.py` (batch 4's own Context/Edits), since it
exercises the corroboration path only through `_run_verify_gates`'s public behavior, never by
reading those other modules directly.

## Cards

### Card 9: Unit tests for the corroboration path

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add new test cases to `test-implementer-common.py`, placed immediately after the existing "Case 72
  -- _run_verify_gates batch_verify_baseline subset-diff matrix" cases — this matrix actually has
  five existing sub-cases today, 72a through 72e (72e: "a stuck dict with no 'signatures' key must
  never be waived"), not four; insert the new cases after 72e and before the following, unrelated
  "Case 73" (a dirty-tree regression test), using the same `_setup_fixture(project_root)` real-git-repo
  helper already defined in this file, which inits a repo with a seed base commit and returns that
  commit's SHA.

  New case "72f — corroboration succeeds: a start_sha checkout reproduces the same mismatch ->
  waived + baseline persisted". Setup: call `base_sha = _setup_fixture(project_root)`. Use a
  `verify_cmd` whose failure is content-independent (reproduces identically regardless of repo
  content, e.g. `"echo '--- FAIL: TestNew (0.00s)' && exit 1"`, matching case 72b's own
  content-independent command). Build a real `status.md` fixture using the established
  `_status.render_initial(...)` + `_status.init_batches(status_path, [...])` pattern (used
  identically in `test-millpy-fix.py`/`test-status.py`): write
  `_status.render_initial("Test Task", "test", "2026-01-01T00:00:00Z", "main", "test-slug",
  "test-branch")`'s return value to a `status_path` under `project_root` (e.g. `project_root /
  "_mill" / "status.md"`, creating the parent `_mill/` dir first), then call
  `_status.init_batches(status_path, ["01-test-batch"])` to seed one batch entry at `state: pending`
  with no `verify_baseline_failures` field yet. Call `_run_verify_gates(project_root,
  verify_cmd, None, batch_verify_baseline=["--- FAIL: TestOld (1.11s)"], start_sha=base_sha,
  status_path=<the fixture status.md path>, batch_name="01-test-batch")`. Assert the result is `None`
  (waived). Assert (via `_status.read_batches(status_path)`) that the `"01-test-batch"` entry's
  `verify_baseline_failures` now includes both the original `"--- FAIL: TestOld (1.11s)"` entry and
  the new `"--- FAIL: TestNew (0.00s)"` signature (self-healing persisted).

  New case "72g — corroboration fails to reproduce: still blocks". Setup: call `base_sha =
  _setup_fixture(project_root)`, then create and commit a new file in `project_root` (e.g.
  `(project_root / "marker.txt").write_text("x")` + `git add` + `git commit`) so `project_root`'s
  current `HEAD` differs from `base_sha` — this simulates "the batch's own commit". Use a
  `verify_cmd` whose result depends on that file's presence, e.g.
  `"test -f marker.txt && echo '--- FAIL: TestNew (0.00s)' && exit 1 || exit 0"` (fails at `HEAD`
  where `marker.txt` exists, passes at `base_sha` where it does not exist yet). Call
  `_run_verify_gates(project_root, verify_cmd, None, batch_verify_baseline=["--- FAIL: TestOld
  (1.11s)"], start_sha=base_sha, status_path=<a fresh status.md fixture built via the same
  `_status.render_initial`/`_status.init_batches` pattern as case 72f>, batch_name="01-test-batch")`. Assert the
  result is not `None` and `result["stuck_type"] == "verify"` (still blocks — the control run at
  `base_sha` passed, so the mismatch was not corroborated as pre-existing).

  New case "72h — backward compatibility: omitting start_sha never attempts corroboration". Re-run
  case 72b's exact scenario (a replay signature absent from baseline, `verify_cmd = "echo '--- FAIL:
  TestNew (0.00s)' && exit 1"`, `baseline = ["--- FAIL: TestFoo (9.99s)"]`) but this time patch
  `_implementer_common._corroborate_batch_failure` (via `unittest.mock.patch`) to raise
  `AssertionError("should not be called")` if invoked, then call `_run_verify_gates(project_root,
  verify_cmd, None, batch_verify_baseline=baseline)` with no `start_sha`/`status_path`/`batch_name`
  kwargs at all (matching every pre-existing call site in this codebase before this task). Assert the
  result is not `None` and the patched mock was never called — confirming `start_sha=None`
  (the default) short-circuits `_corroborate_batch_failure` before it does any git/filesystem work,
  so every pre-existing caller's behavior is provably unchanged.
- **Commit:** `test(implementer-common): cover the start_sha corroboration path and its backward compatibility`

## Batch Tests

`verify:` runs `test-implementer-common.py` directly (this batch's sole edited file, and the
location of all new corroboration tests: cases 72f/72g/72h).
