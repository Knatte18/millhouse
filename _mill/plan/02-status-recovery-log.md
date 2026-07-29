# Batch: status-recovery-log

```yaml
task: "mill-start: tracked _mill/ files disappear from the working tree mid-review-loop; existing safeguard covers only status.md"
batch: status-recovery-log
number: 2
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py"
depends-on: []
```

## Batch Scope

Add `_status.append_recovery_log`, the audit-append helper the wiring batches (03/04/05) call whenever `_treeguard.check_and_restore` reports `triggered=True`. This batch does not touch `_treeguard.py` and has no dependency on batch 1 — it only adds a new, independent section-owner function to `_status.py`, following the existing `## Batches` lazy-creation precedent (`_find_batches_block` / `_write_batches`) but append-only like `## Timeline` instead of replace-whole-section like `## Batches`.

## Cards

### Card 3: Add `append_recovery_log` (and its `_find_recovery_log_block` helper) to `_status.py`

- **Context:**
  - `plugins/mill/templates/status-discussing.md`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new heading constant `_RECOVERY_LOG_HEADING = "## Tracked-file recovery log"` near the existing `_BATCHES_HEADING = "## Batches"` constant (`_status.py:530`).
  - Add `_find_recovery_log_block(lines: list[str]) -> tuple[int, int, int, int] | None`, structurally mirroring `_find_batches_block` (`_status.py:550-596`) but scanning for `_RECOVERY_LOG_HEADING` and the `_TIMELINE_FENCE` (`` ```text ``, already defined at `_status.py:50`) instead of `_BATCHES_HEADING` and a yaml fence. Same return contract: `(heading_idx, fence_open_idx, fence_close_idx, section_end_idx)` or `None` when the heading is absent. Raise `ValueError` (matching `_find_batches_block`'s two raise sites) if the heading is present but the fence is missing or unterminated.
  - Add `append_recovery_log(status_path: Path, timestamp: str, restored_paths: list[str]) -> None`:
    1. Call `_require_path(status_path, "append_recovery_log")` (matching every other public `_status.py` function's guard).
    2. Read `status_path`, split into `lines = text.splitlines()` (no `keepends`, matching `_write_batches`'s style at `_status.py:646`, since this function rewrites via `"\n".join(...)` like `_write_batches` does, not the `keepends=True` line-splice style `append_phase` uses).
    3. Build `new_row = f"{quote_scalar(timestamp)}  {', '.join(restored_paths)}"` — two-space column separator, matching `append_phase`'s `f"{phase}  {quote_scalar(timestamp)}\n"` row convention (`_status.py:521`) but with the timestamp first (mirrors the discussion's framing: "a timestamp plus the list of restored paths").
    4. Call `_find_recovery_log_block(lines)`. If `None`: append a new section at EOF exactly like `_write_batches`'s absent-section branch (`_status.py:657-660`) — add one blank-line separator if the last line is non-blank, then extend with `[_RECOVERY_LOG_HEADING, "", "```text", new_row, "```"]`.
    5. If found: insert `new_row` immediately before `fence_close_idx` (i.e. `lines.insert(fence_close_idx, new_row)`) — an append into the existing fenced block, never a whole-section replace (this is the one behavioral difference from `_write_batches`, called out explicitly in the docstring below).
    6. Write back with `status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")` (matching `_write_batches`'s exact write-back line).
  - Docstring for `append_recovery_log` must state explicitly: (a) the section is created lazily on first call, mirroring `_write_batches`'s lazy-insert-if-absent pattern for `## Batches`, but is append-only on every subsequent call rather than replace-whole-section, matching `## Timeline`'s append-only convention instead; (b) this function is the caller's explicit, separate audit-append step — `_treeguard.check_and_restore` itself never calls this function or touches `status.md`.
  - Do not add a `## Tracked-file recovery log` section to `plugins/mill/templates/status-discussing.md` or any other spawn-time status template — the lazy-creation design is the whole point (per `_mill/discussion.md`'s "Recovery-log section: lazy creation via a new `_status.py` helper" Decision). The `Context:` entry for that template above is read-only, to confirm no template edit is needed, not a instruction to edit it.
- **Commit:** `feat(mill): add _status.append_recovery_log for tracked-file recovery audit trail`

### Card 4: Add unit tests for `append_recovery_log` to `test-status.py`

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `append_recovery_log` to the `from _status import (...)` block (`test-status.py:16-35`), keeping the existing alphabetical ordering convention.
  - Add new `# Test N: ...` blocks to the end of `main()`'s existing `try` body (immediately before the `print("All _status unit tests passed.")` line at the end of the file), following the exact style of the file's existing numbered-test blocks (each in its own `with tempfile.TemporaryDirectory() as tmp:`, building a fresh `status.md` via `render_initial(...)`, followed by one or more `assert` calls and a `print("PASS: ...")` line):
    1. **Lazy section creation on first call:** render an initial `status.md` with no `## Tracked-file recovery log` section (the existing `render_initial(...)` output has none, confirmed by `status-discussing.md` never declaring one). Call `append_recovery_log(sp, "2026-07-29T08:00:00Z", ["_mill/status.md"])`. Assert the file now contains a `## Tracked-file recovery log` heading, a fenced `` ```text `` block, and that block's body contains a row combining the given timestamp and path.
    2. **Append-only on second call:** immediately after test 1's call (same file), call `append_recovery_log(sp, "2026-07-29T08:05:00Z", ["_mill/reviews/y.md"])` again. Assert the file now has **two** rows in the `## Tracked-file recovery log` fenced block — the first call's row is still present unchanged, and the new row is appended after it (not replacing the section, matching `## Timeline`'s append-only behavior rather than `## Batches`'s replace-whole-section behavior).
    3. **Multiple restored paths in one call:** call `append_recovery_log` with `restored_paths=["_mill/status.md", "_mill/briefs/x.md"]` on a fresh `status.md`. Assert the resulting row contains both paths (comma-joined, per the row format built in Card 3).
    4. **Does not disturb `## Timeline` or the yaml block:** on a `status.md` that already has a `discussing` timeline row (the default `render_initial` output), call `append_recovery_log`, then call `read(sp)` (or re-parse the yaml block directly) and assert `phase:` is unchanged, and assert the existing `## Timeline` fenced block's rows are unchanged — proving the new section is additive at EOF and does not corrupt the yaml block or `## Timeline`'s own fence-discovery logic (`_split_fences` scoped to `_TIMELINE_FENCE` finding the *first* `` ```text `` fence, not the new recovery-log section's fence, since the recovery-log section is appended after `## Timeline` — confirm this ordering assumption holds, since `_split_fences`'s existing behavior for `## Timeline` scans for the *first* matching fence pair, per its pre-existing implementation).
    5. **Malformed section raises `ValueError`:** on a fresh `status.md`, manually append a bare `## Tracked-file recovery log` heading with no fenced block after it (write the heading line directly, no `` ```text `` fence at all). Call `append_recovery_log` and assert it raises `ValueError` (mirrors `_find_batches_block`'s missing-fence raise). Separately, seed the heading followed by an opening `` ```text `` fence with no closing fence before EOF, and assert `append_recovery_log` also raises `ValueError` in that case (mirrors `_find_batches_block`'s unterminated-fence raise).
- **Commit:** `test(mill): add append_recovery_log coverage to test-status.py`

## Batch Tests

`verify:` runs the full `test-status.py` file (not a `--only` list) since this batch edits `test-status.py` itself directly rather than a separate new test file — the whole file must still pass, including the pre-existing tests for `append_phase`, `set_blocked`, and the `## Batches` helpers, none of which this batch's additive changes should affect.
