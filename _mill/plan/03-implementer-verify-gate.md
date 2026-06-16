# Batch: implementer-verify-gate

```yaml
task: Fix unit test suite failures, spurious review warning, and implementer verify-gate gaps
batch: implementer-verify-gate
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py test-millpy-fix.py
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
default `None`); card 6 resolves the batch verify command and threads it through
the finalize/full callsites of BOTH `millpy-implement.py` and `millpy-fix.py`
(the fixer path shares the same false-success risk on the review-fix path; the
gate is threaded for batch-scope fixes, with holistic fixes passing `None`);
card 7 adds tests. The new parameter defaults to `None`, so existing callsites
and the pre-existing `test-implementer-common.py` cases keep passing unchanged.

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

### Card 6: Resolve and thread the batch verify command through the implementer and fixer CLIs (#488)

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In BOTH CLIs, resolve the batch's verify command via
  `_plan_dag._read_batch_frontmatter(batch_file).get("verify")` — use `.get`,
  NOT `["verify"]`, so a missing/malformed frontmatter (`{}`) or a batch without
  a `verify:` key yields `None` (treated as "nothing to run").
  In `millpy-implement.py`: pass the resolved value as `verify_cmd=` to
  `finalize_from_output(...)` in the `--stage finalize` branch (where
  `batch_file` is already in scope) and to `_forward_output(...)` in the `full`
  stage (the call near the end of `main`).
  In `millpy-fix.py`: the fixer finalize/full paths call the same
  `finalize_from_output` / `_forward_output` and have the identical
  false-success risk on the review-fix path. Thread `verify_cmd` for BATCH scope
  only — in the `--stage finalize` branch resolve `batch_file` from
  `args.batch_name` against the already-parsed `batches`/`plan_base` (both
  defined above the finalize branch) when `args.scope == "batch"`, read its
  `.get("verify")`, and pass it to `finalize_from_output(...)`; for the `full`
  stage set a `verify_cmd` local in the batch-scope branch (from `batch_file`)
  and `None` in the holistic branch, then pass it to the shared
  `_forward_output(...)` tail. For `--scope holistic` pass `verify_cmd=None`
  (there is no single batch verify for a holistic fix) — document that one-line
  exclusion in the code comment. The agent-dispatch `prepare`->`finalize` split
  is gated for both CLIs because the separate `finalize` invocation resolves and
  passes `verify_cmd` itself.
- **Commit:** `feat(implementer): resolve batch verify command for the implement and fix finalize gates (#488)`

### Card 7: Unit tests for the finalize verify gate (#488)

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add test cases for `_forward_output` (and/or
  `finalize_from_output`) exercising `verify_cmd`. CRITICAL — match this file's
  ACTUAL convention: `test-implementer-common.py` is a `main()` runner with
  `sys.exit(main())` and NO `unittest.main()`; it uses the module-level helpers
  `_setup_fixture(project_root)` (git-inits a temp repo) and `_capture_stdout(fn)`
  (runs a callable, returns `(rc, captured)`), with each case block inside
  `main()`. Add the new cases the SAME way — inside `main()`, using
  `_setup_fixture` + `_capture_stdout` and the file's existing failure
  accounting. Do NOT add a `unittest.TestCase` class (it would never be
  discovered or run, so the new coverage would silently be skipped while verify
  stays green). Cases: (a) agent output containing a `{"status":"success",...}`
  line with a failing `verify_cmd` (a portable always-fail command, e.g. a
  Python one-liner `python -c "import sys; sys.exit(1)"` or `exit 1`) -> the
  parsed emitted JSON has `status == "stuck"` and `stuck_type == "verify"` with
  the failure output in `reason`; (b) same success output with a passing
  `verify_cmd` (e.g. `exit 0`) -> emitted JSON keeps `status == "success"`;
  (c) `verify_cmd=None` -> success preserved (current behaviour); (d) an
  inferred-success scenario (no JSON status line, HEAD advanced, tree clean) with
  a failing `verify_cmd` -> `stuck_type == "verify"`. Keep the file's existing
  cases passing (they call without `verify_cmd`).
- **Commit:** `test(implementer): cover the finalize verify gate (#488)`

## Batch Tests

`verify:` runs `run-all.py --only test-implementer-common.py
test-millpy-implement.py test-millpy-fix.py`. `test-implementer-common.py`
covers the gate logic (card 7's new cases plus the pre-existing cases, which
must stay green). `test-millpy-implement.py` and `test-millpy-fix.py` are re-run
to confirm the card-6 threading into each CLI introduces no regression in the
CLIs' stage handling. All three files are scoped to the modules this batch
edits.
