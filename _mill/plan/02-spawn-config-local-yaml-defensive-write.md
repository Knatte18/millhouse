# Batch: spawn-config-local-yaml-defensive-write

```yaml
task: 'mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies'
batch: spawn-config-local-yaml-defensive-write
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-spawn.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #834: a newly-spawned worktree can end up without `.millhouse/config.local.yaml` at its hub root (`dest_hub`) when `_worktree.copy_millhouse` does not produce that file (the exact historical cause is unconfirmed — `copy_millhouse` itself has no swallowed exceptions, so any failure there would already propagate to `millpy-spawn.py`'s outer rollback). The fix adds an unconditional, idempotent self-heal write immediately after the `copy_millhouse` call: if `dest_hub/.millhouse/config.local.yaml` is missing, write it directly with the same `{"hub_relative_path": hub_subpath}` content shape the existing gated stub-write block (lines 263-269, a *different* file at the worktree root, unaffected by this change — see Card 3's Requirements) already writes. This runs regardless of the `hub_subpath != "."` gate that block is scoped to, so it also covers this repo's own container-form layout (`hub_relative_path: .`), which the existing gated block never touches.

External interface: none. `millpy-spawn.py main()`'s only new behavior is a no-op when `config.local.yaml` already exists (the overwhelmingly common case) and a self-heal write when it's missing. Self-contained batch.

## Cards

### Card 3: defensive self-heal write for `dest_hub/.millhouse/config.local.yaml`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `millpy-spawn.py`'s `main()`, immediately after the `_worktree.copy_millhouse(...)` call (the block at lines 212-216, ending with the closing `)`), and before the `# Timestamp used for write_initial_status.` comment at line 218, insert:
  ```python
  # Defensive self-heal: copy_millhouse should have copied config.local.yaml from the hub,
  # but if it didn't (cause unconfirmed -- copy_millhouse has no swallowed exceptions),
  # write it directly so the new worktree is never left without one.
  config_local_path = dest_hub / ".millhouse" / "config.local.yaml"
  if not config_local_path.exists():
      config_local_path.parent.mkdir(parents=True, exist_ok=True)
      config_local_path.write_text(
          yaml.safe_dump({"hub_relative_path": hub_subpath}),
          encoding="utf-8",
      )
  ```
  This uses `dest_hub` (already bound at line 144: `dest_hub = resolve_hub_relative_path(worktree_path, hub_subpath)`) and `hub_subpath` (already bound at line 98: `hub_subpath = cfg.get("hub_relative_path", ".")`) — no new parameters or imports needed; `yaml` is already imported at module level (used later at line 267 in the existing gated stub-write block). This insertion runs unconditionally for both `hub_subpath == "."` and `hub_subpath != "."` — it is NOT gated the way the existing `if hub_subpath != ".":` block at lines 263-269 is. Do not modify that existing block; it writes a different file (`worktree_path/.millhouse/config.local.yaml`, the worktree-root bootstrap stub for terminal/vscode discovery when the hub lives in a subfolder), which is unrelated to `dest_hub`'s own config.
- **Commit:** `fix(spawn): self-heal missing dest_hub config.local.yaml after copy_millhouse (#834)`

### Card 4: regression tests for the self-heal write, both layout variants

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add an `omit_source_config: bool = False` keyword parameter to `_run_spawn_real_fs` (`test-millpy-spawn.py:750-763`). Guard the existing source-hub config write (currently unconditional at lines 767-775: `(hub / ".millhouse" / "config.local.yaml").write_text(...)`) with `if not omit_source_config:` so that when `omit_source_config=True`, the source hub's `.millhouse/` directory is created (line 768: `(hub / ".millhouse").mkdir(parents=True)`) but no `config.local.yaml` is written into it — this simulates `copy_millhouse` finding nothing to copy for that file (the exact fixture technique the discussion's Testing plan names: "pre-emptying the source hub's `.millhouse/` of that file"). `_fake_copy_millhouse_real` (already used as `worktree_mock.copy_millhouse.side_effect`) needs no change — it already only copies entries that exist in `src`.

  Add two new standalone test functions, following this file's existing `def test_xxx() -> None:` convention (see `test_spawn_standard_layout_regression` at line 871 and `test_spawn_subfolder_install_destination_layout` at line 919 for the exact assertion style — `raise AssertionError(...)` on failure, `print("PASS: ...")` on success):

  1. `test_spawn_self_heals_missing_config_local_yaml_standard_layout`: call `_run_spawn_real_fs(tmpdir, ".", omit_source_config=True)` (standard/container-form layout, `hub_subpath == "."`, so `dest_hub == wt`). Assert `exit_code == 0`. Assert `(wt / ".millhouse" / "config.local.yaml").exists()`. Read and `yaml.safe_load` it; assert the parsed dict equals exactly `{"hub_relative_path": "."}`.
  2. `test_spawn_self_heals_missing_config_local_yaml_subfolder_layout`: call `_run_spawn_real_fs(tmpdir, "src/Models", slug="subfolder-self-heal", title="Subfolder Self Heal", omit_source_config=True)`. Assert `exit_code == 0`. Let `dest_hub = wt / "src/Models"`. Assert `(dest_hub / ".millhouse" / "config.local.yaml").exists()`. Read and `yaml.safe_load` it; assert the parsed dict equals exactly `{"hub_relative_path": "src/Models"}`. Additionally assert the pre-existing worktree-root bootstrap stub is STILL written and unaffected: `(wt / ".millhouse" / "config.local.yaml")` also exists (from the existing gated block at `millpy-spawn.py:263-269`), proving Card 3's change does not interfere with the unrelated worktree-root stub.

  Register both new functions in the `tests = [...]` list inside `main()` (`test-millpy-spawn.py:1450-1467`), immediately after the existing `test_spawn_subfolder_install_destination_layout` entry.
- **Commit:** `test(spawn): regression coverage for config.local.yaml self-heal, both layouts (#834)`

## Batch Tests

`verify:` runs `test-millpy-spawn.py` directly (single file). Card 4 adds two new registered test functions exercising Card 3's fix on both the `hub_subpath == "."` and `hub_subpath != "."` layout variants named in the discussion's Testing plan.
