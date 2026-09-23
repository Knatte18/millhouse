# Batch: status-path-coercion

```yaml
task: 'mill-plan/verify/implement pipeline: misc small bugs, round 3'
batch: status-path-coercion
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
depends-on: []
```

## Batch Scope

Fixes GitHub #1114: `_status` helpers raise `TypeError` on a plain `str` `status_path`, while every SKILL.md pseudocode call site passes a bare `status_path`.
After this batch, every public `_status` function taking `status_path` accepts `pathlib.Path`, `str`, or any `os.PathLike` and coerces it to `Path`; other types still raise a clear `TypeError` naming the function (the #597 goal).
No SKILL.md call site changes.

## Cards

### Card 3: coerce str/PathLike status_path in _status helpers

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_status.py`:
  - Add `import os` to the module imports.
  - Replace `_require_path(status_path, fn_name: str) -> None` with `_as_path(status_path, fn_name: str) -> Path`: return `status_path` unchanged when it is already a `Path`; return `Path(status_path)` when it is a `str` or an `os.PathLike`; otherwise raise `TypeError(f"{fn_name}: status_path must be a pathlib.Path, str, or os.PathLike, got {type(status_path).__name__}")`. Rewrite its docstring: it coerces instead of rejecting, and still gives a clear error for uncoercible types (GitHub #597, #1114).
  - In every public function that calls `_require_path` today, replace the call with `status_path = _as_path(status_path, "<fn>")` (same literal function name as today), keeping it as the first statement after the docstring so every later use (including private helpers such as `_write_batches` that receive `status_path`) sees a `Path`. `grep -n "_require_path"` enumerates the call sites; after the change that grep must return nothing.
  - Apply the same `_as_path` rebinding to any public function whose first parameter is `status_path` but has no `_require_path` call today (`resume_batch` is one; check every public `def` whose first parameter is `status_path`), so the whole public surface accepts `str` consistently.
  - Change each such public function's `status_path` annotation from `Path` to `Path | str` and add one sentence to its `status_path` Args entry (where the docstring has one) that a `str`/`os.PathLike` is accepted and coerced. If the module docstring's API list states `status_path` must be a `Path`, update that statement too.
  In `plugins/mill/unit_tests/test-status.py`:
  - Replace the "str-input-raises-TypeError regression tests (GitHub #597)" block (the three try/except blocks for `append_phase`, `update_field`, `set_blocked` with a `"some/str/path"` argument) with coercion tests, each on a fresh temp status file rendered via `render_initial`: `append_phase`, `update_field`, `set_blocked` and `read_status` called with `str(path)` produce the same effect/result as with the `Path`; a non-`Path` `os.PathLike` (a tiny local class with `__fspath__`) works for `append_phase`; `append_phase(None, ...)` and `append_phase(123, ...)` raise `TypeError` whose message contains `append_phase`.
  - Update the block's leading comment to reference GitHub #1114 and the coercion contract.
- **Commit:** `fix(status): accept str/PathLike status_path in _status helpers (#1114)`

## Batch Tests

`verify:` runs `test-status.py`, which exercises every `_status` helper with `Path` inputs (proving the rebinding is behaviour-neutral) plus the new str/PathLike/invalid-type cases.
Per-file scoping is sufficient: the change only widens accepted input types, so no existing `Path` caller elsewhere can regress.
