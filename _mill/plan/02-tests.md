# Batch: Tests

```yaml
task: Replace psmux marker protocol with idle-prompt detection
batch: Tests
number: 2
cards: 3
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/test-psmux-capture.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-sub.py"
depends-on: [1]
```

## Batch Scope

This batch adapts the test suite to the new idle-prompt API delivered by Batch 1. It deletes all nine marker-based fixture files under `unit_tests/fixtures/psmux-capture/`, fully rewrites `test-psmux-capture.py` with inline string fixtures covering the new extraction algorithm, and updates `test-claude-sub.py` with corrected mock signatures for S1/S4/S7/S9, a full rewrite of S6, two new error-path tests (S10, S11), and direct unit tests for `_wait_for_idle_stable`. All changes are committed together once both test files pass.

Batch-local decisions: inline snapshot strings use raw multi-line Python strings; the `❯` and `● ` characters appear in those strings as Unicode literals. `time.sleep` and `time.monotonic` are mocked with `mock.patch` in `_wait_for_idle_stable` unit tests to avoid real delays.

## Cards

### Card 3: Delete fixture files

- **Context:** none
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/unit_tests/fixtures/psmux-capture/clean.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/markers-reversed.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/multiline.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/no-end-marker.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/polling-not-ready.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/quoted-marker-text.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/whitespace-compressed.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/with-scrollback.txt`
  - `plugins/mill/unit_tests/fixtures/psmux-capture/with-status.txt`
- **Requirements:** Delete all nine `.txt` files listed above using `Path.unlink()` or equivalent. The `fixtures/psmux-capture/` directory itself may remain (empty) or be removed — either is acceptable. No other files under `unit_tests/fixtures/` are touched.
- **Commit:** `chore(tests): delete marker-based psmux-capture fixture files`

### Card 4: Rewrite `test-psmux-capture.py`

- **Context:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-psmux-capture.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the entire content of `test-psmux-capture.py` with tests that cover the new `extract_response(snapshot)` API using inline multi-line string fixtures. Keep the same `main() -> int` pattern (return error count, `sys.exit(main())`). Do not load any files from `fixtures/psmux-capture/`. Implement all seven scenarios below as separate numbered test cases:

  1. **Basic response**: snapshot is `"  ❯ \n● First line\nSecond line\n  ❯ "`. Expected return value: `"First line\nSecond line"`.

  2. **Multi-line response**: snapshot contains `● Start line` followed by 9 continuation lines (total 10 lines of response), then `❯`. Verify all 10 lines are present in the returned string and the `● ` prefix is stripped from the first.

  3. **Bullet-prefix strip**: first line of the response in the snapshot is `"●  extra space"` (bullet + 2 spaces). The returned first line must be `" extra space"` (strip exactly 2 chars: `"● "`). Verify `extract_response` returns the expected string without over-stripping.

  4. **Session history**: snapshot contains two complete prior response blocks (each: `❯` line, `● PriorN` line, continuation, `❯` line), then the current response (`● Current response\n❯`). Verify only `"Current response"` is returned (the algorithm finds the *last* `❯` and works backwards).

  5. **No bullet prefix**: snapshot has `❯` line but no `● ` line anywhere. Verify `MarkerNotFoundError` is raised.

  6. **No idle char**: snapshot has `● Response text` but no `❯` line. Verify `MarkerNotFoundError` is raised.

  7. **Whitespace variants**: snapshot has lines with leading spaces before `❯` and `● ` — e.g. `"  ❯ done"` and `"  ● First line"`. Verify `extract_response` returns `"First line"` (`.strip()` matching works regardless of leading spaces).

- **Commit:** `test(psmux-capture): rewrite tests for idle-prompt extraction API`

### Card 5: Update `test-claude-sub.py`

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
  - `plugins/mill/scripts/_psmux_capture.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the following changes to `test-claude-sub.py`. Preserve the `_load_claude_sub_module()` helper and all existing structure. Commit message covers all changes in one commit.

  **1. Update mock signatures in S1, S4, S7, and both sub-tests of S9:**
  - Change `def mock_extract_response(capture, begin, end)` to `def mock_extract_response(snapshot)` (1-arg lambda/function) in each of those tests.
  - Add `mock.patch.object(mod, "_wait_for_idle_stable", return_value=True)` to the `with mock.patch(...)` block in each. This mocks the new Step 11 polling function so the tests do not block.
  - Keep `mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True)` where it already appears (Step 7 CLAUDE_READY). Do not remove it.

  **2. Rewrite S6 (regression guard, no flags):**
  - Replace `def mock_capture_pane(session_name, **kwargs): return "MILL_BEGIN_abc123\nresponse text\nMILL_END_def456"` with a version that returns a valid snapshot: `"  ❯ \n● Hello\n  ❯ "`.
  - Change `def mock_extract_response(capture, begin, end)` to `def mock_extract_response(snapshot)`.
  - Add `mock.patch.object(mod, "_wait_for_idle_stable", return_value=True)` to the `with mock.patch(...)` block.
  - Keep `mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True)` (for Step 7).
  - Keep `mock.patch.object(mod, "_wait_for_idle_prompt", return_value=True)` (for Step 9 boot-wait).
  - Assertions remain: `m_kill.call_count > 0` and `ret == 0`.

  **3. Add S10 (`_wait_for_idle_stable` timeout):**
  - New test after S9. Name it S10.
  - Setup: auto-generated session (no `--psmux-session`); mock `_psmux.new_session`, `_psmux.set_history_limit`, `_psmux.send_keys`, `_psmux.load_buffer`, `_psmux.paste_buffer`, `_psmux.capture_pane` returning `""`, `_psmux.kill_session` as `m_kill`; `mock.patch.object(mod, "_wait_for_marker_in_pane", return_value=True)`; `mock.patch.object(mod, "_wait_for_idle_prompt", return_value=True)`; `mock.patch.object(mod, "_wait_for_idle_stable", return_value=False)`. Capture stderr.
  - Assert `ret == 1`, `m_kill.call_count > 0` (session owned, error cleanup), and that `"response-poll timeout"` appears in stderr.

  **4. Add S11 (`extract_response` raises `MarkerNotFoundError`):**
  - New test after S10. Name it S11.
  - Setup identical to S10 except `_wait_for_idle_stable` returns True, add `mock.patch("_psmux.load_buffer")` and `mock.patch("_psmux.paste_buffer")` (same as S10), and `_psmux_capture.extract_response` raises `_psmux_capture_mod.MarkerNotFoundError("no bullet found")` (import `_psmux_capture` module at top of test as `_psmux_capture_mod` if not already imported, or use `mock.patch("_psmux_capture.extract_response", side_effect=...)`). Capture stderr.
  - Assert `ret == 1` and that `"MarkerNotFoundError"` appears in stderr.

  **5. Add direct unit tests for `_wait_for_idle_stable`:**
  - Load the module once, extract `_wait_for_idle_stable = mod._wait_for_idle_stable` (or equivalent).
  - For each scenario, mock `_psmux.capture_pane` with a `side_effect` list of return values, mock `time.sleep` (no-op), and mock `time.monotonic` with a `side_effect` list that returns monotonically increasing values. Call `_wait_for_idle_stable(session_name="s", timeout_s=5.0)` directly.

  Scenario (a): capture returns `["❯ idle\n", "❯ idle\n", ...]` for the first two polls; `time.monotonic` side_effect starts at `[0.0, 0.0, 1.0, 1.0, ...]`. Assert returns `True`.

  Scenario (b): captures return `["❯ idle\n", "no idle\n", "❯ idle\n", "❯ idle\n"]` for polls 1-4; `time.monotonic` starts at `[0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0]`. Assert returns `True`.

  Scenario (c): all captures return `"no idle"` (no `❯` line); `time.monotonic` side_effect returns `[0.0, 0.0, 6.0, 6.0]` so the timeout check fires. Assert returns `False`.

  Note: `time.monotonic` is called once before the loop (for `start`) and once per loop iteration (for the timeout check). Provide enough values in the side_effect list. Mock `time.sleep` to avoid actual delays.

- **Commit:** `test(claude-sub): update mocks for idle-prompt flow; add S10/S11/wait-stable tests`

## Batch Tests

The verify command runs `test-psmux-capture.py` and `test-claude-sub.py` in sequence. Both must exit 0 (zero errors) for the batch to pass. If either exits non-zero, the implementer must diagnose from the printed `[FAIL]` lines and fix before re-running verify.
