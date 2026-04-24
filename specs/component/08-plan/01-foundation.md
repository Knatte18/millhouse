# Batch 1: foundation

```yaml
batch: 1
name: foundation
cards: 2
depends_on: []
```

## Scope

Add `read_status(status_path) -> dict` to `_status.py` and extend `test-status.py` with unit tests covering it. No CLI work yet.

## Cards

### Card 1: `read_status` helper

**Reads:** `plugins/mill/scripts/_status.py`

**Modifies:** `plugins/mill/scripts/_status.py`

**Requirements:**

- Add `read_status(status_path: Path) -> dict` to the public API and module docstring.
- Returns `{"phase": str, "task": str|None, "current_batch": str|None, "last_timeline_entry": str|None, "blocked_reason": str|None}`.
- This function is only called when an active-dir exists (i.e. a `status.md` file is present). Callers never invoke it for backlog-only tasks that have no active-dir.
- Parse the top `` ```yaml `` block with `yaml.safe_load` to extract `phase`, `task`, `blocked_reason`.
  - Missing `phase:` key → raise `ValueError` with a descriptive message.
  - Missing `task:` key → return `None` for that field (not a `ValueError`).
  - Missing `blocked_reason:` → return `None`.
- `current_batch`: call `read_batches(status_path)` and return the `name` of the first batch whose `state` is in `{"running", "reviewing", "fixing", "blocked"}`. If no such batch, return `None`. If `read_batches` raises `ValueError` (malformed `## Batches` section), let it propagate — do not catch. Note: `"blocked"` here is a **batch-level** state from `_BATCH_STATES` — distinct from the **task-level** `phase: blocked` in the top yaml block. Both can coexist (e.g. `phase=implementing` with a batch in state `blocked`).
- Parse the `` ```text `` Timeline block: last non-empty line is `last_timeline_entry` (strip whitespace). If no timeline block or it's empty, `last_timeline_entry` is `None`.
- Raises `ValueError` with a descriptive message if:
  - The file does not exist — add an explicit `if not status_path.exists(): raise ValueError(...)` guard before calling `read_text()` (naive `read_text()` raises `FileNotFoundError`, not `ValueError`; unit test case 4 asserts `ValueError`).
  - The `` ```yaml `` block is absent or unterminated.
  - `yaml.safe_load` fails to parse the block.
  - `phase:` key is missing from the yaml block.
  - `read_batches` raises `ValueError` (propagated as-is).
- Never silently returns partial data on the above conditions.

**Commit:** `feat(_status): add read_status helper`

---

### Card 2: unit tests for `read_status`

**Reads:** `plugins/mill/unit_tests/test-status.py`, `plugins/mill/scripts/_status.py`

**Modifies:** `plugins/mill/unit_tests/test-status.py`

**Requirements:**

- Import `read_status` at the top alongside existing imports.
- Add a new test block inside `main()` after the existing batch tests.
- Test cases (all using `tempfile.TemporaryDirectory`):
  1. `read_status` on a freshly-rendered `render_initial` file → `phase="discussing"`, `task` equals the title passed, `last_timeline_entry` is the initial timeline row, `current_batch=None`, `blocked_reason=None`.
  2. After `append_phase(sp, "discussed", ts)` → `phase="discussed"`, `last_timeline_entry` is `"discussed  <ts>"`.
  3. After `init_batches(sp, ["b1", "b2"])` and `set_batch_field(sp, "b1", "state", "running")` → `current_batch="b1"`.
  4. Raises `ValueError` on a missing file path.
  5. Raises `ValueError` on a file with no yaml block.
  6. File with a valid yaml block that has no `task:` key → `task` is `None` (no exception) AND `phase` is correctly returned AND `current_batch=None` AND `blocked_reason=None` (full shape check).
  7. File with a well-formed top yaml block but a malformed `## Batches` section (e.g. unclosed `` ```yaml `` fence) → `ValueError` is raised.
- Print `PASS: ...` for each case.
- Run `python plugins/mill/unit_tests/test-status.py` after implementing and confirm all tests pass.

**Commit:** `test(_status): unit tests for read_status`
