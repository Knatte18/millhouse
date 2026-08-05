---
name: mill-resume
description: Resume an active task on another machine or after a fresh clone. Recreates <container>/wts/<slug> from the remote branch so the user can continue with mill-go.
---

# mill-resume

One-shot.
Finds an `[active]` task in `Home.md` that has no local worktree, then recreates the worktree from the remote branch so the user can continue with `mill-go`.

**Task state lives on the branch.** `status.md`, `discussion.md`, `plan/`, and `reviews/` are committed files on the task branch — not in the wiki.
After `git worktree add` in Phase 6, they are available at `<container>/wts/<slug>/status.md` etc. No separate wiki-state copy step is needed.

**Cross-machine resume:** on a machine that has never checked out the task branch, run `git fetch origin` first to make the remote-tracking ref available. `git worktree add` will then check out the branch automatically.

---

## Usage

```
mill-resume <slug>
mill-resume
```

If a slug is passed, resume that specific task.
If no argument is provided, list resume candidates and let the user pick.

---

## Phases

### Phase 1: Verify setup

If `_mill/status.md` exists at cwd (this is a genuine task worktree, just missing scaffolding) AND either `.millhouse/config.local.yaml` (or the legacy `.millhouse/config.yaml`) or the `.wiki` junction is missing, skip the two checks below and go directly to **Phase 1b: Repair an off-canonical worktree**.

Otherwise:

If `.millhouse/config.local.yaml` (or the legacy `.millhouse/config.yaml`) does not exist, stop and tell the user to run `mill-setup` first.

If the `.wiki` junction does not exist at cwd, stop and tell the user to run `mill-setup` first (the wiki junction is required to read task state).

Both present: verify the wiki daemon is healthy before proceeding to Phase 2.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
import _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
if not _client.health_check(wiki_path):
    print('[mill-resume] wiki daemon health check failed', file=sys.stderr)
    raise SystemExit(1)
"
```

If this fails, halt: tell the user the wiki daemon is unreachable or unhealthy and to inspect the reason `health_check()` printed to stderr before retrying.

### Phase 1b: Repair an off-canonical worktree

Reached only when Phase 1 found `_mill/status.md` at cwd but `.millhouse/config.local.yaml` or the `.wiki` junction is missing -- a task worktree that was hand-created (e.g. via `git worktree add`) outside any mill skill, at a non-canonical path, and never scaffolded.
This repair is scoped to `mill-resume` alone -- if a different skill is run directly from inside such a worktree, that skill's own existing missing-scaffolding handling applies unchanged;
direct the user to run `mill-resume` instead.

**Step 1 -- read slug and safety pre-check.**

Read `_mill/status.md` at cwd;
parse `slug:` from the YAML block.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
import _paths, _resume_repair
lines = _resume_repair.check_uncommitted_changes(_paths.resolve_git_root())
if lines:
    print('\n'.join(lines), file=sys.stderr)
    raise SystemExit(1)
"
```

If this halts: tell the user the worktree has uncommitted changes -- commit or stash them, then re-run `mill-resume`.
Do not proceed.

**Step 2 -- collision check.**

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import _paths, _status
git_root = _paths.resolve_git_root()
container_path = _paths.resolve_container_path(git_root)
canonical = _paths.resolve_canonical_worktree_path(container_path, '<slug>')
print(canonical)
if not canonical.exists():
    print('FREE')
else:
    candidate_status = canonical / '_mill' / 'status.md'
    if candidate_status.exists() and _status.read(candidate_status).get('slug') == '<slug>':
        print('RESUMABLE')
    else:
        print('COLLISION')
"
```

If `COLLISION`: halt -- tell the user the canonical path already exists (a different task,
or an unrelated directory) and to resolve manually before re-running `mill-resume`.
Do not proceed;
no mutation attempted.

If `RESUMABLE`: the canonical path already exists and its own `_mill/status.md` carries the *same* slug being repaired -- this is a worktree from a prior Phase 1b run whose `move()` step succeeded but whose scaffold steps (`.millhouse` copy / `.wiki` junction) did not complete.
Skip Step 3's confirmation prompt (the operator already approved this relocation in the prior run) and go directly to Step 4 -- `relocate_and_scaffold` (Card 8) is idempotent and will skip the already-done `move()`, re-run the safe-to-repeat `.millhouse` copy, and create the `.wiki` junction only if it is not already present.

**Step 3 -- confirm with the user.**

Present as a numbered-options prompt:

```
Worktree at <cwd> is task '<slug>' but is missing .millhouse/.wiki
scaffolding.
  1) Relocate to <canonical> and scaffold it (recommended)
  2) Cancel, do nothing
```

If the user picks 2 (or anything but 1), stop without mutating anything.

**Step 4 -- relocate and scaffold.**

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
import _paths, _resume_repair
git_root = _paths.resolve_git_root()
container_path = _paths.resolve_container_path(git_root)
canonical = _paths.resolve_canonical_worktree_path(container_path, '<slug>')
main_root = _paths.resolve_main_worktree_root(git_root)
hub_root = _paths.resolve_hub_path(cwd=main_root)
wiki_path = _paths.resolve_wiki_path(git_root)
try:
    _resume_repair.relocate_and_scaffold(git_root, canonical, hub_root, wiki_path)
except Exception as e:
    print(str(e), file=sys.stderr)
    raise SystemExit(1)
print(canonical)
"
```

If this fails, report the printed stderr and stop.
Tell the user: re-running `mill-resume` will retry safely -- `relocate_and_scaffold` (Card 8) is idempotent, so if the failure was in `git worktree move` itself (locked worktree, cross-filesystem move, permission error), nothing was mutated and the retry starts the move over from `<cwd>`;
if the move already succeeded and a later scaffold step (`.millhouse` copy or `.wiki` junction) is what failed, the worktree now lives at `<canonical>` and Step 2's `RESUMABLE` branch on the next run will route straight back into Step 4 to finish scaffolding without re-attempting the move.

