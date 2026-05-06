# Plan: '20 (A) — mill UX-fixes: teardown + spawn-integration'

```yaml
task: '20 (A) — mill UX-fixes: teardown + spawn-integration'
slug: mill-merge-teardown-fix
approved: false
started: 20260506-125506
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: worktree-locked-error
    file: 01-worktree-locked-error.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-worktree.py
  - name: auto-spawn-integration
    file: 02-auto-spawn-integration.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: WorktreeLockedError as WorktreeError subclass

- **Decision:** `WorktreeLockedError(WorktreeError)` is raised by `remove_safe` when the worktree directory cannot be removed because a process (typically the current CC session) holds an NTFS lock on it. The exception carries the path and the original error message.
- **Rationale:** Callers that already `catch WorktreeError` continue to work. Callers that need to distinguish a transient lock from a hard failure can `catch WorktreeLockedError` specifically. The `None` return signature of `remove_safe` does not change.
- **Applies to:** batch worktree-locked-error

### Decision: Auto-spawn helper extracted for testability

- **Decision:** Both `millpy-vscode.py` and `millpy-terminal.py` expose a module-level `_load_spawn_main()` function that encapsulates the importlib load of `millpy-spawn.py` and returns its `main` callable. The `if not active` block calls `_load_spawn_main()` rather than inlining the importlib sequence.
- **Rationale:** Patching `_load_spawn_main` in unit tests is trivial (`patch('mill_vscode._load_spawn_main', return_value=...)`). Patching `importlib.util.spec_from_file_location` inline would require fragile multi-level mock chaining.
- **Applies to:** batch auto-spawn-integration

## All Files Touched

- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/scripts/millpy-terminal.py`
- `plugins/mill/scripts/millpy-vscode.py`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-terminal/SKILL.md`
- `plugins/mill/skills/mill-vscode/SKILL.md`
- `plugins/mill/unit_tests/test-millpy-terminal.py`
- `plugins/mill/unit_tests/test-millpy-vscode.py`
- `plugins/mill/unit_tests/test-worktree.py`
