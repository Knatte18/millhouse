# Batch: status-blocked-reason-cleanup

```yaml
task: (A) — Small infra fixes batch 7
batch: status-blocked-reason-cleanup
number: 3
cards: 2
verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-status.py" && PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Delivers GitHub issue #276 — `_status.append_phase` clears any existing `blocked_reason:` YAML row when the new phase is anything other than `blocked`. The cleanup mirrors `set_blocked`'s in-place YAML-row mutation logic (lines 244–258 in `_status.py`) in inverse: same row-discovery scan, but the result is a line deletion instead of a rewrite. `set_blocked` is unchanged; the new behaviour fires only on transitions OUT of `blocked`.

Batch-local decision: the deletion happens as part of the same single read+write cycle that `append_phase` already performs. No new helper function; the new logic is a 4-line block added inside the existing `append_phase` body, after the `phase:` row is rewritten and before the timeline append. This keeps the "reads, rewrites, and writes the file once" guarantee from the existing docstring (line 281) intact.

## Cards

### Card 7: `_status.append_phase` auto-clears stale `blocked_reason:`

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Modify `_status.append_phase(status_path, phase, timestamp)` in `plugins/mill/scripts/_status.py` (currently lines 271–331) so that, when `phase != "blocked"`, the helper removes any existing `blocked_reason:` row from the top YAML block as part of the same write.

  Required code shape — insert the new block AFTER the existing `phase:` row rewrite (which ends at the `break` inside the `for i in range(y_start, y_end)` loop near line 314) and BEFORE the "Timeline block: insert a new row" comment near line 318:

  ```python
  # Auto-clear blocked_reason: when transitioning to a non-blocked phase.
  # blocked_reason: only has meaning while phase: blocked; leaving the row
  # behind after advancing past blocked produces stale, misleading status.md.
  # Mirrors set_blocked's in-place row discovery (lines 244-258) in inverse:
  # same scan, but delete the line instead of rewriting it.
  if phase != "blocked":
      for i in range(y_start, y_end):
          stripped = lines[i].rstrip("\r\n")
          if re.match(r"^blocked_reason:\s*", stripped):
              del lines[i]
              # y_end is no longer valid after deletion, but we exit the
              # loop immediately — no further indices used inside the yaml
              # range.
              break
  ```

  Behavioural contract after the change:
  - `append_phase(_, "planning", ts)` after `set_blocked(_, "reason", _)` → `blocked_reason:` row removed; `phase:` shows `planning`; timeline gets the new `planning` row.
  - `append_phase(_, "blocked", ts)` on a status.md that already has `blocked_reason: "first reason"` → `blocked_reason:` PRESERVED unchanged; `phase:` shows `blocked`; timeline gets the new `blocked` row.
  - `append_phase(_, "discussed", ts)` on a status.md that has NO `blocked_reason:` row → behaviour identical to current; no row created, no row deleted, no error.
  - `append_phase` still reads and writes the file exactly once (the in-memory `lines` list mutation reuses the same read; the final `status_path.write_text(...)` is the single write).

  Update the function's docstring (the section starting at line 272) to document the new behaviour:
  - Add a fourth sentence to the opening paragraph: "When the new phase is anything other than `blocked`, any existing `blocked_reason:` row in the top yaml block is removed in the same write — `blocked_reason:` only has meaning while `phase: blocked`."
  - In the Raises section, no change (the behaviour does not raise).

  Do not change `set_blocked`. Do not change `update_field`. Do not change `_split_fences`. Do not change the `_BATCH_*` constants or the batches subsystem.
- **Commit:** `fix(status): append_phase clears blocked_reason when leaving blocked`

### Card 8: Unit tests for stale `blocked_reason:` cleanup

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Extend `plugins/mill/unit_tests/test-status.py` with three new test cases inside the existing `main()` function. Insert them inside the `# --- set_blocked tests ---` region (currently after the existing Test 3 at line 207), as new tests 4 / 5 / 6 in the file's existing single top-level `try: ... except AssertionError:` block (the file uses inline `assert` statements + `print("PASS: ...")` on success, NO `passed += 1` / `failed += 1` counters and NO `ok` / `fail` helpers — that pattern belongs to `test-setup-hub-links.py`, not here).

  Tests required (each runs inside its own `with tempfile.TemporaryDirectory() as tmp:` block matching the existing Tests 1–3 style):

  - `Test: append_phase to non-blocked clears blocked_reason`
    1. Render a fresh `status.md` via `render_initial(...)` with `phase: discussing` (the existing seed pattern).
    2. Call `set_blocked(sp, "auto: discussion review gaps unresolved after 2 rounds", timestamp="2026-05-12T01:00:00Z")`.
    3. Call `append_phase(sp, "planning", "2026-05-12T02:00:00Z")`.
    4. Assert: parse via `read_full(sp)`; `data["yaml"]["phase"] == "planning"`; `"blocked_reason" not in data["yaml"]`. Also raw-text assert: `file_text.count("blocked_reason:") == 0`.
    5. Print `PASS: append_phase to non-blocked clears blocked_reason`.

  - `Test: append_phase to blocked preserves blocked_reason`
    1. Render a fresh `status.md`.
    2. Call `set_blocked(sp, "first reason", timestamp="2026-05-12T01:00:00Z")`.
    3. Call `append_phase(sp, "blocked", "2026-05-12T02:00:00Z")`.
    4. Assert: `read_full(sp)`; `data["yaml"]["phase"] == "blocked"`; `data["yaml"]["blocked_reason"] == "first reason"`. Raw-text assert: `file_text.count("blocked_reason:") == 1`.
    5. Print `PASS: append_phase to blocked preserves blocked_reason`.

  - `Test: append_phase on status without blocked_reason is a no-op for that row`
    1. Render a fresh `status.md` (no `blocked_reason:` row ever written).
    2. Call `append_phase(sp, "discussed", "2026-05-12T01:00:00Z")`.
    3. Assert: `read_full(sp)`; `data["yaml"]["phase"] == "discussed"`; `"blocked_reason" not in data["yaml"]`. Raw-text assert: `"blocked_reason:" not in file_text` (no row spuriously introduced).
    4. Print `PASS: append_phase preserves clean status when no blocked_reason present`.

  All three tests sit inside the existing single top-level `try:` block alongside Tests 1–3, use raw `assert ...` statements followed by `print("PASS: <name>")` on success, and rely on `test-status.py`'s outer `except AssertionError` (in `main()`) to surface failures with a non-zero exit. NO `passed += 1` / `failed += 1` counters, NO `ok(name)` / `fail(name, exc)` helpers, NO `traceback.print_exc()` — see lines 148–207 (`# --- set_blocked tests ---` Tests 1, 2, 3) for the exact assertion-then-print idiom to mirror.

  Imports at the top of the file already cover everything needed (`render_initial`, `set_blocked`, `append_phase`, `read_full`, `tempfile`, `pathlib.Path`). No new imports required.
- **Commit:** `test(status): append_phase clears stale blocked_reason on non-blocked transitions`

## Batch Tests

The frontmatter `verify:` runs `unit_tests/test-status.py` first (fast feedback) then `unit_tests/run-all.py` (full suite regression).

Acceptance:
- `test-status.py` exits 0 with the three new PASS lines and every pre-existing PASS line still present.
- `run-all.py` exits 0; no regression in any other test file.
