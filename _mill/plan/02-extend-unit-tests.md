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

Add new test scenarios that exercise the no-ASCII-space capture path introduced by the batch 1 fixes. Card 4 adds three scenarios to `test-claude-sub.py` covering `_wait_for_idle_prompt` and `_wait_for_idle_stable` with captures that contain `"shortcuts"` but not `"for shortcuts"`. Card 5 adds two tests to `test-psmux-capture.py` covering `extract_response` with a non-ASCII space after the bullet and a regression guard with ASCII space.

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
  - **Scenario (f):** `_wait_for_idle_prompt` with a capture that contains `"?forshortcuts"` (no ASCII space) — `mock.patch("_psmux.capture_pane", return_value="?forshortcuts")`. Assert the function returns `True`. Print `[OK] _wait_for_idle_prompt scenario (f)` on success.
  - **Scenario (g):** `_wait_for_idle_stable` Phase 2 with captures that contain `"?forshortcuts"` twice consecutively — `mock.patch("_psmux.capture_pane", side_effect=["?forshortcuts", "?forshortcuts", "?forshortcuts"])` (three items: Phase 1 times out after first, Phase 2 sees it twice). Assert the function returns `True`. Print `[OK] _wait_for_idle_stable scenario (g)` on success.
  - **Scenario (h):** `_wait_for_idle_stable` where Phase 1 capture returns `"esc to interrupt"` and Phase 2 captures return `"shortcuts"` twice — `side_effect=["esc to interrupt", "shortcuts", "shortcuts"]`. Assert the function returns `True`. Print `[OK] _wait_for_idle_stable scenario (h)` on success.
  - All scenarios must mock `time.sleep` and `time.monotonic` (or equivalent) to avoid real sleeps and timeouts, using the same approach as existing scenarios (a)-(e) in the file.
  - All existing scenarios (a)-(e) must still pass — do not modify them.
- **Commit:** `test(test-claude-sub): add scenarios (f)-(h) for no-ASCII-space idle detection`

### Card 5: Add bullet-prefix tests 11-12 to test-psmux-capture.py

- **Context:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-psmux-capture.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add two tests after the existing Test 10 block, inside the `main()` function, using the same pattern as existing tests (inline snapshot string, assert result).
  - **Test 11 — non-ASCII space after bullet:** snapshot is a minimal complete snapshot with `"● First line"` on the bullet line (U+00A0 non-breaking space between `●` and `First`). Use this snapshot structure (modelled on Test 8):
    ```
      ❯
    ● First line

    ✻ Cogitated for 1s

    ────────────────────────────────────────────────────────────────────────────────
    ❯
    ────────────────────────────────────────────────────────────────────────────────
    ? for shortcuts
    ```
    Assert `extract_response(snapshot)` returns `"First line"`. Print `[OK] Test 11: non-ASCII space after bullet` on success.
  - **Test 12 — ASCII space regression guard:** same structure but with `"● First line"` (U+0020 ASCII space). Assert result is `"First line"`. Print `[OK] Test 12: ASCII space after bullet (regression guard)` on success.
  - All existing tests 1-10 must still pass.
- **Commit:** `test(test-psmux-capture): add Tests 11-12 for non-ASCII-space after bullet`

## Batch Tests

`verify:` runs the same two test files as batch 1. After this batch, all 13 existing scenarios plus the 3 new scenarios in `test-claude-sub.py` must pass, and all 10 existing tests plus the 2 new tests in `test-psmux-capture.py` must pass.
