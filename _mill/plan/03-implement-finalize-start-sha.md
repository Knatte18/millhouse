# Batch: implement-finalize-start-sha

```yaml
task: "millpy-implement.py / _done_gate.py: Windows baseline teardown, truncated failure reason, ignored --start-sha"
batch: implement-finalize-start-sha
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py
depends-on: []
```

## Batch Scope

Fixes GitHub #1012: `millpy-implement.py --stage finalize` accepts a `--start-sha` flag but always ignores it, reading `start_sha` from `status.md` instead — documented in-source as intentional ("ignored by implement; status.md is authoritative"). `mill-go-base/SKILL.md`'s Agent-mode dispatch pattern documents threading `--start-sha` into "every finalize call for fix and implementer CLIs", and `millpy-fix.py`'s own finalize branch already honors it unconditionally (`start_sha=args.start_sha`, no fallback). An operator who manually corrected a batch's `start_sha` (after a fresh non-`--resume-incomplete` `--stage prepare` re-captured HEAD as a wrong new value for an already-partially-committed batch) and passed the correction via `--start-sha` at `--stage finalize` found it had no effect, producing a false `stuck_type: logic, reason: "success reported but no content commit"`. This batch makes `--stage finalize` honor an explicitly-passed, non-empty `--start-sha`, falling back to `status.md`'s stored value when the flag is absent — the CLI flag is already threaded into every normal finalize call today (with a value identical to what's already in `status.md`, so this is a no-op on the ordinary path) and only diverges from `status.md` in the exact manual-correction scenario #1012 reports. `--session-id` and `--round` remain fully ignored at `--stage finalize` — out of scope, per `_mill/discussion.md`'s Scope/Out.

## Cards

### Card 5: Honor an explicit --start-sha at --stage finalize, falling back to status.md

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In the `--stage finalize` branch of `main()`, replace `start_sha = batch_status.get("start_sha")` with `start_sha = args.start_sha if args.start_sha else batch_status.get("start_sha")` — the CLI flag wins whenever it is a non-empty, non-`None` string; falls back to the existing `status.md`-read value (`batch_status.get("start_sha")`) otherwise, exactly as before.
  2. Update the `--start-sha` argparse `help=` text (currently `help="SHA captured at prepare stage (ignored by implement; status.md is authoritative)."`, on the `--start-sha` `parser.add_argument` call) to `help="SHA captured at prepare stage; honored at --stage finalize when passed (non-empty), falling back to status.md otherwise."`.
  3. The current three-line comment block immediately above the `--start-sha` `parser.add_argument` call reads: `# These flags are accepted for CLI-shape parity with millpy-fix.py and the generic agent-mode dispatch loop (mill-go SKILL.md step 5).` / `# millpy-implement.py ignores them;` / `# the --stage finalize branch reads the authoritative start_sha and implementer_session from status.md instead.` — this same three-line comment sits directly above BOTH the `--start-sha` argparse block AND the immediately-following `--session-id` argparse block, describing both flags together. Split it: place a new, `--start-sha`-specific one-line comment directly above the `--start-sha` `parser.add_argument` call stating `--start-sha` is now honored at `--stage finalize` when passed, with `status.md` as the fallback. Leave the original three-line comment block in place, unmodified verbatim, directly above the `--session-id` `parser.add_argument` call instead — `--session-id` remains fully ignored, so that comment's "ignores them"/"reads ... from status.md instead" wording stays accurate for `--session-id` on its own.
  4. Do not change `--round`'s argparse definition, help text, or its own separate comment (the block reading "Accepted for CLI-shape parity with millpy-fix.py and the agent-mode dispatch loop; ignored by implement (the finalize branch reads start_sha and implementer_session from status.md).") — unrelated to this fix, `--round` remains ignored.
  5. Do not change `session_id = batch_status.get("implementer_session")` in the `--stage finalize` branch, or any other line in that branch besides the `start_sha` resolution named in requirement 1 — `--session-id` remains status.md-only, and every other finalize-branch behavior (verify command resolution, `finalize_from_output` call, its other keyword arguments) is unchanged.
- **Commit:** `fix(implement): honor explicit --start-sha at --stage finalize, falling back to status.md (#1012)`

### Card 6: Update finalize start_sha honored/fallback test coverage

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In `test_15_stage_finalize_accepts_session_and_start_sha_flags`: change the assertion `self.assertEqual(call_kwargs.get("start_sha"), "STATUS_SHA")` to `self.assertEqual(call_kwargs.get("start_sha"), "CLI_SHA")` — the test already sets `status.md`'s `start_sha` to `"STATUS_SHA"` and passes `--start-sha CLI_SHA` on the CLI; the CLI value must now win. Leave `self.assertEqual(call_kwargs.get("session_id"), "STATUS_SESSION")` unchanged immediately below it — `--session-id` remains ignored. Update the test's docstring (currently `"""--stage finalize accepts --session-id and --start-sha flags, still uses status.md values."""`) to state that `--start-sha` is now honored while `--session-id` still falls back to `status.md`. Update the inline comment directly above the two assertions (currently `# Verify the kwargs passed to finalize_from_output contain status.md values, NOT CLI args`) to match.
  2. In `test_16_stage_finalize_accepts_round_flag`: change the assertion `self.assertEqual(call_kwargs.get("start_sha"), "STATUS_SHA")` to `self.assertEqual(call_kwargs.get("start_sha"), "CLI_SHA")` (this test also sets `status.md`'s `start_sha` to `"STATUS_SHA"` and passes `--start-sha CLI_SHA`). Leave `self.assertEqual(call_kwargs.get("session_id"), "STATUS_SESSION")` unchanged immediately below it. Update the test's docstring (currently states it "Mirrors test_15... for #568: the --round flag is accepted for CLI-shape parity with millpy-fix.py but is ignored; the finalize branch reads start_sha and implementer_session from status.md.") and the inline comment directly above the assertions (currently `# Finalize must use status.md values, not the CLI --round/--session-id/--start-sha args.`) so both state that only `--round` and `--session-id` remain ignored — `--start-sha` is now honored.
  3. Add a new test method `test_finalize_start_sha_falls_back_to_status_md_when_flag_absent` (placed immediately after `test_16_stage_finalize_accepts_round_flag`): mirrors `test_15`'s setup exactly (write `"STATUS_SHA"` to `status.md` for batch `"test-batch"` via `millpy_implement._status.set_batch_field(status_path, "test-batch", "start_sha", "STATUS_SHA")`, write an `agent_output_path` with a `{"status":"success","commit_sha":"xyz","session_id":"fake"}` JSON line, patch `millpy_implement.finalize_from_output` with `return_value=0`), but invoke `--stage finalize` WITHOUT any `--start-sha` flag at all (only `"test-batch"`, `"--stage", "finalize"`, `"--agent-output", str(agent_output_path)`). Assert `rc == 0`, `mock_finalize.assert_called_once()`, and `call_kwargs.get("start_sha") == "STATUS_SHA"` — confirms the fallback path (the ordinary auto-dispatch case, and the warm-`SendMessage` recovery path documented in `mill-go-base/SKILL.md` step 5.5, which bypasses `--stage prepare` entirely and therefore never supplies `--start-sha` to the following `--stage finalize` call) is unaffected by Card 5's fix.
- **Commit:** `test(implement): update finalize start_sha honored/fallback coverage (#1012)`

## Batch Tests

`verify:` runs `test-millpy-implement.py` in full (already scoped to exactly the module this batch edits — a `unittest.TestCase`-based file invoked directly, `python test-millpy-implement.py`, running every test including this batch's new/updated ones).
