# Batch: Fix production code

```yaml
task: Smoke-test the psmux implementer end-to-end
batch: Fix production code
number: 1
cards: 3
verify: PYTHONPATH= "$MILL_PYTHON" plugins/mill/unit_tests/run-all.py --only test-claude-sub.py test-psmux-capture.py
depends-on: []
```

## Batch Scope

Fix the two confirmed bugs in the psmux production layer, then commit the pre-existing doc update. Card 1 fixes the idle-detection substring in `millpy-claude-sub.py` (both `_wait_for_idle_prompt` and `_wait_for_idle_stable`). Card 2 fixes the bullet-prefix detection in `_psmux_capture.py`. Card 3 commits `doc/psmux-tui-behavior.md`, which was already updated during mill-plan exploration and is sitting as an uncommitted change in the working tree.

After this batch, all existing unit tests must still pass — the fixes are backwards-compatible (ASCII-space captures that contain `"shortcuts"` as a substring still match; bullet stripping with `[1:].lstrip()` behaves identically to `[2:]` when the character after `●` is an ASCII space).

## Cards

### Card 1: Fix idle detection in millpy-claude-sub.py

- **Context:**
  - `doc/psmux-tui-behavior.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-claude-sub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `_wait_for_idle_prompt`: change `if "for shortcuts" in capture:` to `if "shortcuts" in capture:`. This is the only occurrence of `"for shortcuts"` in that function.
  - In `_wait_for_idle_stable` Phase 2: change `curr_idle = "for shortcuts" in capture` to `curr_idle = "shortcuts" in capture`. This is the only occurrence in that function.
  - No other changes to the file. Do not modify `_wait_for_idle_stable` Phase 1 (it already handles both `"esc to interrupt"` and `"esctointerrupt"`).
- **Commit:** `fix(millpy-claude-sub): use "shortcuts" as idle marker -- non-ASCII spaces in psmux alt-screen`

### Card 2: Fix bullet-prefix detection in _psmux_capture.py

- **Context:**
  - `doc/psmux-tui-behavior.md`
- **Edits:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `extract_response`, change `bullet_prefix = "● "` to `bullet_prefix = "●"` (remove the trailing space).
  - Change the line `first_line = response_lines[0].strip()[2:]  # [2:] removes "● "` to `first_line = response_lines[0].strip()[1:].lstrip()`. The `[1:]` removes the bullet character `●`, and `.lstrip()` removes any following whitespace (ASCII or non-ASCII), leaving only the response text.
  - The `startswith(bullet_prefix)` check in the search loop does not need changing — it now matches `"●"` alone which is correct.
  - No other changes to the file.
- **Commit:** `fix(_psmux_capture): match bullet on "●" alone, strip trailing whitespace`

### Card 3: Commit psmux-tui-behavior.md doc update

- **Context:** none
- **Edits:**
  - `doc/psmux-tui-behavior.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - The file was already updated during mill-plan exploration and contains the correct new content. Verify the file is modified (contains the "non-ASCII spaces" section and updated bug table), then stage and commit it. Do not add or change any content.
- **Commit:** `docs(psmux-tui-behavior): add non-ASCII-space findings from smoke-test-psmux`

## Batch Tests

`verify:` runs `run-all.py --only test-claude-sub.py test-psmux-capture.py`. Both test files set their own `sys.path` via `HUB = Path(__file__).resolve().parent.parent.parent.parent` and `sys.path.insert(0, ...)`, so `PYTHONPATH=` (empty) is correct.

`test-claude-sub.py` exercises `_wait_for_idle_prompt` and `_wait_for_idle_stable` via mocked captures — all existing scenarios use ASCII-space captures such as `"? for shortcuts"` which contain `"shortcuts"` as a substring, so they pass unchanged.

`test-psmux-capture.py` exercises `extract_response` with inline snapshots — existing tests use `"● "` (ASCII space) which `[1:].lstrip()` handles identically to the old `[2:]`.