`hub_root` resolution is two steps, each closing a different bug: first `main_root = _paths.resolve_main_worktree_root(git_root)` -- resolved purely from git's own common-directory metadata, never consulting cwd's own `.millhouse/`.
This step alone is necessary because Phase 1 branches into Phase 1b when *either* `.millhouse/config.local.yaml` *or* `.wiki` is missing, so `.millhouse/config.local.yaml` can still exist at cwd (the `.wiki`-only-missing case) -- a bare `_paths.resolve_hub_path()` call (which cwd-walks from `Path.cwd()` by default) would find that local file immediately and return the broken worktree itself, exactly the `cwd == old_worktree` situation `move()`'s own docstring (Card 7) warns against.
Second, `hub_root = _paths.resolve_hub_path(cwd=main_root)` -- passing the already-resolved `main_root` as `resolve_hub_path`'s explicit `cwd` argument runs its normal stub/`hub_relative_path`-aware walk (`_paths.py:159-225`) rooted at the true main worktree instead of at the broken worktree's cwd, so an M2+sub repo whose main-worktree hub `.millhouse` lives in a subdirectory (e.g. `src/csharp/NORCE.Models/.millhouse` -- the same repo shape Batches 3/4 fix elsewhere in this task) still resolves to the correct `.millhouse` source.
Using `resolve_main_worktree_root` alone (an earlier draft of this step) would silently source `.millhouse` from the wrong directory for exactly that repo shape -- `_worktree.copy_millhouse` no-ops without raising when its `src` argument does not exist (`_worktree.py:104-105`), so the failure would be silent, not an exception.

**Step 5 -- report and continue.**

The worktree now lives at `<canonical>`.
Report this explicitly: "Relocated to `<canonical>`."
Every subsequent step in this session must reference `<canonical>` by absolute path -- do not assume the current shell's cwd followed the move.
Continue directly to **Phase 9: Read and report phase**, using `<canonical>` as the worktree path;
skip Phases 2-8 (the slug is already known from `_mill/status.md`, the worktree already exists, and scaffolding is already done by Step 4 above).

### Phase 2: Resolve the slug

**If a slug argument was passed:** use it directly.
Skip to Phase 4.

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

`<container>` is `_paths.resolve_container_path(git_root)`.
Read `repo.branch-prefix` from config (if set).
Derive `branch_name` for each slug: if prefix is set and non-empty, `branch_name = f"{prefix}/{slug}"`;
otherwise `branch_name = slug`.

Present candidates as a numbered list:

```
Resume candidates:
  1) <slug-a>  (phase: implementing)
  2) <slug-b>  (phase: planned)
Pick a number:
```

The phase shown is from the remote branch tip's `_mill/status.md`.
Fetch and read it with `git show origin/<branch_name>:_mill/status.md`;
parse the `phase:` field from the YAML block.
If the file is absent or unreadable, show `(phase: unknown)`.

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

If the remote-tracking branch is not yet fetched locally, run `git fetch origin <branch_name>` first;
`git worktree add` requires the tracking ref to be present.
If `git worktree add` fails (branch already checked out elsewhere, disk error, etc.), report the error and stop.

### Phase 7: Copy `.millhouse/` from parent

Copy `.millhouse/` (excluding `scratch/` and `children/`) from the parent worktree (cwd) to the new worktree.
This gives the new worktree the config and wrapper scripts. (`_mill/` lives at the worktree root on the task branch and is not under `.millhouse/` — no exclusion needed.)

Also copy `.millhouse/config.local.yaml` from the parent to the new worktree if it exists.

This is the same copy step as `mill-spawn` — see `plugins/mill/scripts/millpy/entrypoints/spawn_task.py` for the canonical implementation.

### Phase 8: Create `.wiki` junction

Create a `.wiki` junction in the new worktree pointing at the same wiki clone as the parent:

```python
from _junction import create as junction_create
junction_create(wiki_clone_path, new_worktree / ".wiki")
```

### Phase 9: Read and report phase

Read `<container>/wts/<slug>/_mill/status.md` from the newly added worktree.
Parse the `phase:` field from the YAML block.

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
| `.millhouse/config.local.yaml` missing | Stop, tell user to run `mill-setup` (only when `_mill/status.md` is also absent at cwd -- otherwise branch to Phase 1b) |
| `.wiki` junction missing | Stop, tell user to run `mill-setup` (only when `_mill/status.md` is also absent at cwd -- otherwise branch to Phase 1b) |
| wiki daemon health check fails (Phase 1) | Halt; tell user to inspect the printed reason |
| Phase 1b: worktree has uncommitted changes | Halt with a clear message; worktree untouched |
| Phase 1b: canonical path occupied by an unrelated worktree/task | Halt identifying the collision; no mutation attempted |
| Phase 1b: canonical path occupied by this same task's own interrupted repair | Skip confirmation, resume scaffolding via idempotent relocate_and_scaffold |
| Phase 1b: relocate_and_scaffold fails (move or scaffold step) | Report the error with stderr and stop; safe to re-run mill-resume -- retry is idempotent |
| `_client` mutation raises `WikiPushError` | Report error; daemon failed to push to wiki remote — do not proceed (stale state risk) |
| No remote branch for slug | Halt with manual-resolution message |
| Remote branch has no status.md | Halt with manual-resolution message (pre-migration task) |
| `git worktree add` fails | Report error with stderr |
| No resume candidates | Print "no tasks to resume" and stop |
