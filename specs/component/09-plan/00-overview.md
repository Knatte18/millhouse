# Plan: mill-abandon script

```yaml
task: mill-abandon script
slug: 09-mill-abandon-script
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
  python plugins/mill/integration_tests/test-abandon.py
```

## Batches

1. `01-script` — implement `mill-abandon.py`
2. `02-tests` — unit tests + integration test

## Shared decisions

- `_status.append_phase` exists and is used as-is; no changes to `_status.py`.
- `_active.read_slug` exists and is used as-is; no changes to `_active.py`.
- Builder-lock guard uses `_builder_lock.read()` + inline stale check via `STALE_WINDOW_SEC`. Do NOT call `_builder_lock._is_stale` — it is module-private. Inline: `age = (now - parse_iso(info.timestamp)).total_seconds(); stale = age > _builder_lock.STALE_WINDOW_SEC` (ValueError on bad timestamp → treat as stale). Non-stale lock → refuse unless `--force`.
- `--force` bypasses both confirmation prompt and builder-lock guard.
- Exit 0 on user-cancel (N at prompt). Exit 1 on environment/validation error.
- Terse stdout: only the final success line (or error). No intermediate step echoes.
- Wiki-lock timeout: 30 s default (same as mill-merge).
- Timestamp format: `datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` — ISO-8601 UTC Z-suffix, consistent with mill-spawn.
- Worktree detection: check `.millhouse/active.slug.md` exists (same pattern as mill-cleanup's inverse hub-check).
- `--reason` deferred.

## All Files Touched

| File | Action |
|---|---|
| `plugins/mill/scripts/mill-abandon.py` | Create |
| `plugins/mill/unit_tests/test-abandon.py` | Create |
| `plugins/mill/integration_tests/test-abandon.py` | Create |
