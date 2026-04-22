# mill-cleanup (script)

```yaml
type: script
layer: 04
v1_ref: plugins/mill/skills/mill-cleanup/
status: partially discussed — key decisions captured, not ready for full-write
note: "Sweeper. Runs from the hub. Reconciles git worktrees, Home.md markers, and `<WIKI_PATH>/active/<slug>/` directories based on each task's `status.md phase:`. Removes artefacts for done/abandoned tasks; resets abandoned tasks to unclaimed in Home.md; leaves live-in-progress state untouched."
```

## Purpose

Bring the three places task-state lives into a consistent state:
- **Hub git worktrees** (`git worktree list`).
- **Home.md markers** (unclaimed, `[s]`, `[active]`, `[done]`).
- **Wiki `active/<slug>/` directories** (with their `status.md phase:`).

Actions are driven by `status.md phase:`, not by Home.md markers. For `phase: done`, clean up any residue. For `phase: abandoned`, clean up + reset Home.md marker to unclaimed so the task can be re-claimed. For live phases, leave everything alone. Report mismatches (orphan worktrees, orphan active dirs without Home.md entries, etc.) without auto-fixing.

## Decisions

- **Runs from the hub**, never from a worktree. Refuses to run if cwd is a worktree — prevents self-deletion class of bugs.
- **Source of truth**: `<WIKI_PATH>/active/<slug>/status.md` → `phase:` field. Home.md markers are a derived summary, not the input to cleanup decisions.
- **Inputs**:
  - `<WIKI_PATH>/active/*` → set of active-dir slugs + their `status.md phase:`.
  - `git worktree list --porcelain` → set of existing worktrees.
  - `<WIKI_PATH>/Home.md` → `{slug: marker}` (for reconciling markers after cleanup; not for deciding action).
- **Actions by status.md phase**:
  - `phase: done` — mill-merge should already have removed worktree + branch + active/<slug>/ and set Home.md to `[done]`. If any residual artefact exists, remove it. Home.md marker untouched (stays `[done]`).
  - `phase: abandoned` — set by mill-abandon. Remove worktree + branch + active/<slug>/. Reset Home.md marker from `[active]` to **unclaimed** (no marker) so the task re-enters the backlog. No `[abandoned]` marker is written — v2 does not use one.
  - Any live phase (`discussing`, `discussed`, `planning`, `planned`, `implementing`, `reviewing`, `fixing`, `blocked`) — leave alone. Blocked is investigated, not cleaned up.
- **Orphan handling** (no action, just report):
  - Worktree exists but no matching `active/<slug>/` → report as orphan worktree.
  - Home.md `[active]` entry but no matching `active/<slug>/` → report.
  - `active/<slug>/` without a Home.md entry → report.
- **Dry-run by default**: print what it would do. `--apply` (or `-y`) actually performs the removal.
- **Wiki writes batched**: all `active/<slug>/` deletions + any Home.md marker resets go in one `_wiki.write_commit_push` commit (`chore: cleanup — <N> done, <M> abandoned`).
- **Junction removal**: when removing a worktree, iterate the wiki config's `junctions:` block and drop each junction the worktree owns. Uses the same `_junction.resolve_target` + `_junction.remove` machinery as mill-setup/mill-spawn.

## Flow

1. Assert cwd is the hub (not a worktree).
2. `wiki.sync_pull(<WIKI_PATH>)`.
3. Enumerate slugs under `<WIKI_PATH>/active/*` and read each `status.md phase:`.
4. Enumerate git worktrees and Home.md markers.
5. Build an action plan per slug:
   - `phase: done` + residual artefact → remove worktree + branch + active/<slug>/ (Home.md stays `[done]`).
   - `phase: abandoned` → remove worktree + branch + active/<slug>/ + reset Home.md marker to unclaimed.
   - Live phase → no action.
   - Orphans (worktree without active/, Home.md [active] without active/, active/ without Home.md) → report, no action.
6. Print the plan. If `--apply` not given, stop.
7. On `--apply`:
   - For each worktree to remove: `git worktree remove --force <path>` + `git branch -d <branch>`.
   - Remove any junctions the worktree owns (iterate `junctions:`).
   - For each active-dir to delete: `rm -rf <WIKI_PATH>/active/<slug>/` queued for the batched wiki commit.
   - For each Home.md marker reset: queue the `[active]` → unclaimed edit.
   - `_wiki.write_commit_push` all wiki changes in one commit.
   - Regenerate sidebar.
8. Report counts: `<N>` worktrees removed, `<M>` active dirs deleted, `<R>` Home.md markers reset, `<P>` orphans reported.

## Backend

**New:**
- `mill-cleanup.py` — CLI entrypoint.
- `_worktree.py` — needs `list()` and `remove(path)` (planned in mill-spawn).
- `_tasks_md.py` — parse Home.md to `{slug: marker}` (planned).

**Reused:**
- `_wiki.py`, `_junction.py`, `_sidebar.py`.

## Out of scope vs v1

- No deep filesystem-lock diagnostics; if `git worktree remove` fails, surface stderr and move on. (v1 had `handle.exe`/`lsof` hints; those can come back as a `--diagnose` option later if needed.)
- No archive-to-`archive/<slug>/`; active dirs are deleted, not moved.

## Open design points

- **`--force` vs `--apply`**: bikeshed. `--apply` reads more clearly as "I mean it".
- **Batched vs per-slug commit**: batched is simpler; revisit if the commit message should list slugs explicitly.
- **Windows worktree lock workarounds**: not addressed at v2.0. Users close the directory and re-run.
