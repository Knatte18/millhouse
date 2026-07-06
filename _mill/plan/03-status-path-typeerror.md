# Batch: status-path-typeerror

```yaml
task: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash
batch: status-path-typeerror
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
depends-on: []
```

## Batch Scope

Fixes GitHub #597: `_status.append_phase(status_path, phase, timestamp)` (and every other public `status_path`-taking function in `_status.py`) calls `status_path.read_text(...)` assuming a `pathlib.Path`; passed a plain `str`, it crashes with a bare, unexplained `AttributeError` instead of a clear error naming the expected type. Card 5 adds one shared guard helper and applies it to all seventeen public `status_path`-taking functions (not just `append_phase`); Card 6 adds regression coverage. No API signature changes — callers that already pass a `Path` see no behavior change. External interface: none; the next batch does not depend on this one.

## Cards

### Card 5: Add `_require_path` guard to every public status_path-taking function

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new module-level helper near the top of `plugins/mill/scripts/_status.py` (after the existing constant definitions, e.g. after `_TIMELINE_FENCE`):
  ```python
  def _require_path(status_path, fn_name: str) -> None:
      if not isinstance(status_path, Path):
          raise TypeError(
              f"{fn_name}: status_path must be a pathlib.Path, got {type(status_path).__name__}"
          )
  ```
  Call `_require_path(status_path, "<fn_name>")` as the first statement inside each of these seventeen public functions (the `<fn_name>` argument is that function's own name as a literal string), per the module docstring's Public API list (lines 18-37): `read`, `read_full`, `read_parent_branch`, `read_slug`, `read_branch`, `phase_entry_timestamp`, `update_field`, `set_blocked`, `append_phase`, `init_batches`, `set_batch_field`, `set_batch_fields`, `read_batches`, `read_status`, `get_module_verify_baseline`, `set_module_verify_baseline`, `clear_module_verify_baseline`. Do NOT add the guard to `_write_batches` (private helper, leading underscore, line 606) or to `render_initial` (does not take `status_path` as an argument). Do not change the body of any of these functions beyond inserting the one guard call as their first statement — no behavior change for existing `Path`-typed callers.
- **Commit:** `fix(status): raise clear TypeError for non-Path status_path across all public functions (#597)`

### Card 6: Add str-input-raises-TypeError regression tests

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add new test case(s) to `plugins/mill/unit_tests/test-status.py` (the file already imports `append_phase` and others at line 18 and exercises `append_phase` extensively with `Path`-typed `status_path` from line 135 onward — add the new cases near that existing coverage, not interleaved with it). For at least `append_phase`, `update_field`, and `set_blocked`, call each with a plain `str` in place of `status_path` (e.g. `append_phase("some/str/path", "phase", "2026-01-01T00:00:00Z")`, `update_field("some/str/path", "key", "value")`, `set_blocked("some/str/path", "reason", timestamp="2026-01-01T00:00:00Z")`) inside a `try/except TypeError` block, and assert: (a) a `TypeError` is raised (fail the test via `raise AssertionError` if no exception or the wrong exception type is raised), and (b) the exception message contains both the function's own name and the substring `"pathlib.Path"`. Print one `PASS:` line per function tested, matching the file's existing style. Do not modify any existing test case in the file — every existing `Path`-typed call must keep passing unchanged.
- **Commit:** `test(status): cover TypeError on non-Path status_path across guarded functions`

## Batch Tests

`verify:` scopes to `test-status.py` only via `run-all.py --only test-status.py` — both cards touch only `_status.py` and its own test file; `test-status.py` already has extensive existing `Path`-typed coverage that must continue to pass unchanged alongside the new cases.
