# Plan: Unhandled exceptions in mill-go orchestration components should degrade gracefully

```yaml
task: "Unhandled exceptions in mill-go orchestration components should degrade gracefully"
slug: "mill-orchestration-crash-hardening"
approved: true
started: "20260716-110959"
parent: "hanf/linux-port-more"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: psmux-cleanup-crash
    file: 01-psmux-cleanup-crash.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-psmux-driver.py test-llm-claude.py
  - number: 2
    name: wiki-daemon-json-noise
    file: 02-wiki-daemon-json-noise.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-wiki-daemon.py test-wiki-client-retry.py
```

## Shared Decisions

### Decision: Python verify commands must reset PYTHONPATH

- **Decision:** Every `verify:` command in this plan starts with the literal `PYTHONPATH= ` (empty value, single space) prefix.
- **Rationale:** without the reset, the test subprocess inherits the mill cache's `PYTHONPATH` and loads stale cache-installed modules instead of the worktree copies this task edits, silently testing the wrong code.
- **Applies to:** all batches.

### Decision: Graceful degradation only — no happy-path behavior change

- **Decision:** every fix in this plan changes error/edge-case handling only. The happy path is unchanged: a real `psmux` session under `dispatch: psmux` still gets listed and killed exactly as before; a real, well-formed, correctly-authenticated JSON request to the wiki daemon still gets parsed, dispatched, and answered exactly as before.
- **Rationale:** this task is scoped as crash-hardening (see `_mill/discussion.md` Scope/Out), not a behavior or feature change. Cards must not alter the control flow for the cases that already work correctly today.
- **Applies to:** all batches.

### Decision: Unit tests only — no real git/LLM/psmux processes

- **Decision:** all new/edited tests use `unittest.mock` and stdlib fixtures (tempfile, `MagicMock`) exactly as the existing tests in the same files already do. No card spawns a real `psmux` binary, a real daemon accept loop in a background thread, or a real `claude` CLI invocation.
- **Rationale:** matches `plugins/mill/unit_tests/`'s established convention (see file docstrings: "Uses tempfile dirs; no real TCP sockets or accept loop", "These tests exercise the pure-Python surface... do NOT invoke the live `claude` CLI") and `mill:python-testing`.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_daemon.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_psmux.py`
- `plugins/mill/scripts/wiki/_client.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-psmux-driver.py`
- `plugins/mill/unit_tests/test-wiki-daemon.py`
