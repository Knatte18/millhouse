# Plan: spec 10 — mill-inspect script

```yaml
task: mill-inspect script (end-to-end)
slug: 10-mill-inspect-script
approved: false
started: 2026-04-24
parent: main
root: c:/Code/millhouse/hub
verify: >
  python plugins/mill/unit_tests/run-all.py &&
  python plugins/mill/integration_tests/test-spawn.py &&
  python plugins/mill/integration_tests/test-merge.py &&
  python plugins/mill/integration_tests/test-plan-assets.py &&
  python plugins/mill/integration_tests/test-go-assets.py &&
  python plugins/mill/integration_tests/test-cleanup.py &&
  python plugins/mill/integration_tests/test-status.py &&
  python plugins/mill/integration_tests/test-abandon.py &&
  python plugins/mill/integration_tests/test-inspect.py
```

## Batch index

| # | Name | Cards | Description |
|---|------|-------|-------------|
| A | status-read-full | 2 | Add `read_full` to `_status.py` + unit test |
| B | inspect-cli | 2 | `mill-inspect.py` CLI entrypoint |
| C | integration-test | 1 | `test-inspect.py` integration test |

## Shared decisions

- `read_full` is a new sibling function, not an extension of `read_status`. Returns `{"yaml": dict, "timeline": list[str]}`.
- Timeline dumped unconditionally — no `--full` flag.
- JSON schema: `{ "<slug>": { "status": {...yaml...}, "timeline": [...], "worktree": null|str, "home_marker": str } }`.
- Exit 0 when no active tasks, print `(no active tasks)`.
- Warning format: `[WARN]` (ASCII, cp1252-safe).
- Phase order for `--since`: `discussing discussed planning planned implementing reviewing fixing done abandoned blocked`.
- Worktree match: branch `impl/<slug>` or `<slug>` (same convention as mill-status).
- Wiki path via `_paths.resolve_wiki_path(git_toplevel)`, never junction.

## All files touched

| File | A | B | C |
|------|---|---|---|
| `plugins/mill/scripts/_status.py` | M | | |
| `plugins/mill/unit_tests/test-status.py` | M | | |
| `plugins/mill/scripts/mill-inspect.py` | | C | |
| `plugins/mill/integration_tests/test-inspect.py` | | | C |
