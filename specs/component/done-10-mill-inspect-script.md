# mill-inspect (script)

```yaml
type: script
layer: 04
v1_ref: plugins/mill/skills/mill-inspect/
status: done — merged to main 2026-04-24 (branch impl/10-mill-inspect-script)
note: "Deep read of EVERY active task's status.md. Structured dump beyond what mill-status shows. Read-only."
```

**Implementation notes:** Added `read_full` to `_status.py` as a new sibling alongside `read_status`, returning the full yaml dict and timeline list without the lossy summary layer. `mill-inspect.py` reuses `_worktree.list_worktrees`, `_tasks_md.parse`, and `_paths.resolve_wiki_path` — no new path helpers needed. The `--since` phase order is defined locally as a module-level tuple; `[WARN]` prefix used throughout for cp1252 safety. JSON schema is stable as specified in decisions.

## Purpose

When `mill-status` says "something's off", `mill-inspect` is where you look for detail. It dumps the full `status.md` YAML block plus the complete Timeline for every `<WIKI_PATH>/active/<slug>/` — grouped by slug, verbosely, machine-readable if asked.

## Decisions

- **All active tasks by default**. No slug argument required. `mill-inspect <slug>` narrows to one task for focus.
- **Read-only**. No wiki writes, no network calls.
- **Per-task output** (for each active slug, in alphabetical order):
  - A heading line `## <slug>` for grep-ability.
  - Full YAML block from `status.md` (including `batches:` list when mill-go has populated it).
  - Full Timeline (all lines, not just the last) — dumped unconditionally, no `--full` flag.
  - If a worktree exists for the slug on this machine: `worktree: <path>`.
  - If Home.md marker is not `[active]`: highlight it with `[WARN]` prefix (e.g. `[WARN] home_marker: done`) — cp1252-safe, no unicode.
- **Output formats**:
  - Default: human-readable markdown-ish dump.
  - `--json`: structured JSON suitable for piping into `jq`.
- **`--json` schema** (stable; downstream tooling may rely on it):
  ```
  {
    "<slug>": {
      "status": { ...all yaml-block fields... },
      "timeline": ["<phase>  <timestamp>", ...],
      "worktree": "<path> or null",
      "home_marker": "<phase string or 'unclaimed'>"
    }
  }
  ```
- **`--since <phase>`** (optional filter): show only tasks whose current phase is at or later than `<phase>` in the canonical phase order. Order defined locally in `mill-inspect.py`:
  `discussing → discussed → planning → planned → implementing → reviewing → fixing → done → abandoned → blocked`
- **Exit code when no active tasks**: exit 0, print `(no active tasks)`. Non-zero exit is reserved for environment/validation errors.
- **Warning format**: `[WARN]` (ASCII only — Windows cp1252-safe). No `⚠` unicode.
- **No wiki sync**: same rule as mill-status. If the user wants fresh data they run `git -C <WIKI_PATH> pull` first.
- **Timestamp invariant**: read-only; no timestamps generated.

## Backend

**New:**
- `mill-inspect.py` — CLI entrypoint.
- `_status.read_full(status_path) -> dict` — new sibling alongside `read_status`. Returns `{"yaml": {<all-yaml-block-keys>}, "timeline": [<raw-line-strings>]}`. Does NOT call `read_status` internally — parses the same blocks directly to avoid the lossy summary layer.

**Reused:**
- `_paths.resolve_wiki_path(git_toplevel)`, `_paths.resolve_git_root()`.
- `_tasks_md.parse(text)` — Home.md marker lookup.
- `_worktree.list_worktrees(cwd)` — worktree path column.

**Not used:**
- `_wiki.py` — no wiki writes or lock needed.

## Flow

1. `resolve_git_root()` → git_toplevel.
2. `resolve_wiki_path(git_toplevel)` → wiki_path.
3. List `<wiki_path>/active/*` directories → slugs (sorted).
4. If slug argument given, filter to that one (exit 1 if absent).
5. Read `<wiki_path>/Home.md` → `_tasks_md.parse()` → marker map.
6. `list_worktrees(git_toplevel)` → branch→path map.
7. For each slug: `_status.read_full(status_md_path)` → yaml dict + timeline list.
8. Match worktree by branch pattern `impl/<slug>` or `<slug>`.
9. Apply `--since` filter if given.
10. Render: markdown (default) or JSON (`--json`).

## Out of scope

- No editing. `mill-inspect` never writes.
- No aggregation across machines. Only looks at the wiki on this machine.
- No syntax highlighting / color. Plain output is pipe-friendly.
