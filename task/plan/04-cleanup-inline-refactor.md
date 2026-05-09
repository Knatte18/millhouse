# Batch: cleanup-inline-refactor

```yaml
task: "35 (A) — Centralize path resolution across all three modes"
batch: cleanup-inline-refactor
number: 4
cards: 1
verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanup.py
depends-on: []
```

## Batch Scope

`millpy-cleanup.py:103-114` has 11 lines of inline `hub_relative_path` resolution that duplicate `_paths.resolve_hub_relative_path`. The duplication predates the path-invariants work and is a maintenance liability — the next hub_relative_path edge case will require touching two places.

This batch replaces the inline block with a single call to the existing `resolve_hub_relative_path`. It does NOT depend on Batch 1 because `resolve_hub_relative_path` is unchanged by this task; it can run in parallel with Batch 1.

## Cards

### Card 7: replace inline hub_relative_path block with resolve_hub_relative_path call

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_active.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-cleanup.py:103-114`, replace the 11-line inline block with a `resolve_hub_relative_path` call. The current block:

  ```python
  hub_subpath = "."
  stub_path = wt_path / ".millhouse" / "config.local.yaml"
  if stub_path.exists():
      try:
          stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
          hub_subpath = stub_data.get("hub_relative_path", ".")
      except Exception:  # noqa: BLE001
          hub_subpath = "."
  hub_mill_dir = (
      wt_path / ".millhouse" if hub_subpath == "."
      else wt_path / hub_subpath / ".millhouse"
  )
  ```

  Becomes:

  ```python
  hub_subpath = "."
  stub_path = wt_path / ".millhouse" / "config.local.yaml"
  if stub_path.exists():
      try:
          stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
          hub_subpath = stub_data.get("hub_relative_path", ".")
      except Exception:  # noqa: BLE001
          hub_subpath = "."
  hub_mill_dir = _paths.resolve_hub_relative_path(wt_path, hub_subpath) / ".millhouse"
  ```

  The stub-read + try/except stays inline (the helper does not consume the stub); only the final two-branch ternary collapses into a single helper call. Add `import _paths` to the imports if not already present (it is — confirm at the top of the file).

  Behavior must be byte-equivalent: `resolve_hub_relative_path(wt_path, ".")` returns `wt_path` unchanged; `resolve_hub_relative_path(wt_path, "src/Models")` returns `wt_path / "src" / "Models"`; trailing slashes are normalized. The existing `test-cleanup.py` exercises both branches.
- **Commit:** `refactor(cleanup): use resolve_hub_relative_path for hub-mill-dir lookup`

## Batch Tests

The verify command runs `test-cleanup.py`. The change is a behavior-preserving refactor; existing tests cover both `hub_relative_path == "."` and the sub-dir cases via the cleanup loop's hub-mill-dir resolution. No test changes needed.
