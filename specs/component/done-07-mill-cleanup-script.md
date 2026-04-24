# mill-cleanup (script)

```yaml
type: script
layer: 04
v1_ref: plugins/mill/skills/mill-cleanup/
status: done — merged to main 2026-04-24 (branch impl/07-mill-cleanup-script)
note: "Sweeper. Runs from the hub. Reconciles git worktrees, Home.md markers, and `<WIKI_PATH>/active/<slug>/` directories based on each task's `status.md phase:`. Removes artefacts for done/abandoned tasks; resets abandoned tasks to unclaimed in Home.md; leaves live-in-progress state untouched."
```

**Implementation notes:** `plugins/mill/scripts/_worktree.py` gained `list_worktrees()` (parses `git worktree list --porcelain`) and `remove(path, force=True)`. `plugins/mill/scripts/mill-cleanup.py` is the CLI: pure `build_plan()` (easy to unit-test — covers all phase × orphan combinations) separated from impure `apply_plan()`. Dry-run by default; `--apply` executes: iterate wiki `junctions:` → `_junction.remove` → `git worktree remove --force` → `git branch -D`, then one batched `_wiki.write_commit_push` for active-dir deletions + Home.md marker resets, plus sidebar regen. Wiki path via `_paths.resolve_wiki_path` per spec 14. No SKILL.md wrapper — mill-cleanup is a maintenance CLI, not a Claude-facing skill. Full verify (unit tests + 5 integration tests including new `test-cleanup.py`) passes.

## Purpose

Bring the three places task-state lives into a consistent state:
- **Hub git worktrees** (`git worktree list`).
- **Home.md markers** (unclaimed, `[s]`, `[active]`, `[done]`).
- **Wiki `active/<slug>/` directories** (with their `status.md phase:`).

Actions are driven by `status.md phase:`, not by Home.md markers. For `phase: done`, clean up any residue. For `phase: abandoned`, clean up + reset Home.md marker to unclaimed so the task can be re-claimed. For live phases, leave everything alone. Report mismatches (orphan worktrees, orphan active dirs without Home.md entries, etc.) without auto-fixing.

## Decisions (locked)

- **Runs from the hub**, never from a worktree. Refuses to run if cwd is a worktree — prevents self-deletion class of bugs.
- **Source of truth**: `<WIKI_PATH>/active/<slug>/status.md` → `phase:` field. Home.md markers are a derived summary, not the input to cleanup decisions.
- **Inputs**:
  - `<WIKI_PATH>/active/*` → set of active-dir slugs + their `status.md phase:`.
  - `git worktree list --porcelain` → set of existing worktrees.
  - `<WIKI_PATH>/Home.md` → `{slug: marker}` (for reconciling markers after cleanup; not for deciding action).
- **Wiki path resolution**: uses `_paths.resolve_wiki_path(git_root)` per spec 14. Never touches the `.millhouse/wiki` junction.
- **Actions by status.md phase**:
  - `phase: done` — mill-merge should already have removed worktree + branch + active/<slug>/ and set Home.md to `[done]`. If any residual artefact exists, remove it. Home.md marker untouched (stays `[done]`).
  - `phase: abandoned` — set by mill-abandon. Remove worktree + branch + active/<slug>/. Reset Home.md marker from `[active]` to **unclaimed** (no marker) so the task re-enters the backlog. No `[abandoned]` marker is written — v2 does not use one.
  - Any live phase (`discussing`, `discussed`, `planning`, `planned`, `implementing`, `reviewing`, `fixing`, `blocked`) — leave alone. Blocked is investigated, not cleaned up.
