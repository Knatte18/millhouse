# Discussion: 20 (A) — mill UX-fixes: teardown + spawn-integration

```yaml
task: '20 (A) — mill UX-fixes: teardown + spawn-integration'
slug: mill-merge-teardown-fix
status: discussing
parent: main
```

## Problem

Two independent UX failures in mill's worktree lifecycle. Both surfaced as broken operator workflows with no reasonable workaround.

**Fix A (#161):** When a CC session is running from inside a task worktree, `mill-merge` crashes on worktree removal with "Permission denied". Windows NTFS locks the current working directory — `git worktree remove --force` fails, and the Python `shutil.rmtree` fallback also raises `PermissionError`. The current code either raises `WorktreeError` (hard halt) or propagates the uncaught Python exception. The merge cannot complete, leaving the worktree stale and the operator stuck.

**Fix B (#162):** `mill-vscode` and `mill-terminal` require an active worktree to exist before they can do anything. In practice, spawn is never used standalone — the operator always runs spawn then immediately runs vscode or terminal. There is no reason to make the operator issue two commands, and no feedback when the worktree list is empty.

## Scope

**In:**
- `plugins/mill/scripts/_worktree.py` — add `WorktreeLockedError` exception; catch the in-use/PermissionError case in `remove_safe`, raise `WorktreeLockedError` instead of `WorktreeError`
- `plugins/mill/skills/mill-merge/SKILL.md` — update Step 8 handling table: `WorktreeLockedError` → skip worktree + branch deletion, print both manual commands, continue to Step 9
- `plugins/mill/scripts/millpy-vscode.py` — when active list is empty (no `--list`, no `--slug`): auto-invoke spawn, re-discover, continue normally
- `plugins/mill/scripts/millpy-terminal.py` — same auto-invoke logic
- `plugins/mill/skills/mill-vscode/SKILL.md` — reflect new auto-spawn behavior
- `plugins/mill/skills/mill-terminal/SKILL.md` — same
- Unit tests for all changed modules

**Out:**
- No change to `millpy-spawn.py`
- No change to the spawn workflow when called directly via `/mill-spawn`
- `--list` and `--slug` flags in millpy-vscode: no auto-spawn (those paths imply caller knows what they want)
- No auto-spawn offered as a picker option when active worktrees exist
- No change to `millpy-merge-in.py` or mill-merge-in skill

## Decisions

### WorktreeLockedError as a WorktreeError subclass

- **Decision:** Add `WorktreeLockedError(WorktreeError)` in `_worktree.py`. `remove_safe` raises it instead of `WorktreeError` when the removal fails due to the path being in use (locked CWD, PermissionError, or git "in use" / access-denied patterns in stderr).
- **Rationale:** SKILL.md can distinguish "directory locked" (skip + continue) from a hard failure (halt) without changing the `remove_safe` return type. Existing callers that catch `WorktreeError` continue to work — the subclass is caught by the parent class catch.
- **Rejected:** Returning `bool` from `remove_safe` would change its `None` signature and require all callers to check the return value; printing inside `remove_safe` and returning normally would leave callers unable to tell whether the directory was actually removed.

### Continue merge after WorktreeLockedError

- **Decision:** When Step 8 raises `WorktreeLockedError`, skip the worktree directory removal AND the `git branch -D` that follows it (the branch cannot be deleted while a worktree is still checked out on it). Print both manual cleanup commands. Continue to Step 9 (portal removal), Step 10 (legacy wiki cleanup), Step 11 (sidebar + merge lock release).
- **Rationale:** The issue says "skip on PermissionError" — the intent is to not block the merge. Portal cleanup, Home.md flip, and sidebar regeneration are all safe even if the worktree directory survives. The operator can delete the directory and branch manually after closing the CC session.
- **Rejected:** Halting entirely (current behavior) — this is exactly the UX failure the issue documents.

### Auto-spawn in vscode/terminal only on empty worktree list

- **Decision:** Auto-invoke spawn only in the `if not active` branch, and only when neither `--list` nor `--slug` is active. When active worktrees exist, show the existing picker unchanged.
- **Rationale:** "spawn is never run alone" describes the most common flow where the operator is starting fresh. When active worktrees exist, the operator is resuming, not starting — offering spawn in the picker would be noise. Operators who want to spawn a new task while others are active use `/mill-spawn` directly.
- **Rejected:** Always including spawn as option N+1 in the picker — adds complexity and UI noise for the common case.

### Empty backlog after auto-spawn

- **Decision:** If spawn returns exit 0 with an empty backlog, print "No tasks available and no active worktrees. Add tasks to Home.md first." and exit 0.
- **Rationale:** Empty backlog is not an error — it is a normal state that will be resolved by adding tasks. Exit 0 is consistent with the current "no active worktrees" exit code and with spawn's own exit-0-on-empty behavior.
- **Rejected:** Exit 1 — misleads the operator into thinking something broke.

### Spawn invocation via importlib

- **Decision:** In millpy-vscode.py and millpy-terminal.py, load millpy-spawn.py via importlib (identical pattern to the unit tests) and call its `main([])` directly. No subprocess wrapping.
- **Rationale:** Avoids subprocess overhead, inherits the already-set `sys.path`, and keeps the call testable with mock patches. millpy-spawn.py is already designed to be called as `main()`.
- **Rejected:** Subprocess call — would require capturing stdout (to suppress it or relay it), and adds test complexity with no benefit.

## Technical context

### _worktree.remove_safe — exact change points

File: `plugins/mill/scripts/_worktree.py`

Two places need changes:

**1. After `git worktree remove` fails (lines 247-252):** Current code checks for "Filename too long". Add a second check for in-use / permission-denied patterns before the final `raise WorktreeError`. Detection string targets:
- `"Permission denied"` (git on Windows NTFS)
- `"is in use"` (git's "worktree is in use" message)
- `"cannot remove"` (git's generic removal failure)

If matched: raise `WorktreeLockedError(f"worktree is locked (path={path}): {stderr!r}")`.

**2. shutil.rmtree fallback (lines 260-261):** Wrap in `try/except PermissionError as exc: raise WorktreeLockedError(...) from exc`. This handles the case where git fails with "Filename too long" AND shutil can't remove the CWD.

**WorktreeLockedError definition:** Add at the top of `_worktree.py` alongside `WorktreeError`:
```python
class WorktreeLockedError(WorktreeError):
    """Raised when a worktree directory cannot be removed because it is in use."""
```

### mill-merge SKILL.md — Step 8 handling table update

File: `plugins/mill/skills/mill-merge/SKILL.md`

Current table row:
```
| "is in use" / "is not empty" | Surface message and halt. |
```

New row:
```
| WorktreeLockedError | Print "[worktree] cannot remove <path>: directory is in use — CC session is running inside it.\nRun after closing this session:\n    git worktree remove --force <path>\n    git branch -D <child_branch>". Skip Step 8 branch deletion. Continue to Step 9. |
```

The child branch name is already captured earlier in Step 8 (before `remove_safe` is called).

### millpy-vscode.py and millpy-terminal.py — spawn integration

Both scripts follow the same pattern. In the `if not active:` block (after `discover_active_worktrees`), add:

```python
if not active:
    # load spawn via importlib (millpy-spawn.py has a hyphenated name)
    import importlib.util as _ilu
    _spawn_spec = _ilu.spec_from_file_location(
        "mill_spawn",
        Path(__file__).parent / "millpy-spawn.py",
    )
    mill_spawn = _ilu.module_from_spec(_spawn_spec)
    _spawn_spec.loader.exec_module(mill_spawn)
    rc = mill_spawn.main([])
    if rc != 0:
        return rc
    active = _spawn_core.discover_active_worktrees(worktrees_dir)
    if not active:
        print("No tasks available and no active worktrees. Add tasks to Home.md first.", file=sys.stderr)
        return 0
    # fall through to normal picker / auto-select
```

This block replaces the current early-return `return 0` for the empty case. For millpy-terminal.py: same insertion point (`if not active:` block). For millpy-vscode.py: only when not `--list` and not `--slug` — the existing early-return for `--list` and `--slug` is not reached when `active` is empty, but be explicit with a guard on the spawn block: `if not active and not args.list and args.slug is None:`.

### Unit test changes

**test-worktree.py:** Add a test for `WorktreeLockedError`. Use `unittest.mock.patch` on `_subprocess_util.run` to return a mock result with `returncode=1` and `stderr="Permission denied"`. Assert `WorktreeLockedError` is raised (not the base `WorktreeError`). Add a parallel test for the `shutil.rmtree` PermissionError path using `unittest.mock.patch("shutil.rmtree", side_effect=PermissionError(...))` after arranging a "Filename too long" git failure.

**test-millpy-terminal.py:** Update the "no active worktrees → exits 0, no subprocess call" test — this test will need to mock the spawn import and assert that spawn's `main` was called. Add a new test: spawn returns 0 + empty backlog → exit 0 with message. Add: spawn returns 0 + one new worktree → auto-selected, subprocess called.

**test-millpy-vscode.py:** Same additions as terminal tests. Also: verify that `--list` and `--slug` with an empty active list still exit 0 without calling spawn.

## Constraints

None from CONSTRAINTS.md (not present). Standard mill constraints from CLAUDE.md apply:
- `${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths
- Junction safety: `strip_all_in_worktree` must still run before any removal attempt — `WorktreeLockedError` is raised AFTER junctions are stripped, so this invariant is preserved

## Testing

**_worktree.py:**
- `WorktreeLockedError` is a subclass of `WorktreeError` (isinstance check)
- `remove_safe` raises `WorktreeLockedError` on "Permission denied" in git stderr
- `remove_safe` raises `WorktreeLockedError` on "is in use" in git stderr
- `remove_safe` raises `WorktreeLockedError` when `shutil.rmtree` raises `PermissionError` (long-path fallback)
- `remove_safe` still raises `WorktreeError` (base) for unrecognised git failures (regression)
- `remove_safe` still returns normally on success (regression)

**millpy-vscode.py:**
- No active worktrees, no flags → spawn called, re-discover, auto-select or picker
- No active worktrees, spawn returns empty backlog → exit 0 with message, no code launched
- No active worktrees, spawn returns rc=1 → exit 1
- `--list` with no active worktrees → exits 0, spawn NOT called
- `--slug` with no active worktrees → exits 0 (slug not found), spawn NOT called
- Existing tests for active-worktree paths must still pass

**millpy-terminal.py:**
- No active worktrees → spawn called, re-discover, auto-select
- No active worktrees, spawn empty backlog → exit 0
- Existing tests must still pass

## Q&A log

- **Q:** Should `remove_safe` raise a new exception type or return a bool to signal "skipped"? **A:** New `WorktreeLockedError(WorktreeError)` subclass — doesn't change return type, callers that catch the base class still work.
- **Q:** After `WorktreeLockedError`, should mill-merge halt or continue? **A:** Continue — skip the worktree directory and branch deletion, print both manual commands, continue Steps 9-11.
- **Q:** Should auto-spawn be offered in the picker when active worktrees exist? **A:** No — only auto-invoke on empty worktree list; operators with active worktrees who want to spawn use `/mill-spawn` directly.
- **Q:** What if the backlog is empty after auto-spawn? **A:** Print message and exit 0; empty backlog is not an error.
- **Q:** Should `--list` and `--slug` in millpy-vscode trigger auto-spawn? **A:** No — both flags imply the caller knows what they want.
