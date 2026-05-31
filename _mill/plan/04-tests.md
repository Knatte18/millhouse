# Batch: Tests

```yaml
task: Replace claude -p with psmux-routed LLM dispatch
batch: Tests
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-psmux-capture.py test-claude-sub.py test-llm-claude.py
depends-on: [1, 2, 3]
```

## Batch Scope

Update unit tests to cover the fixed behaviour from Batches 1-3, and add a
keep-alive reuse test to the integration suite. After this batch, the full
unit test suite for the affected files must pass green. The integration test
(`test-claude-psmux.py`) is updated but excluded from `verify:` since it
requires real psmux and claude at runtime.

## Cards

### Card 8: Update test-psmux-capture.py for new extract_response boundary

- **Context:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-psmux-capture.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add three new test cases to `main()`:
  1. **Completion marker stripped**: snapshot has `● PONG\n\n✻ Cogitated for
     5s\n\n────────────\n❯\n────────────\n? for shortcuts`. Assert
     `extract_response(snapshot) == "PONG"`.
  2. **Auto-suggest not included**: snapshot has
     `● Hello world\n\n✻ Cooked for 2s\n\n────────────\n❯ show an example\n────────────\n? for shortcuts`.
     Assert `extract_response(snapshot) == "Hello world"`.
  3. **Multi-line response stripped cleanly**: snapshot has
     `● Line one\nLine two\n\n✻ Brewed for 3s\n\n────────────\n❯\n────────────`.
     Assert result equals `"Line one\nLine two"` (no trailing blank lines, no
     `✻` line). Use `.strip()` on expected if needed to match
     `result.strip()`.
  All existing tests (MarkerNotFoundError cases, basic bullet extraction) must
  continue to pass — do not modify them.
- **Commit:** `test(_psmux_capture): cover ✻ stripping and separator boundary`

### Card 9: Update test-claude-sub.py for new idle detection, Escape, shell_path, rows

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_psmux.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  The S1-S11 tests mock `_wait_for_idle_prompt` and `_wait_for_idle_stable` at
  the module level — their `side_effect` / `return_value` shapes don't change.
  These tests need no structural changes EXCEPT: S1 asserts
  `m_send_keys.call_count == 3` for the reuse path (before the Escape fix). After
  Card 5, the reuse path sends one extra `send_keys("Escape", enter=False)` call
  before the Step 10 bracketed paste sequence. Update S1's assertion to
  `m_send_keys.call_count == 4` and verify the first call is `Escape`.

  Fix the three direct `_wait_for_idle_stable` unit tests (Scenarios a/b/c at
  the bottom of the file). They currently mock `_psmux.capture_pane` to return
  `"❯ idle\n"`. After Card 4's rewrite, the function checks for
  `"for shortcuts"` and `"esc to interrupt"`, not `"❯"`. Rewrite the scenarios:
  - Scenario (a): first two captures return `"? for shortcuts"`. Assert returns
    `True`.
  - Scenario (b): first two captures return `"esc to interrupt"`, next two
    return `"? for shortcuts"` twice → True after phase 2 stabilises.
  - Scenario (c): all captures return `"esc to interrupt"` or empty (never
    `"for shortcuts"`), timeout fires → returns `False`.
  (The `time.monotonic` side_effect lists in Scenarios a/b/c must account for
  Phase 1 polls as well — adjust as needed so the loops terminate correctly.)

  Add new test **S12: `_resolve_shell_path` reads config value**: mock
  `_config.load_config` to return
  `{"llm": {"claude": {"psmux": {"shell_path": "C:/my/pwsh.exe"}}}}`. Call
  `mod._resolve_shell_path()`. Assert returns `"C:/my/pwsh.exe"`.

  Add new test **S13: `_resolve_shell_path` defaults to `pwsh`**: mock
  `_config.load_config` to return `{}`. Assert returns `"pwsh"`.

  Add new test **S14: `new_session` called with `rows=100`**: run through the
  new-session path (auto-generated session name, success). Assert the
  `rows` kwarg passed to `_psmux.new_session` equals 100.
- **Commit:** `test(claude-sub): cover idle detection rewrite, Escape on reuse, shell_path, rows=100`

### Card 10: Add cwd psmux test to test-llm-claude.py

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add one test after the existing K-series tests: **K6: `cwd` is passed through
  on psmux path**. Patch `_get_via_psmux_flag` to return `True`, patch
  `shutil.which` to return `"/usr/bin/psmux"`, patch `_subprocess_util.run` to
  capture kwargs and return a success result. Call
  `run_implementer("prompt", model="m", session_id="abc", cwd="/some/path")`.
  Assert the `cwd` kwarg passed to `_subprocess_util.run` equals `"/some/path"`.
  All existing K1-K5 and Tests 2-11 must remain green.
- **Commit:** `test(_llm_claude): K6 verify cwd passed through on psmux path`

### Card 11: Add keep-alive reuse test to test-claude-psmux.py

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_psmux_capture.py`
  - `plugins/mill/scripts/_psmux.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-claude-psmux.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add `test_keep_alive_reuse() -> int` following the pattern of the existing
  tests. Prerequisites: same `_check_prerequisites()` check. The test:
  1. First call: run `millpy-claude-sub.py` with `--mode bulk --model
     claude-sonnet-4-6 --psmux-session mill-test-reuse --keep-alive`, prompt
     `"Reply with the single word FIRST and nothing else."`. Assert returncode 0
     and `"FIRST"` in stdout.
  2. Second call: run `millpy-claude-sub.py` with `--mode bulk --model
     claude-sonnet-4-6 --psmux-session mill-test-reuse` (no `--keep-alive`),
     prompt `"Reply with the single word SECOND and nothing else."`. Assert
     returncode 0 and `"SECOND"` in stdout. Assert `"FIRST"` NOT in stdout
     (auto-suggest from the first response must not contaminate the second).
  3. `_assert_cleanup()` at the end.
  Add `("test_keep_alive_reuse", test_keep_alive_reuse)` to the `tests` list in
  `main()`.
- **Commit:** `test(integration/claude-psmux): add keep-alive reuse test`

## Batch Tests

`verify:` runs `test-psmux-capture.py`, `test-claude-sub.py`, and
`test-llm-claude.py`. The integration test (`test-claude-psmux.py`) requires
live psmux + claude and is excluded from the automated verify. Run it manually
after deploying to confirm end-to-end behaviour.

The three unit test files were selected because this batch edits exactly them.
`run-all.py --only` with these three names is narrow; it does not run the full
77-file suite. This is the correct scope for this batch.
