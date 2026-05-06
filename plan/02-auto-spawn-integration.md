# Batch: auto-spawn-integration

```yaml
task: '20 (A) — mill UX-fixes: teardown + spawn-integration'
batch: auto-spawn-integration
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Adds auto-spawn integration to `millpy-vscode.py` and `millpy-terminal.py`: when no active worktrees are found and no special flags are set, each script now invokes `millpy-spawn.py` via importlib before proceeding. The spawn entry point is factored into a `_load_spawn_main()` module-level helper for clean unit-test patching. Updates both SKILL.md files to reflect the new behavior. Adds tests covering the new code paths in both scripts.

External interface: `millpy-vscode.py` and `millpy-terminal.py` are invoked by the operator the same way as before; they now do more work on first run (spawning) rather than exiting empty.

## Cards

### Card 4: millpy-vscode.py auto-spawn integration

- **Reads:**
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/skills/mill-vscode/SKILL.md`
- **Modifies:**
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/skills/mill-vscode/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **millpy-vscode.py:**
  1. Add a module-level function `_load_spawn_main() -> callable` immediately before `main()`. It loads `millpy-spawn.py` via importlib and returns its `main` callable:
     ```python
     def _load_spawn_main():
         import importlib.util as _ilu
         spec = _ilu.spec_from_file_location("mill_spawn", Path(__file__).parent / "millpy-spawn.py")
         module = _ilu.module_from_spec(spec)
         spec.loader.exec_module(module)
         return module.main
     ```
  2. Replace the `if not active:` early-return block (currently `print("No active worktrees found.") return 0`) with the following logic:
     - If `args.list` is True OR `args.slug is not None`: print `"No active worktrees found."` (to stderr) and `return 0`. These flag paths bypass spawn.
     - Otherwise (no flags, empty list): call `spawn_main = _load_spawn_main()`, then `rc = spawn_main([])`. If `rc != 0`: `return rc`. Re-discover: `active = _spawn_core.discover_active_worktrees(worktrees_dir)`. If still empty: print `"No tasks available and no active worktrees. Add tasks to Home.md first."` to stderr and `return 0`. Fall through to the existing `args.list` / `args.slug` / picker code below.
  3. The rest of `main()` is unchanged — the `if args.list:`, `if args.slug is not None:`, and picker blocks run normally with the refreshed `active` list.

  **mill-vscode/SKILL.md:**
  Update the description line from "Scans active worktrees and opens VS Code in the selected one." to "Scans active worktrees and opens VS Code in the selected one. When no active worktrees exist and no flags are set, auto-invokes mill-spawn to create a new worktree first."
  Update the exit-0 note to: "Exits 0 (with a message) when no active worktrees exist and the backlog is empty after auto-spawn."
- **Commit:** `feat(mill-vscode): auto-invoke spawn when no active worktrees`

### Card 5: millpy-terminal.py auto-spawn integration

