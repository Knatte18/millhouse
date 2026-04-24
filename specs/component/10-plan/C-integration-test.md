# Batch C — integration-test

```yaml
batch: C
name: integration-test
commit: "test(inspect): add test-inspect.py integration test"
```

## Scope

Write `test-inspect.py` — a real-git integration test for `mill-inspect.py`. Uses `.scratch/` fixtures.

## Cards

### C1 — `test-inspect.py`

**Creates:** `plugins/mill/integration_tests/test-inspect.py`

**Reads:** `plugins/mill/integration_tests/test-status.py`, `plugins/mill/integration_tests/test-abandon.py`

- Fixture: real git repo in `.scratch/test-inspect-<id>/`, wiki repo beside it. Two active task dirs in `wiki/active/`: one with a known status.md (phase `implementing`, 2 timeline entries), one with phase `discussing`. `Home.md` has both slugs marked `[active]`.
- `test_inspect_all`: run `mill-inspect.py`, assert both slugs appear in stdout, yaml fields present, timeline lines present.
- `test_inspect_single_slug`: run `mill-inspect.py <slug>`, assert only that slug in stdout.
- `test_inspect_unknown_slug`: run `mill-inspect.py missing-slug`, assert exit code 1.
- `test_inspect_json`: run `mill-inspect.py --json`, parse stdout as JSON, assert schema shape matches spec (both slugs present, `status`/`timeline`/`worktree`/`home_marker` keys).
- `test_inspect_since`: run `mill-inspect.py --since planned`, assert only `implementing` slug present (not `discussing`).
- `test_inspect_no_active`: empty `wiki/active/`, run `mill-inspect.py`, assert `(no active tasks)` in stdout, exit 0.
- `test_inspect_warn_marker`: set one slug's Home.md marker to `done`, run inspect, assert `[WARN]` in stdout for that slug.

**Requirements:**
- Fixture uses `tempfile` or direct `.scratch/` path; cleaned up at test end (or left for debug — match existing test convention).
- Script invoked via `subprocess` with the scripts dir on `PYTHONPATH` (same as other integration tests).
- No real LLM.

**Commit:** `test(inspect): add test-inspect.py integration test`
