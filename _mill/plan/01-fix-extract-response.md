# Batch: Fix extract_response

```yaml
task: Replace claude -p with psmux-routed LLM dispatch
batch: Fix extract_response
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-psmux-capture.py
depends-on: []
```

## Batch Scope

Fix `extract_response` in `_psmux_capture.py` so it stops before the TUI's
completion marker (`✻ Verb for Ns`) and separator line (`────────`), returning
only the actual response text. Currently the function uses the last `❯` as its
upper boundary, which includes these chrome lines in the returned text and
corrupts review input.

## Cards

### Card 1: Strip completion marker and separator from extract_response

- **Context:**
  - `doc/psmux-tui-behavior.md`
- **Edits:**
  - `plugins/mill/scripts/_psmux_capture.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  After finding `idle_idx` (last line starting with `❯`), walk backwards from
  `idle_idx - 1` skipping: (a) empty lines, (b) lines whose stripped form
  starts with `✻` (the completion marker character U+273B — handles
  `✻ Cogitated`, `✻Brewed`, `✻ Crunched`, all verb variants without matching
  the verb), (c) separator lines (stripped form is non-empty and every character
  is `─`). The first line that passes all three skip checks is `content_end_idx`.
  If no such line exists, raise `MarkerNotFoundError("no response content found
  before idle char")`. Then search backwards from `content_end_idx` (not from
  `idle_idx`) for the last line whose stripped form starts with `● `
  (`bullet_idx`). Extract `lines[bullet_idx:content_end_idx + 1]`. All other
  logic (bullet prefix strip, `result.strip()`) unchanged. Update the docstring
  to describe the new boundary logic.
- **Commit:** `fix(_psmux_capture): strip ✻ completion marker and separator from extract_response`

## Batch Tests

`test-psmux-capture.py` — existing tests cover the basic `● ` / `❯` boundary
and `MarkerNotFoundError` cases. This batch adds no new test file; Card 1's
changes are verified by the existing suite plus the new cases added in Batch 4
(Card 9). The `verify:` command here confirms the existing tests still pass
after the fix.
