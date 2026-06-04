---
name: mill-resume
description: Resume an active task on another machine or after a fresh clone. Recreates <container>/wts/<slug> from the remote branch so the user can continue with mill-go.
---

# mill-resume

One-shot. Finds an `[active]` task in `Home.md` that has no local worktree, then recreates the worktree from the remote branch so the user can continue with `mill-go`.

**Task state lives on the branch.** `status.md`, `discussion.md`, `plan/`, and `reviews/` are committed files on the task branch — not in the wiki. After `git worktree add` in Phase 6, they are available at `<container>/wts/<slug>/status.md` etc. No separate wiki-state copy step is needed.

**Cross-machine resume:** on a machine that has never checked out the task branch, run `git fetch origin` first to make the remote-tracking ref available. `git worktree add` will then check out the branch automatically.

---

## Usage

```
mill-resume <slug>
mill-resume
```

If a slug is passed, resume that specific task. If no argument is provided, list resume candidates and let the user pick.

---

## Phases

### Phase 1: Verify setup

If `.millhouse/config.local.yaml` (or the legacy `.millhouse/config.yaml`) does not exist, stop and tell the user to run `mill-setup` first.

If the `.wiki` junction does not exist at cwd, stop and tell the user to run `mill-setup` first (the wiki junction is required to read task state).

### Phase 2: Resolve the slug

**If a slug argument was passed:** use it directly. Skip to Phase 4.

**If no argument was passed:** query the wiki for resume candidates:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json, _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
tasks = _client.list_tasks_brief(wiki_path)
print(json.dumps([t for t in tasks if t.get('status') == 'active'], indent=2))
"
```

A resume candidate is a task with `status == "active"` that does NOT already have a local worktree at `<container>/wts/<slug>/` with a matching branch (`git branch --list <branch_name>` returns output).

`<container>` is `_paths.resolve_container_path(git_root)`. Read `repo.branch-prefix` from config (if set). Derive `branch_name` for each slug: if prefix is set and non-empty, `branch_name = f"{prefix}/{slug}"`; otherwise `branch_name = slug`.

Present candidates as a numbered list:

```
Resume candidates:
  1) <slug-a>  (phase: implementing)
  2) <slug-b>  (phase: planned)
Pick a number:
```

The phase shown is from the remote branch tip's `_mill/status.md`. Fetch and read it with `git show origin/<branch_name>:_mill/status.md`; parse the `phase:` field from the YAML block. If the file is absent or unreadable, show `(phase: unknown)`.

If there are no candidates (all active tasks already have a local worktree), print:

```
No tasks to resume. All active tasks already have a local worktree.
```

and stop.

### Phase 4: Derive branch name

Given the slug (from argument or user pick), derive the full branch name:

- If `repo.branch-prefix` from config is set and non-empty: `branch_name = f"{prefix}/{slug}"`
- Otherwise: `branch_name = slug`

All subsequent git commands use `<branch_name>`, NOT `<slug>` directly.

### Phase 5: Pre-flight checks

**Check 1 — remote branch exists:**

```bash
git ls-remote --exit-code origin <branch_name>
```

If the remote branch does not exist, halt with:

```
No remote branch '<branch_name>' exists. The task is active but the feature branch was never pushed — resolve manually (abandon or push-first).
```

**Check 2 — remote branch has a status.md:**

```bash
git show origin/<branch_name>:_mill/status.md
```

If the file is absent (pre-migration task whose state was in the wiki but was never committed to the branch), halt with:

```
Branch '<branch_name>' exists but has no _mill/status.md. This task may predate the container-layout migration — resolve manually: commit a status.md to the branch, or run mill-abandon to clean up.
```

### Phase 6: Create worktree

```bash
git -C <git-root> worktree add <container>/wts/<slug> <branch_name>
```

Where:
- `<git-root>` is `git rev-parse --show-toplevel` from cwd.
- `<container>` is `_paths.resolve_container_path(<git-root>)`.
- The worktree lands at `<container>/wts/<slug>/` — the canonical location for all task worktrees in the container layout.

If the remote-tracking branch is not yet fetched locally, run `git fetch origin <branch_name>` first; `git worktree add` requires the tracking ref to be present. If `git worktree add` fails (branch already checked out elsewhere, disk error, etc.), report the error and stop.

### Phase 7: Copy `.millhouse/` from parent

Copy `.millhouse/` (excluding `scratch/` and `children/`) from the parent worktree (cwd) to the new worktree. This gives the new worktree the config and wrapper scripts. (`_mill/` lives at the worktree root on the task branch and is not under `.millhouse/` — no exclusion needed.)

Also copy `.millhouse/config.local.yaml` from the parent to the new worktree if it exists.

This is the same copy step as `mill-spawn` — see `plugins/mill/scripts/millpy/entrypoints/spawn_task.py` for the canonical implementation.

### Phase 8: Create `.wiki` junction

Create a `.wiki` junction in the new worktree pointing at the same wiki clone as the parent:

```python
from _junction import create as junction_create
junction_create(wiki_clone_path, new_worktree / ".wiki")
```

### Phase 9: Read and report phase

Read `<container>/wts/<slug>/_mill/status.md` from the newly added worktree. Parse the `phase:` field from the YAML block.

### Phase 10: Report

Print:

```
Resumed task '<slug>' at phase: <phase>. Run mill-go to continue.
  Branch: <branch-name>
  Path:   <project-path>
```

If the current phase is a review phase (e.g. `plan-reviewing`, `reviewing`), also print:

```
Note: task is mid-review. mill-go will re-enter the current phase from its start (new review round; reviewer invocations are idempotent via timestamped filenames).
```

---

## Error Conditions

| Condition | Action |
|---|---|
| `.millhouse/config.local.yaml` missing | Stop, tell user to run `mill-setup` |
| `.wiki` junction missing | Stop, tell user to run `mill-setup` |
| `_client` mutation raises `WikiPushError` | Report error; daemon failed to push to wiki remote — do not proceed (stale state risk) |
| No remote branch for slug | Halt with manual-resolution message |
| Remote branch has no status.md | Halt with manual-resolution message (pre-migration task) |
| `git worktree add` fails | Report error with stderr |
| No resume candidates | Print "no tasks to resume" and stop |
