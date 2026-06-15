# Batch: accept-session-start-sha-flags

```yaml
task: "Fix millpy-implement.py finalize to accept (or not require) --session-id/--start-sha"
batch: accept-session-start-sha-flags
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py
depends-on: []
```

## Batch Scope

Single batch delivering the entire fix: make `millpy-implement.py` accept the `--session-id` and
`--start-sha` flags that mill-go's agent-mode dispatch threads into the finalize call (mill-go
SKILL.md step 5, lines 127-129), so agent-mode implement batch finalize stops dying with
`error: unrecognized arguments: --session-id` (exit 2). The flags are accepted-but-ignored: the
`--stage finalize` branch continues to read `start_sha` and `implementer_session` from `status.md`,
unchanged. The batch is one unit because the two cards (argparse addition + its unit test) share the
same two files and the same logical change. Card 1 is a TDD card written first to pin the contract;
Card 2 makes it pass. No external interface is produced for a later batch — this is the whole task.

## Cards

### Card 1: TDD test — finalize accepts the flags and still uses status.md values

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-fix-finalize.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add one test method to the `TestMillpyImplement` class in
  `test-millpy-implement.py`, named `test_15_stage_finalize_accepts_session_and_start_sha_flags`.
  It must prove two things: (1) the implement CLI parses `--stage finalize` together with
  `--session-id` and `--start-sha` without argparse exiting 2; (2) the finalize branch passes the
  `status.md` values to `finalize_from_output`, NOT the CLI args. Setup: set the `test-batch` batch's
  `start_sha` and `implementer_session` in the fixture status.md to distinct sentinel values via
  `millpy_implement._status.set_batch_field(status_path, "test-batch", "start_sha", "STATUS_SHA")`
  and the same for `"implementer_session"` -> `"STATUS_SESSION"` (mirror the `set_batch_field` usage
  in `test_2_initial_dispatch_running_batch` at line 202). Write an agent-output file containing a
  valid status JSON (mirror `test_14_stage_finalize_reads_agent_output` at lines 350-354). Patch
  `millpy_implement.finalize_from_output` with a `unittest.mock.patch.object` whose mock returns `0`
  and captures the call; the patch target is `millpy_implement.finalize_from_output` because the name
  is bound into the implement module via `from _implementer_common import ... finalize_from_output`
  (`millpy-implement.py:36`). Invoke via `self._run_main([...])` with argv
  `["test-batch", "--stage", "finalize", "--agent-output", str(agent_output_path),
  "--session-id", "CLI_SESSION", "--start-sha", "CLI_SHA"]`. Assert: `rc == 0`; the mock was called
  once; the captured keyword args satisfy `start_sha == "STATUS_SHA"` and `session_id ==
  "STATUS_SESSION"` (i.e. the `status.md` values, NOT `"CLI_SHA"`/`"CLI_SESSION"`). Read the captured
  kwargs from the mock's `call_args` (the finalize branch calls `finalize_from_output(Path(...),
  project_root, start_sha=..., snapshot_path=..., session_id=...)`, so the asserted values are in
  `call_args.kwargs`). Follow the `call_args[1].get("start_sha")` / `call_args[1].get("session_id")`
  passthrough-assertion style from `test-fix-finalize.py:167-172`.
- **Commit:** `test(implement): finalize accepts --session-id/--start-sha, still uses status.md`

### Card 2: Add --session-id and --start-sha as accepted-but-ignored argparse flags

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement.py`'s `main()` argparse block (after the `--agent-output`
  argument at lines 81-84, before `args = parser.parse_args(argv)` at line 85), add two
  `parser.add_argument` calls mirroring `millpy-fix.py:95-104`: `--start-sha` with `default=None`,
  and `--session-id` with `default=None`. Use plain-ASCII `help=` text. Precede the two new arguments
  with a short comment (ASCII only) stating they are accepted for CLI-shape parity with
  `millpy-fix.py` and the generic agent-mode dispatch loop (mill-go SKILL.md step 5), that
  `millpy-implement.py` ignores them, and that the `--stage finalize` branch reads the authoritative
  `start_sha`/`implementer_session` from `status.md` instead. Do NOT modify the `--stage finalize`
  branch (lines 164-184) — it must keep reading `batch_status.get("start_sha")` and
  `batch_status.get("implementer_session")` from `status.md`. Do NOT reference `args.session_id` or
  `args.start_sha` anywhere in the file.
- **Commit:** `fix(implement): accept --session-id/--start-sha flags for agent-dispatch parity`

## Batch Tests

`verify:` runs only `test-millpy-implement.py` — the single test file whose module under test
(`millpy-implement.py`) is the one edited by Card 3, and the file Card 2 adds the new test to. Scope
is correct: the change is confined to the implement CLI's argparse and is fully exercised by the new
`test_15_...` method plus the existing finalize/argparse regression tests in the same file
(`test_13_*` prepare, `test_14_*` finalize). No cross-cutting helper is touched, so the per-batch
single-file scope (not `run-all.py`) is the right choice.