- **Reads:**
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/skills/mill-terminal/SKILL.md`
- **Modifies:**
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/skills/mill-terminal/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  **millpy-terminal.py:**
  1. Add `_load_spawn_main()` — identical implementation to Card 4.
  2. Replace the `if not active:` early-return block (currently `print("No active worktrees found.", file=sys.stderr) return 0`) with:
     - Call `spawn_main = _load_spawn_main()`, then `rc = spawn_main([])`. If `rc != 0`: `return rc`. Re-discover: `active = _spawn_core.discover_active_worktrees(worktrees_dir)`. If still empty: print `"No tasks available and no active worktrees. Add tasks to Home.md first."` to stderr and `return 0`. Fall through to the existing single/multi-picker code.
  3. millpy-terminal.py has no `--list` or `--slug` flags, so no flag guard is needed.
  4. The rest of `main()` is unchanged.

  **mill-terminal/SKILL.md:**
  Update the description line to: "Scans the worktrees container for directories with an `active.slug.md` marker, presents a numbered picker, and launches `claude --name <slug>` in the selected worktree. When no active worktrees exist, auto-invokes mill-spawn to create one first."
  Update the exit-0 note to: "Exits 0 (with a message) when no active worktrees exist and the backlog is empty after auto-spawn."
- **Commit:** `feat(mill-terminal): auto-invoke spawn when no active worktrees`

### Card 6: test-millpy-vscode.py — auto-spawn tests

- **Reads:**
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
  - `plugins/mill/scripts/millpy-vscode.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-millpy-vscode.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add the following test blocks after the existing tests. All patches use the `mill_vscode.*` namespace (the importlib-loaded module alias set up at the top of the test file).

  **Test: no active worktrees, no flags → spawn called, new worktree, code launched.**
  Set up one worktree directory `wt_new`. Patch `discover_active_worktrees` using `side_effect` to return `[]` on the first call and `[(wt_new, "task-new", "New Task")]` on the second call. Patch `mill_vscode._load_spawn_main` to return a callable that records it was called and returns 0. Patch `subprocess.run`. Call `mill_vscode.main([])`. Assert: `_load_spawn_main` callable was invoked with `[]`; `subprocess.run` was called; the path in the subprocess argv contains `wt_new`. Print `"PASS: no active worktrees + no flags → spawn called, new worktree opened"`.

  **Test: no active worktrees, spawn returns non-zero → exit 1, code not launched.**
  Patch `discover_active_worktrees` to return `[]`. Patch `mill_vscode._load_spawn_main` to return a callable returning 1. Patch `subprocess.run`. Call `mill_vscode.main([])`. Assert: return code is 1; `subprocess.run` NOT called. Print `"PASS: spawn non-zero rc → exit 1, no VS Code"`.

  **Test: no active worktrees, spawn returns 0 but backlog empty (re-discover still empty) → exit 0, code not launched.**
  Patch `discover_active_worktrees` to always return `[]`. Patch `mill_vscode._load_spawn_main` to return a callable returning 0. Patch `subprocess.run`. Call `mill_vscode.main([])`. Assert: return code is 0; `subprocess.run` NOT called. Print `"PASS: spawn empty backlog → exit 0, no VS Code"`.

  **Test: `--list` with no active worktrees → spawn NOT called, exit 0.**
  Patch `discover_active_worktrees` to return `[]`. Patch `mill_vscode._load_spawn_main`. Call `mill_vscode.main(["--list"])`. Assert: `_load_spawn_main` NOT called; return code is 0. Print `"PASS: --list with empty active list → spawn not called"`.

  **Test: `--slug` with no active worktrees → spawn NOT called, exit 0.**
  Patch `discover_active_worktrees` to return `[]`. Patch `mill_vscode._load_spawn_main`. Call `mill_vscode.main(["--slug", "nonexistent"])`. Assert: `_load_spawn_main` NOT called; return code is 0. Print `"PASS: --slug with empty active list → spawn not called"`.

  **Update existing test** `"no active worktrees → exits 0, no subprocess call"`: this test was correct for the old behavior. Remove it or rename it to document the new behavior — the closest equivalent is the "spawn empty backlog → exit 0" test above. Do NOT leave a test that asserts `subprocess.run` is NOT called when `discover_active_worktrees` returns `[]` without also patching `_load_spawn_main`, as that would fail under the new code path.
- **Commit:** `test(mill-vscode): add auto-spawn unit tests`

### Card 7: test-millpy-terminal.py — auto-spawn tests

- **Reads:**
  - `plugins/mill/unit_tests/test-millpy-terminal.py`
  - `plugins/mill/scripts/millpy-terminal.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-millpy-terminal.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add the following test blocks after the existing tests. All patches use the `mill_terminal.*` namespace.

  **Test: no active worktrees → spawn called, new worktree, claude launched.**
  Set up one worktree directory `wt_new` with an active marker (`_write_active_marker`). Patch `discover_active_worktrees` with `side_effect` returning `[]` first, then `[(wt_new, "task-new", "New Task")]`. Patch `mill_terminal._load_spawn_main` to return a callable returning 0. Patch `subprocess.run`. Call `mill_terminal.main([])`. Assert: spawn callable was invoked with `[]`; `subprocess.run` called with `cwd=wt_new`. Print `"PASS: no active worktrees → spawn called, claude launched in new worktree"`.

  **Test: no active worktrees, spawn returns non-zero → exit 1.**
  Patch `discover_active_worktrees` to return `[]`. Patch `mill_terminal._load_spawn_main` to return a callable returning 1. Patch `subprocess.run`. Call `mill_terminal.main([])`. Assert: return code 1; `subprocess.run` NOT called. Print `"PASS: spawn non-zero rc → exit 1, no claude"`.

  **Test: no active worktrees, spawn returns 0, backlog empty → exit 0.**
  Patch `discover_active_worktrees` to always return `[]`. Patch `mill_terminal._load_spawn_main` to return a callable returning 0. Patch `subprocess.run`. Call `mill_terminal.main([])`. Assert: return code 0; `subprocess.run` NOT called. Print `"PASS: spawn empty backlog → exit 0, no claude"`.

  **Update existing test** `"no active worktrees → exits 0, no subprocess call"`: same note as Card 6 — this test must either be removed or updated to patch `_load_spawn_main` and represent the "empty backlog" scenario. The test as written will call into `_load_spawn_main()` which will try to load `millpy-spawn.py` for real, which in CI may succeed or fail unpredictably. Replace the old test body to patch `_load_spawn_main` returning a callable that returns 0, `discover_active_worktrees` returning `[]` both times, and assert `subprocess.run` is NOT called.
- **Commit:** `test(mill-terminal): add auto-spawn unit tests`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` runs the full test suite. After this batch, all new tests (spawn-invoked, spawn-error, empty-backlog, flag-guard) must pass, and the five existing hub-relative-path + picker tests in both test-millpy-vscode.py and test-millpy-terminal.py must continue to pass. The full run also catches any accidental regressions in other test files.
