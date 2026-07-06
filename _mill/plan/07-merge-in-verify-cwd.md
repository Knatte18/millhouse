# Batch: merge-in-verify-cwd

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
batch: merge-in-verify-cwd
number: 7
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
depends-on: [3]
```

## Batch Scope

Fixes #604 for the third replay site found during discussion review: `mill-merge-in/SKILL.md` step 4 ("Verify") also consumes `iter_batch_verifies` to replay every batch's verify command after a merge-in sync, but currently unpacks the old `(name, cmd)` 2-tuple and runs each command "from the worktree root" with no per-batch cwd distinction — this both breaks on batch 3's new 3-tuple shape and reproduces #604 for any batch whose verify resolves to `cwd: hub`. Depends on batch 3 for the 3-tuple shape.

## Cards

### Card 26: Update mill-merge-in's Verify step for the 3-tuple and resolved cwd

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In step 4 ("Verify"), update the call `_plan_dag.iter_batch_verifies(plan_dir)` to `_plan_dag.iter_batch_verifies(plan_dir, hub_root, git_root)` (`hub_root` resolved via `_paths.resolve_hub_path()`, `git_root` already a local in this SKILL's scope), and update the surrounding prose from "yields `(batch_name, verify_cmd)` pairs" to "yields `(batch_name, verify_cmd, cwd)` triples". Replace the "For each `(name, cmd)`:" loop header and its "Run the command from the worktree root" bullet: unpack `(name, cmd, cwd)` instead, and run each command with its resolved `cwd` (`hub_root` when the tuple's `cwd` is `hub_root`, `git_root` when it is `git_root`, and — matching the existing pre-batch-3 default behavior — `hub_root` when it is `None`, since "the worktree root" this step already resolves to is `hub_root`, not `git_root`). Leave the `${PLUGIN_ROOT}` substitution and `skip_list` allowlist pre-check bullets unchanged — both already operate on the extracted `cmd` string, which is unaffected by the tuple-shape change.
- **Commit:** `docs(mill-merge-in): replay verify commands at their resolved per-batch cwd (#604)`

### Card 27: Add a nested-layout case to integration_tests/test-merge.py

- **Context:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add an integration-level nested-layout case asserting a batch with `verify: {cwd: hub, command: ...}` replays correctly at the resolved `hub_root` during merge-in, not at a fixed "worktree root". Leave the existing `iter_batch_verifies(...) == []` assertion at line `~431` (the all-null-verify seed plan case) unmodified — it is unaffected by the tuple-shape change since the assertion is against an empty list either way, but update its call to pass the two new required arguments (`hub_root`, `git_root`) so it continues to type-check against the batch-3 signature.
- **Commit:** `test(merge): cover nested-layout verify replay cwd resolution (#604)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py` runs the full integration suite, covering the existing empty-list case (updated call signature, unchanged assertion) and the new nested-layout case from Card 27.
