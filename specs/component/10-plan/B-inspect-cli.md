# Batch B — inspect-cli

```yaml
batch: B
name: inspect-cli
commit: "feat(mill-inspect): add mill-inspect CLI script"
```

## Scope

Implement `mill-inspect.py` — the CLI entrypoint for deep-reading all active tasks.

## Cards

### B1 — `mill-inspect.py` scaffold + core loop

**Creates:** `plugins/mill/scripts/mill-inspect.py`

**Reads:** `plugins/mill/scripts/_status.py`, `plugins/mill/scripts/_paths.py`, `plugins/mill/scripts/_tasks_md.py`, `plugins/mill/scripts/_worktree.py`

- `argparse` CLI: positional `slug` (optional, nargs=`?`), `--json`, `--since <phase>`.
- Phase order tuple at module level (ASCII-only names):
  `PHASE_ORDER = ("discussing", "discussed", "planning", "planned", "implementing", "reviewing", "fixing", "done", "abandoned", "blocked")`
- Flow:
  1. `resolve_git_root()` → git_toplevel.
  2. `resolve_wiki_path(git_toplevel)` → wiki_path.
  3. `active_dir = wiki_path / "active"` → list slug dirs, sort.
  4. If slug arg: filter to that one; exit 1 with message if absent.
  5. If no slugs after filter: print `(no active tasks)`; exit 0.
  6. Read `wiki_path / "Home.md"` → `_tasks_md.parse()` → build `{slug: phase_or_unclaimed}` map.
  7. `list_worktrees(git_toplevel)` → build `{branch: path}` map.
  8. For each slug: `read_full(active_dir / slug / "status.md")` → collect record.
  9. Apply `--since` filter: skip slugs whose phase index < `--since` phase index (unknown phases treated as index 0).
  10. Render (see B2).

**Requirements:**
- Worktree match: check branch `impl/<slug>` then `<slug>` in the branch→path map. `None` if no match.
- Home.md marker: use `.phase` from `_tasks_md.Task`; if slug absent from parse result, marker is `"unclaimed"`.
- `[WARN]` prefix on marker if marker != `"active"`.

**Commit:** `feat(mill-inspect): add mill-inspect CLI script`

---

### B2 — render functions (markdown + JSON)

**Modifies:** `plugins/mill/scripts/mill-inspect.py`

- `render_markdown(records: list[dict]) -> str`:
  - Per slug: `## <slug>`, yaml block content (key: value lines from `record["yaml"]`), timeline lines, worktree line, home_marker line (with `[WARN]` if not active).
- `render_json(records: list[dict]) -> str`:
  - Build dict keyed by slug, each value: `{"status": yaml_dict, "timeline": timeline_list, "worktree": wt_or_null, "home_marker": marker_str}`.
  - `json.dumps(..., indent=2)`.
- Wire into main: `--json` calls `render_json`, default calls `render_markdown`.

**Requirements:**
- Output is plain ASCII where possible. Yaml values are printed verbatim (user-controlled content); that's fine.
- `render_markdown` must be pipe-friendly: no trailing ANSI codes, no color.
- `print(render_...(records))` to stdout; errors to stderr.

**Commit:** same as B1 (single commit for B).
