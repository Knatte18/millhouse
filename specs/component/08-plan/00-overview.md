# Plan: mill-status script

```yaml
task: mill-status script
slug: 08-mill-status-script
approved: false
started: false
parent: main
root: c:/Code/millhouse/hub
verify: >
  python plugins/mill/unit_tests/run-all.py &&
  python plugins/mill/integration_tests/test-spawn.py &&
  python plugins/mill/integration_tests/test-merge.py &&
  python plugins/mill/integration_tests/test-plan-assets.py &&
  python plugins/mill/integration_tests/test-go-assets.py &&
  python plugins/mill/integration_tests/test-cleanup.py &&
  python plugins/mill/integration_tests/test-status.py
```

## Batch index

| # | Name | Cards | Description |
|---|------|-------|-------------|
| 1 | foundation | 2 | `read_status` helper in `_status.py` + unit tests |
| 2 | cli | 3 | `mill-status.py` data assembly, table rendering, integration test |

## Shared decisions

- **Wiki path**: `_paths.resolve_wiki_path(git_toplevel)` — never the junction.
- **Color**: `sys.stdout.isatty()` auto-detect; `--no-color` disables. No color in `--json` mode. ANSI codes never count toward column width.
- **Sort**: alphabetical default; `--sort phase` flag → `blocked(0) → implementing(1) → reviewing(2) → fixing(3) → planning(4) → discussed(5) → discussing(6) → (tail group)`; tail-group sort key is `("z", phase or "")` — `None` → `("z", "")` < `("z", "foo")` so `None` sorts before any alphabetical unknown phase.
- **Truncation**: `TITLE` and `LAST EVENT` columns truncated to 40 chars with `…`. All other columns left untruncated. `--json` never truncates.
- **`read_status` return shape**: `{"phase": str, "task": str|None, "current_batch": str|None, "last_timeline_entry": str|None, "blocked_reason": str|None}`. Missing `phase:` → `ValueError`. Missing `task:` → `None`. `current_batch` derived from `read_batches()` (first batch with state in `{running, reviewing, fixing, blocked}`); `ValueError` from `read_batches` propagates. Only called when an active-dir exists — never for backlog-only tasks.
- **Marker mapping**: `Task.phase is None` → display as `"unclaimed"`. `"s"`, `"active"`, `"done"`, `"abandoned"` pass through verbatim. Slugs with no Home.md entry → `"missing"`.
- **Backlog tasks**: slugs present only in Home.md (no active-dir, no worktree) → `phase=None`, rendered as `—`; no `WT?` or `HM?` flags.
- **Inconsistency flags**: `WT?` when marker is `"active"` and no local worktree; `HM?` when active-dir exists but no Home.md entry. Flag appended to MARKER cell with a space; MARKER column width accounts for it.
- **Worktree → slug**: skip entries where `branch is None` or `not branch.startswith("impl/")`. Slug = `branch[len("impl/"):]`. This excludes the main worktree (branch `main`).
- **Home.md parse**: call `_tasks_md.parse(text)` then build dict: `{t.slug: t for t in result}`.

## All Files Touched

- `plugins/mill/scripts/_status.py` — add `read_status`
- `plugins/mill/unit_tests/test-status.py` — extend with `read_status` tests
- `plugins/mill/scripts/mill-status.py` — new CLI entrypoint
- `plugins/mill/integration_tests/test-status.py` — new integration test
