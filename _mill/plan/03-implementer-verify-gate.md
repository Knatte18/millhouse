# Batch: implementer-verify-gate

```yaml
task: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps
batch: implementer-verify-gate
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py
depends-on: []
```

## Batch Scope

#488: the implementer finalize path (`_implementer_common._forward_output`,
reached via `finalize_from_output`) trusts the implementer's self-reported
`success` JSON and never re-runs `verify:`. When per-batch code review is
disabled there is no later stage that re-runs verify either, so a false-success
silently advances the batch. This batch adds an always-on verify gate: on a
`success` outcome, re-run the batch's `verify:` command against the
post-implementer HEAD and demote a failing verify to `stuck_type: verify`. Card
5 adds the gate to `_implementer_common.py` (new `verify_cmd` parameter,
default `None`); card 6 resolves the batch verify command in
`millpy-implement.py` and threads it through both the `finalize` branch and the
`full` stage; card 7 adds unit tests. The new parameter defaults to `None`, so
existing callsites and the pre-existing `test-implementer-common.py` cases keep
passing unchanged.

## Cards

### Card 5: Add the verify gate to _forward_output / finalize_from_output (#488)

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a keyword parameter `verify_cmd: str | None = None` to both
  `finalize_from_output` and `_forward_output` in `_implementer_common.py`;
  `finalize_from_output` forwards its `verify_cmd` to `_forward_output`. Add a
  module-level helper (e.g. `_run_verify_gate(project_root, verify_cmd) -> dict |
  None`) that, when `verify_cmd` is not `None`, runs `subprocess.run(verify_cmd,
  shell=True, capture_output=True, text=True, cwd=project_root)` (mirroring the
  precedent in `millpy-merge-in-subagent.py` lines ~175-194) and, on non-zero
  return code, returns the stuck dict `{"status": "stuck", "stuck_type":
  "verify", "reason": <tail>}` where `<tail>` is the LAST 2000 characters of
  `(stdout + stderr).strip()`; on success (rc 0) or `verify_cmd is None` returns
  `None`. In `_forward_output`, before EACH point that emits a `status: success`
  JSON (the parsed-success emit and all inferred-success emits), call the gate
  helper; if it returns a stuck dict, print that dict (with the same
  `commit_sha` enrichment the success path uses where applicable) and return
  instead of emitting success. The gate must run AFTER any formatter-drift
  auto-commit (`_commit_formatter_drift`), i.e. against the final HEAD, so every
  success emit is gated on the same clean state. Do not change behaviour when
  `verify_cmd is None` (current behaviour preserved exactly).
- **Commit:** `fix(implementer): re-run verify before approving a success report (#488)`

### Card 6: Resolve and thread the batch verify command in millpy-implement.py (#488)

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`, resolve the batch's verify command
  via `_plan_dag._read_batch_frontmatter(batch_file).get("verify")` — use `.get`,
  NOT `["verify"]`, so a missing/malformed frontmatter (`{}`) or a batch without a
  `verify:` key yields `None` (treated as "nothing to run"). Pass the resolved
  value as `verify_cmd=` to `finalize_from_output(...)` in the `--stage finalize`
  branch (where `batch_file` is already in scope) and to `_forward_output(...)`
  in the `full` stage (the call near the end of `main`). The agent-dispatch
  `prepare`->`finalize` split is gated because the separate `finalize` invocation
  resolves and passes `verify_cmd` itself.
- **Commit:** `feat(implementer): resolve batch verify command for the finalize gate (#488)`

### Card 7: Unit tests for the finalize verify gate (#488)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add unittest cases for `_forward_output` (and/or
  `finalize_from_output`) exercising `verify_cmd`, using a temporary git repo
  fixture (mirror the git-init/commit setUp pattern in
  `test-review-common-guard.py`) and capturing stdout to read the emitted JSON:
  (a) agent output containing a `{"status":"success",...}` line with
  `verify_cmd="exit 1"` (or a portable always-fail command) -> emitted JSON has
  `status == "stuck"` and `stuck_type == "verify"` with the failure output in
  `reason`; (b) same success output with `verify_cmd="exit 0"` -> emitted JSON
  keeps `status == "success"`; (c) `verify_cmd=None` -> success preserved
  (current behaviour); (d) an inferred-success scenario (no JSON status line, but
  HEAD advanced and tree clean) with a failing `verify_cmd` -> `stuck_type ==
  "verify"`. Keep existing cases in the file passing (they call without
  `verify_cmd`).
- **Commit:** `test(implementer): cover the finalize verify gate (#488)`

## Batch Tests

`verify:` runs `run-all.py --only test-implementer-common.py
test-millpy-implement.py`. `test-implementer-common.py` covers the gate logic
(card 7's new cases plus the pre-existing cases, which must stay green).
`test-millpy-implement.py` is re-run to confirm the `millpy-implement.py`
threading (card 6) introduces no regression in the CLI's stage handling. Both
files are scoped to the modules this batch edits.
