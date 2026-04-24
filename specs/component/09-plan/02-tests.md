# Batch 02 — tests

```yaml
batch: 02-tests
state: pending
```

## Scope

Unit tests for `mill-abandon.py` logic (in-memory/tempfile, no real git, no real LLM) and an integration test (real git fixture in `.scratch/`).

## Cards

### Card 2.1 — unit_tests/test-abandon.py

Reads:
- `plugins/mill/unit_tests/test-status.py` — pattern reference for `_status` unit tests
- `plugins/mill/unit_tests/test-active.py` — pattern reference for `_active` unit tests
- `plugins/mill/unit_tests/test-builder-lock.py` — pattern for builder-lock stubs
- `plugins/mill/scripts/mill-abandon.py` — import the logic under test

Creates:
- `plugins/mill/unit_tests/test-abandon.py`

Requirements:
- Use `tempfile.TemporaryDirectory` for all fixtures.
- Cover: (a) happy path (abandon from worktree, force flag), (b) hub check fails (no `active.slug.md`), (c) phase already `abandoned` → refuse, (d) phase `done` → refuse, (e) non-stale builder lock → refuse, (f) stale builder lock → proceed, (g) missing status.md → refuse.
- No subprocess calls to `mill-abandon.py` — import and call logic functions directly if the script is structured to allow it. If the script is a pure `if __name__ == "__main__":` monolith, test via subprocess with a controlled tempdir.
- Tests discovered by `run-all.py`'s `glob("test-*.py")` — no manual registration needed.

Commit: `test(09): unit tests for mill-abandon`

### Card 2.2 — integration_tests/test-abandon.py

Reads:
- `plugins/mill/integration_tests/test-cleanup.py` — fixture setup pattern (git clone + worktree)
- `plugins/mill/integration_tests/test-status.py` — pattern for running mill-status in fixture
- `plugins/mill/scripts/mill-abandon.py` — the script under test

Creates:
- `plugins/mill/integration_tests/test-abandon.py`

Requirements:
- Fixture: real bare git repo + wiki clone in `.scratch/test-abandon-<id>/`.
- Scenario A (happy path): spawn a task, run `mill-abandon.py --force` from the worktree, verify `status.md` phase is `abandoned` and timeline has an `abandoned` row.
- Scenario B (hub guard): run `mill-abandon.py --force` from the hub root → expect non-zero exit.
- Scenario C (already-abandoned guard): run `mill-abandon.py --force` twice → second invocation exits non-zero.
- Fixture cleanup: remove `.scratch/test-abandon-<id>/` on teardown.
- Use `subprocess.run` to invoke `mill-abandon.py` as a subprocess (real script execution).

Commit: `test(09): integration test for mill-abandon`
