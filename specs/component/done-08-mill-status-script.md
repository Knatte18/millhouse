# mill-status (script)

```yaml
type: script
layer: 04
v1_ref: plugins/mill/skills/mill-status/
status: done
note: "Read-only snapshot. Prints a one-line-per-task table of every active task on this machine — phase, current batch, last timeline entry, whether the worktree exists, whether Home.md marker agrees. No wiki writes."
```

## Purpose

Give the user a quick glance at all active tasks: what phase each is in, whether anything is blocked, whether state is consistent across Home.md + worktree + `active/<slug>/`.

## Decisions

- **Runs anywhere** — hub or worktree. No side-effects, no wiki writes.
- **Sources** (read-only):
  - `<WIKI_PATH>/active/*` — each slug's `status.md`.
  - `<WIKI_PATH>/Home.md` — marker per slug.
  - `git worktree list --porcelain` — presence of a local worktree for the slug.
- **Output columns** (one line per task):
  - `slug`
  - `title` (from status.md `task:` field; truncated to 40 chars)
  - `phase` (from status.md YAML)
  - `marker` (Home.md: unclaimed / [s] / [active] / [done] / missing — no `[abandoned]` in v2; abandoned tasks revert to unclaimed via mill-cleanup)
  - `worktree` (path if present, `-` if not on this machine)
  - `current_batch` (if implementing/reviewing/fixing)
  - `last_timeline_entry` (most recent Timeline line from status.md; truncated to 40 chars)
  - `blocked_reason` (only when phase is `blocked`)
- **Width-stable table**: columns sized to the longest value in each column. Plain text with color. `--json` flag for machine-readable output (no truncation, no color).
- **Color**: auto-detect TTY (`sys.stdout.isatty()`); color on when stdout is a TTY, off otherwise. `--no-color` flag disables explicitly. No `--color` flag needed — the auto-detect default is the right behavior for piping.
- **Sort**: default alphabetical by slug. `--sort phase` flag for phase-first order: `blocked` → `implementing` → `reviewing` → `fixing` → `planning` → `discussed` → `discussing` → anything else alphabetical at the end.
- **Truncation**: `title` and `last_timeline_entry` columns truncated to 40 characters with `…` suffix. Other columns are short enough that truncation is not needed. `--json` output is never truncated.
- **Backlog tasks**: slugs present only in Home.md (no active-dir, no worktree) are included in the table with `phase=None` rendered as `—`, no inconsistency flags.
- **Inconsistency flags**: mark slugs where state is off — `[active]` in Home.md but no worktree → `WT?`; `active/<slug>/` exists but no Home.md entry → `HM?`. One-character flags appended to the `marker` column keep the row short.
- **No network**: does NOT call `wiki.sync_pull`. If the wiki is stale, the user knows; forcing a pull for a read-only snapshot is heavy.
- **`read_status` helper**: `_status.py` gains a `read_status(status_path) -> dict` function returning `{phase, task, current_batch, last_timeline_entry, blocked_reason}`. Unit-tested in `test-status.py`.

## Flow

1. Resolve `<WIKI_PATH>` via `_paths.resolve_wiki_path(git_toplevel)`.
2. Parse Home.md → `{slug: marker}`.
3. List `<WIKI_PATH>/active/*` directories.
4. For each active-dir slug, call `_status.read_status` to get YAML block fields + last Timeline line.
5. List `git worktree list --porcelain` → `{slug: path}` (derive slug from branch).
6. Join all three sets by slug. Compute inconsistency flags.
7. Print table (or JSON if `--json`).

## Backend

**New:**
- `mill-status.py` — CLI entrypoint.

**Extended:**
- `_status.py` — gains `read_status(status_path) -> dict` (returns `{phase, task, current_batch, last_timeline_entry, blocked_reason}`). Unit test extended in `test-status.py`.

**Reused:**
- `_paths.py` (wiki path resolution), `_tasks_md.py` (Home.md marker parsing), `_worktree.py` (`list_worktrees`), `_subprocess_util.run`.

## Out of scope

- No wiki sync.
- No per-task commit history. That's mill-inspect's job.
- No cross-machine aggregation. Only this machine's worktrees show in the worktree column; the active-dir column reflects the whole wiki.
