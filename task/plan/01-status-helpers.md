# Batch: status-helpers

```yaml
task: 50 (A) — Bug-fix batch 5 (post-44 triage)
batch: status-helpers
number: 1
cards: 3
verify: python plugins/mill/unit_tests/test-status.py
depends-on: []
```

## Batch Scope

Add the new `_status.set_blocked` helper (#238) and quote timeline-row
timestamps in `_status.append_phase` (#248). Extend `test-status.py` with
coverage for both. After this batch lands, `_status.py` exposes a single
public API for transitioning a task into the blocked state, and every newly
written timeline row carries a quoted timestamp matching `render_initial`'s
output shape.

External interface the next batch (`skill-docs`) consumes: the public callable
`_status.set_blocked(status_path, reason, *, timestamp)`. Signature is fixed in
Card 1 below.

Batch-local decisions:

- `set_blocked` writes all three mutations in a single `write_text` call,
  mirroring `append_phase`'s atomic pattern. No intermediate file state.
- `set_blocked` reuses the existing module-private `_split_fences` helper to
  locate the yaml fence and the timeline fence. Cross-function use of
  `_split_fences` is already established inside `_status.py` (see
  `append_phase`); no module-private-access lint applies.
- The new key insertion point is "immediately after the `phase:` row" in the
  yaml block. When `blocked_reason:` already exists, it is rewritten in place
  with no duplication. This is documented in the docstring.

## Cards

### Card 1: Add `_status.set_blocked` helper

- **Context:**
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new public function `set_blocked(status_path: Path, reason: str, *, timestamp: str) -> None` to `plugins/mill/scripts/_status.py`. The function performs three mutations on `status_path` in a single `write_text` call:
  1. Rewrite the `phase:` row in the top fenced-yaml block to `phase: blocked` (use the same `re.match(r"^(phase:\s*).*$", ...)` pattern `append_phase` uses; the value goes through `_yaml_writer.quote_scalar` — `quote_scalar("blocked")` returns `blocked` unquoted, but the call stays for consistency with `append_phase`).
  2. Locate the `blocked_reason:` row inside the same yaml block via `re.match(r"^(blocked_reason:\s*).*$", ...)`. If found, rewrite it in place with `f"blocked_reason: {_yaml_writer.quote_scalar(reason)}{eol}"`. If not found, INSERT a new row directly after the `phase:` row: `f"blocked_reason: {_yaml_writer.quote_scalar(reason)}\n"` (using `\n`; the caller is responsible for line-ending parity since the file was just rewritten by step 1). The insertion must happen between the phase-rewrite step and the timeline-append step so a single `write_text` writes the final state.
  3. Append a new row to the `## Timeline` text block: `f"{phase_label}  {_yaml_writer.quote_scalar(timestamp)}\n"` where `phase_label = "blocked"`. Use `_split_fences(rewritten_text, _TIMELINE_FENCE)` to find the insertion point — same as `append_phase`. Insert at `t_end` (immediately before the closing fence).
  Add the new function's signature to the module docstring's "Public API" block (lines 18–32). Order: insert the new entry between `update_field` and `append_phase` (alphabetical-by-category ordering keeps the related top-block mutators clustered).
- **Commit:** `feat(_status): add set_blocked helper for blocked_reason flow`

### Card 2: Quote timestamps in `_status.append_phase`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/_status.py`, change the `append_phase` function's timeline-row construction from `new_row = f"{phase}  {timestamp}\n"` to `new_row = f"{phase}  {quote_scalar(timestamp)}\n"`. Update the function's docstring to document the new canonical shape: append a sentence after the existing `Args.timestamp` paragraph stating "The value is written through `_yaml_writer.quote_scalar` so the on-disk row matches `render_initial`'s quoted form." Do NOT back-rewrite existing status.md timeline rows in any worktree — the convergence happens at each future write.
- **Commit:** `fix(_status): quote timestamps in append_phase timeline rows`

### Card 3: Test `set_blocked` and `append_phase` quoting

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_yaml_writer.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `test-status.py` with four new test blocks inserted before the existing `init_batches` test block, each printing one `PASS:` line on success and `assert`-failing on regression:
  1. **`set_blocked` happy path on fresh status:** call `render_initial` to produce a starting file (timestamp `"2026-05-12T00:00:00Z"`, phase `discussing`). Write it to a temp path. Call `set_blocked(path, "auto: discussion review gaps unresolved after 2 rounds", timestamp="2026-05-12T01:00:00Z")`. Assert `read_status(path)["phase"] == "blocked"`, `read_status(path)["blocked_reason"] == "auto: discussion review gaps unresolved after 2 rounds"`, and `read_status(path)["last_timeline_entry"]` matches the regex `r"^blocked\s+'2026-05-12T01:00:00Z'$"`.
  2. **`set_blocked` add-if-missing path:** same fixture as case 1 (top yaml block has no `blocked_reason:` row). After the call, read the file text, locate the yaml block via splitlines, and assert that the row at index `phase_index + 1` starts with `blocked_reason:` — i.e. the new row was inserted directly after `phase:`.
  3. **`set_blocked` rewrite-in-place path:** seed the file with an existing `blocked_reason: foo` row (use `_yaml_writer.quote_scalar` to format) inside the yaml block. Call `set_blocked(path, "new reason", timestamp="...")`. Assert the file text contains `blocked_reason: 'new reason'` exactly once (`text.count("blocked_reason:") == 1`) and does not contain the literal `foo`.
  4. **`append_phase` quoting regression:** call `render_initial` to seed a file, then `append_phase(path, "planning", "2026-05-12T02:00:00Z")`. Read the file, extract the last non-empty line inside the `## Timeline` text fence, and assert it matches the regex `r"^planning\s+'2026-05-12T02:00:00Z'$"`.
  Add `set_blocked` to the existing `from _status import (...)` import block at the top of the file. All fixtures use `tempfile.TemporaryDirectory()` consistent with the existing test style.
- **Commit:** `test(_status): cover set_blocked and append_phase quoting`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-status.py` — runs the existing
22-case suite plus the four new cases added in Card 3. The pre-batch run
provides a regression baseline; the post-batch run must pass all 26+ cases.
