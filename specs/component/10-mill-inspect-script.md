# mill-inspect (script)

```yaml
type: script
layer: 04
v1_ref: plugins/mill/skills/mill-inspect/
status: partially discussed — key decisions captured, not ready for full-write
note: "Deep read of EVERY active task's status.md. Structured dump beyond what mill-status shows. Read-only."
```

## Purpose

When `mill-status` says "something's off", `mill-inspect` is where you look for detail. It dumps the full `status.md` YAML block plus the complete Timeline for every `<WIKI_PATH>/active/<slug>/` — grouped by slug, verbatim, machine-readable if asked.

## Decisions

- **All active tasks by default**. No slug argument required. `mill-inspect <slug>` narrows to one task for focus.
- **Read-only**. No wiki writes, no network calls.
- **Per-task output** (for each active slug, in alphabetical order):
  - A heading line `## <slug>` for grep-ability.
  - Full YAML block from `status.md` (including `batches:` list when mill-go has populated it).
  - Full Timeline (all lines, not just the last).
  - If a worktree exists for the slug on this machine: `worktree: <path>`.
  - If Home.md marker is not `[active]`: highlight it (e.g. `⚠ home_marker: [done]` or `⚠ home_marker: unclaimed`) — useful for spotting Home.md vs status.md drift.
- **Output formats**:
  - Default: human-readable markdown-ish dump.
  - `--json`: structured JSON suitable for piping into `jq`.
- **`--since <phase>`** (optional filter): show only tasks whose current phase is at or later than `<phase>` in the phase order (e.g. `--since implementing` hides discussion/planning tasks).
- **No wiki sync**: same rule as mill-status. If the user wants fresh data they run `git -C <WIKI_PATH> pull` first.

## Flow

1. Resolve `<WIKI_PATH>`.
2. List `<WIKI_PATH>/active/*` directories → set of slugs.
3. If a slug argument is given, filter to just that one (error if absent).
4. For each slug:
   a. Read `status.md`. Parse YAML block + Timeline section.
   b. Check Home.md marker for the slug.
   c. Check `git worktree list` for a matching branch.
5. Render: markdown (default) or JSON (`--json`).

## Backend

**New:**
- `mill-inspect.py` — CLI entrypoint.
- `_status.read_full(status_path) -> dict` — returns YAML + Timeline list. Minor extension to the planned `_status.py`.

**Reused:**
- `_wiki.py`, `_junction.py`, `_tasks_md.py` (planned), `_subprocess_util.run`.

## Out of scope

- No editing. `mill-inspect` never writes.
- No aggregation across machines. Only looks at the wiki on this machine.
- No syntax highlighting / color. Plain output is pipe-friendly.

## Open design points

- **Where "full Timeline" is long**: collapse to last N lines by default with `--full` to show all? Usually Timelines are short (few phase transitions) — just dump everything.
- **`--json` schema stability**: declare the shape in the spec so downstream tooling can rely on it. First-pass shape: `{slug: {status: {...}, timeline: [...], worktree: "...", home_marker: "[active]"}}`.
