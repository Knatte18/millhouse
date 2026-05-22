# Batch: Callers

```yaml
task: Write active-slug indicator file in hub
batch: Callers
number: 2
cards: 3
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Wires `write_hub_active_indicator` (added in Batch 1) into the three operational scripts that manage task lifecycle: mill-spawn (writes indicator when creating a task worktree), mill-claim (writes indicator when claiming a task in-place), and mill-cleanup (deletes indicator on task teardown in both the in-place and worktree paths). After this batch the feature is functionally complete.

## Cards

### Card 4: Call `write_hub_active_indicator` in `millpy-spawn.py`

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-spawn.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In `millpy-spawn.py`'s `main()`, immediately after the call `_spawn_core.recreate_active_junction(dest_hub)` (which is past the dry-run guard), add the call `_spawn_core.write_hub_active_indicator(git_root, slug)`.
  2. Pass `git_root` (the real hub, resolved at the top of `main()` via `resolve_git_root()`), not `dest_hub` (which is the task worktree). The indicator must be written to the real hub's `_mill/`, not the task worktree's `_mill/`.
  3. No other changes to `millpy-spawn.py`.
- **Commit:** `feat(mill-spawn): write hub active indicator after claim`

### Card 5: Call `write_hub_active_indicator` in `millpy-claim.py`

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In `millpy-claim.py`'s `main()`, immediately after the call `_spawn_core.recreate_active_junction(resolve_hub_path())` (line 299, which is past the dry-run guard), add the call `_spawn_core.write_hub_active_indicator(resolve_hub_path(), slug)`.
  2. In the claim (in-place) case the hub IS the task worktree, so `resolve_hub_path()` is the correct hub_root for the indicator.
  3. No other changes to `millpy-claim.py`.
- **Commit:** `feat(mill-claim): write hub active indicator after claim`

### Card 6: Delete indicator in `millpy-cleanup.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  1. In `_apply_inplace_record`, after the existing `.active` junction removal block (after `_junction.remove(active_junction)` and its associated `print` at line 385), add:
     ```python
     indicator = hub_root / "_mill" / f"{record.slug}.active"
     indicator.unlink(missing_ok=True)
     print(f"[cleanup] removed hub active indicator: {indicator}", file=sys.stderr)
     ```
  2. In `_apply_worktree_record`, after the existing portal entry removal block (after `_junction.remove(container_path / "portals" / record.slug)` and its associated `print` at line 429), add the identical three lines (constructing `indicator` the same way using `hub_root` and `record.slug`).
  3. The `print` call is `file=sys.stderr` to match the existing cleanup log style.
  4. No other changes to `millpy-cleanup.py`.
- **Commit:** `feat(mill-cleanup): delete hub active indicator on task teardown`

## Batch Tests

Verify with `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. The existing tests confirm callers are not broken; dedicated indicator tests are in Batch 3.