- **Branch deletion**: always `git branch -D <branch>`. Abandoned branches have un-merged commits by definition; `-d` would refuse them. Done branches should already be merged, but `-D` is safe since cleanup only runs after `mill-merge`/`mill-abandon` has confirmed the phase. Each deletion is logged on stdout so the user sees what went.
- **Malformed `status.md` handling**: if `active/<slug>/status.md` is missing or `phase:` is unreadable, report as `"<slug> — status.md unreadable, skipping (inspect manually)"` and take **no action** on that slug. Cleanup never deletes when the source data is unreadable.
- **Home.md marker reset — `[active]` only**: on `phase: abandoned`, strip the `[active]` marker only. If the marker is something else (`[s]`, `[done]`, unclaimed) alongside `phase: abandoned`, report the inconsistency and leave the marker untouched. User investigates manually.
- **Orphan handling** (report only, no action):
  - Worktree exists but no matching `active/<slug>/` → orphan worktree.
  - Home.md `[active]` entry but no matching `active/<slug>/` → orphan marker.
  - `active/<slug>/` without a Home.md entry → orphan active dir.
- **Dry-run by default**: print what it would do. `--apply` actually performs the removal.
- **Wiki writes batched**: all `active/<slug>/` deletions + any Home.md marker resets go in one `_wiki.write_commit_push` commit (`chore: cleanup — <N> done, <M> abandoned`).
- **Junction removal before worktree remove**: iterate the wiki config's `junctions:` block and call `_junction.remove` for each junction the worktree owns. Belt-and-suspenders — `git worktree remove --force` MAY handle NTFS reparse points on Windows cleanly, but the behaviour is not verified and the existing `_junction.remove` helper is already tested. Cheap to do, safer with.

## Flow

1. Assert cwd is the hub (not a worktree).
2. `_wiki.sync_pull(<WIKI_PATH>)`.
3. Enumerate slugs under `<WIKI_PATH>/active/*` and read each `status.md phase:`. Collect malformed/unreadable entries separately.
4. Enumerate git worktrees and Home.md markers.
5. Build an action plan per slug:
   - `phase: done` + residual artefact → remove worktree + branch (`-D`) + active/<slug>/ (Home.md stays `[done]`).
   - `phase: abandoned` + marker is `[active]` → remove worktree + branch (`-D`) + active/<slug>/ + reset marker to unclaimed.
   - `phase: abandoned` + marker is NOT `[active]` → report inconsistency, no action.
   - Live phase → no action.
   - Orphans + malformed status.md → report, no action.
6. Print the plan. If `--apply` not given, stop.
7. On `--apply`:
   - For each worktree to remove: iterate wiki `junctions:` → `_junction.remove` → then `git worktree remove --force <path>` → `git branch -D <branch>`. Log each step.
   - For each active-dir to delete: `rm -rf <WIKI_PATH>/active/<slug>/` queued for the batched wiki commit.
   - For each Home.md marker reset: queue the `[active]` → unclaimed edit.
   - `_wiki.write_commit_push` all wiki changes in one commit.
   - Regenerate sidebar.
8. Report counts: `<N>` worktrees removed, `<M>` active dirs deleted, `<R>` Home.md markers reset, `<P>` orphans + `<U>` unreadable reported.

## Backend

**New:**
- `plugins/mill/scripts/mill-cleanup.py` — CLI entrypoint.

**Extended:**
- `plugins/mill/scripts/_worktree.py` — adds `list()` returning a list of `{path, branch}` records (parses `git worktree list --porcelain`), and `remove(path, force=True)` wrapping `git worktree remove --force`.

**Reused:**
- `_wiki.py`, `_junction.py`, `_sidebar.py`, `_tasks_md.py` (slug/marker parsing), `_paths.py` (wiki path resolution), `_subprocess_util.py`.

## Out of scope vs v1

- No deep filesystem-lock diagnostics; if `git worktree remove` fails, surface stderr and move on. (v1 had `handle.exe`/`lsof` hints; those can come back as a `--diagnose` option later if needed.)
- No archive-to-`archive/<slug>/`; active dirs are deleted, not moved.
- No Windows worktree-lock workarounds; user closes the directory and re-runs.
- No SKILL.md wrapper decided yet — to be decided during plan-writing (mill-cleanup is a CLI script; a thin SKILL wrapper may or may not add value).
