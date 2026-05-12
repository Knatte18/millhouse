# Plan: (A) — Small infra fixes batch 7

```yaml
task: (A) — Small infra fixes batch 7
slug: mill-misc-fixes-7
approved: false
started: '20260512-171644'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: wiki-health-check
    file: 01-wiki-health-check.md
    depends-on: []
    verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-wiki.py" && PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
  - number: 2
    name: setup-junction-idempotency
    file: 02-setup-junction-idempotency.md
    depends-on: []
    verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-setup-hub-links.py" && PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
  - number: 3
    name: status-blocked-reason-cleanup
    file: 03-status-blocked-reason-cleanup.md
    depends-on: []
    verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-status.py" && PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: typed exceptions for library helpers

- **Decision:** New library helpers (`_wiki.health_check`, `_junction.points_to`) raise typed exception classes from their owning module on failure. `_wiki.WikiHealthError` is a new class added to `_wiki.py` alongside the existing `WikiSetupError`, `WikiPushError`, `LockBusy`. Library code never calls `sys.exit` directly; CLI / SKILL.md callers translate the typed exception into the appropriate `SystemExit` / non-zero shell exit.
- **Rationale:** Matches the existing `_wiki.py` convention (line 130–152) and project convention from `mill:linting`. Typed exceptions give the orchestrator a stable interface to catch and surface clean error messages without parsing stderr.
- **Applies to:** all batches

### Decision: unit tests use tempfile fixtures, no real LLM/git/wiki

- **Decision:** All new unit tests use `tempfile.TemporaryDirectory()` for filesystem fixtures and follow the existing in-file `main()` runner pattern (see `test-wiki.py:41` and `test-setup-hub-links.py:574`). No pytest; no real `git` calls (mocked via `patch.object(_subprocess_util, "run", ...)` where needed); no real wiki clone. Tests must be runnable via `python <test-file>.py` and via `python plugins/mill/unit_tests/run-all.py`.
- **Rationale:** Project-wide convention; the runner at `plugins/mill/unit_tests/run-all.py` discovers any `test-*.py` and shells out to it as a subprocess. Tests that require external state break that contract.
- **Applies to:** all batches

### Decision: idempotency mirrors existing patterns

- **Decision:** Where idempotency is added (`_setup.create_hub_links` junctions loop; `_status.append_phase`'s `blocked_reason:` auto-clear), the implementation mirrors an already-present pattern in the same file. The hardlinks block of `_setup.create_hub_links` (lines 110–152) is the model for the junctions block. `_status.set_blocked`'s YAML-row insert/rewrite logic (lines 244–258) is the model for the new YAML-row delete logic inside `append_phase`.
- **Rationale:** Discussion D2 and D3. Keeping the same-file convention minimises reviewer surface and makes the change pattern-grep-friendly.
- **Applies to:** batches 2 and 3

### Decision: per-card commits via the git-commit skill

- **Decision:** Each card's `Commit:` line is the message the implementer passes to the `git-commit` skill. The implementer never invokes `git commit` directly. The `git-commit` skill runs lint and `codeguide-update` per commit, per the existing mill-go Principles ("Commits go through `git-commit`").
- **Rationale:** Existing mill-go SKILL.md line 313; project-wide standard.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_junction.py`
- `plugins/mill/scripts/_setup.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_wiki.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-setup-hub-links.py`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-wiki.py`
