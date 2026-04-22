# mill-status (script)

```yaml
type: script
layer: 04
v1_ref: plugins/mill/skills/mill-status/
status: partially discussed — key decisions captured, not ready for full-write
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
  - `phase` (from status.md YAML)
  - `marker` (Home.md: unclaimed / [s] / [active] / [done] / missing — no `[abandoned]` in v2; abandoned tasks revert to unclaimed via mill-cleanup)
  - `worktree` (path if present, `-` if not on this machine)
  - `current_batch` (if implementing/reviewing/fixing)
  - `last_timeline_entry` (most recent Timeline line from status.md)
  - `blocked_reason` (only when phase is `blocked`)
- **Width-stable table**: columns sized to the longest value. Plain text; no color by default. `--json` flag for machine-readable output.
- **Inconsistency flags**: mark slugs where state is off — `[active]` in Home.md but no worktree → `WT?`; `active/<slug>/` exists but no Home.md entry → `HM?`. One-character flags appended to the `marker` column keep the row short.
- **No network**: does NOT call `wiki.sync_pull`. If the wiki is stale, the user knows; forcing a pull for a read-only snapshot is heavy.

## Flow

1. Resolve `<WIKI_PATH>` via `_wiki.read_junctions` + `_junction.resolve_target`.
2. Parse Home.md → `{slug: marker}`.
3. List `<WIKI_PATH>/active/*` directories.
4. For each active-dir slug, read its `status.md` YAML block + last Timeline line.
5. List `git worktree list --porcelain` → `{slug: path}` (derive slug from branch).
6. Join all three sets by slug. Compute inconsistency flags.
7. Print table (or JSON if `--json`).

## Backend

**New:**
- `mill-status.py` — CLI entrypoint.
- `_status.py` — `read(status_path) -> dict` (planned in mill-spawn/mill-start) — returns YAML block + last timeline line.
- `_tasks_md.py` — parse Home.md markers (planned).

**Reused:**
- `_wiki.py`, `_junction.py`.
- `_subprocess_util.run` for `git worktree list`.

## Out of scope

- No wiki sync.
- No per-task commit history. That's mill-inspect's job.
- No cross-machine aggregation. Only this machine's worktrees show in the worktree column; the active-dir column reflects the whole wiki.

## Open design points

- **Color**: off by default. `--color` flag to enable? Or detect TTY and default on?
- **Sort order**: alphabetical by slug, or by phase (blocked first, then implementing, etc.)? Alphabetical is predictable; phase-sorted is useful for triage. Default alphabetical, `--sort phase` as option.
- **Truncation**: long `task:` titles or timeline lines — truncate to terminal width or wrap? Truncate with `…`.
