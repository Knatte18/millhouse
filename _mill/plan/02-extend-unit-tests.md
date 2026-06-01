# Batch: Extend unit tests

```yaml
task: Smoke-test the psmux implementer end-to-end
batch: Extend unit tests
number: 2
cards: 2
verify: PYTHONPATH= "$MILL_PYTHON" plugins/mill/unit_tests/run-all.py --only test-claude-sub.py test-psmux-capture.py
depends-on: [1]
```

## Batch Scope

Add new test scenarios that exercise the no-ASCII-space capture path introduced by the batch 1 fixes. Card 4 adds three scenarios to `test-claude-sub.py` covering `_wait_for_idle_prompt` and `_wait_for_idle_stable` with captures that contain `"shortcuts"` but not `"for shortcuts"`. Card 5 adds three tests to `test-psmux-capture.py` covering `extract_response` with U+FFFD (the replacement char produced by invalid-UTF-8 decoding), U+00A0 (non-breaking space), and a regression guard for ASCII space after the bullet.

## Cards

### Card 4: Add idle-detection scenarios (f)-(h) to test-claude-sub.py

- **Context:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add three scenarios after the existing `_wait_for_idle_prompt scenario (e)` block, inside the `main()` function, using the same mock/patch pattern as the existing (a)-(e) scenarios.
  - **Scenario (f):** `_wait_for_idle_prompt` with a capture that contains `"?forshortcuts"` (no ASCII space) -- `mock.patch("_psmux.capture_pane", return_value="?forshortcuts")`. Assert the function returns `True`. Print `[OK] _wait_for_idle_prompt scenario (f)` on success.
  - **Scenario (g):** `_wait_for_idle_stable` Phase 2 with captures that contain `"?forshortcuts"` twice consecutively -- `mock.patch("_psmux.capture_pane", side_effect=["?forshortcuts", "?forshortcuts", "?forshortcuts"])` (three items: Phase 1 times out after first, Phase 2 sees it twice). Assert the function returns `True`. Print `[OK] _wait_for_idle_stable scenario (g)` on success.
  - **Scenario (h):** `_wait_for_idle_stable` where Phase 1 capture returns `"esc to interrupt"` and Phase 2 captures return `"shortcuts"` twice -- `side_effect=["esc to interrupt", "shortcuts", "shortcuts"]`. Assert the function returns `True`. Print `[OK] _wait_for_idle_stable scenario (h)` on success.
  - All scenarios must mock `time.sleep` and `time.monotonic` (or equivalent) to avoid real sleeps and timeouts, using the same approach as existing scenarios (a)-(e) in the file.
  - All existing scenarios must still pass -- do not modify them.
- **Commit:** `test(test-claude-sub): add scenarios (f)-(h) for no-ASCII-space idle detection`

### Card 5: Add bullet-prefix tests 11-13 to test-psmux-capture.py

- **Context:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-psmux-capture.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add three tests after the existing Test 10 block, inside the `main()` function, using the same pattern as existing tests (inline snapshot string, assert result).
  - The snapshot structure for each test mirrors Tests 8-10 (complete snapshot with completion marker and separator lines). Only the character between the bullet and `First line` varies.
  - **Test 11 -- U+FFFD (replacement char) after bullet:** bullet line is `"●�First line"` (U+FFFD between bullet and content -- what `errors="replace"` produces from an invalid-UTF-8 byte). Assert `extract_response(snapshot)` returns `"First line"`. Print `[OK] Test 11: U+FFFD after bullet (replacement char)` on success.
  - **Test 12 -- U+00A0 (non-breaking space) after bullet:** bullet line uses U+00A0 (`" "`) between bullet and content. Assert result is `"First line"`. Print `[OK] Test 12: U+00A0 after bullet (NBSP)` on success.
  - **Test 13 -- ASCII space regression guard:** bullet line uses U+0020 ASCII space (the original `"● First line"` form). Assert result is `"First line"`. Print `[OK] Test 13: ASCII space after bullet (regression guard)` on success.
  - All existing tests 1-10 must still pass.
- **Commit:** `test(test-psmux-capture): add Tests 11-13 for post-bullet separator variants`

## Batch Tests

`verify:` runs the same two test files as batch 1. After this batch, all existing scenarios in `test-claude-sub.py` plus the 3 new scenarios must pass, and all 10 existing tests in `test-psmux-capture.py` plus the 3 new tests (11-13) must pass.
