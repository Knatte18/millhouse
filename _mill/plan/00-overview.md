# Plan: Isolate verify PYTHONPATH so tests validate worktree code

```yaml
task: Isolate verify PYTHONPATH so tests validate worktree code
slug: wiki-v3-verify-isolation
approved: true
started: 20260525-105607
parent: hanf/wiki-v3-adoption
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: verify-isolation
    file: 01-verify-isolation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
```

## Shared Decisions

### Decision: verify-isolation-prefix-canonical-shape

- **Decision:** Every non-null `verify:` command authored by mill-plan starts with the literal token `PYTHONPATH=` followed by a single space and then the command. Example: `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. The empty value on the same line scopes the env-var reset to that one command only.
- **Rationale:** Implementer/fixer Sonnet agents and `mill-merge-in` execute the verify string verbatim; the prefix is the single source of truth for resetting the inherited cache `PYTHONPATH` that would otherwise leak V2-cache modules into the test process.
- **Applies to:** all batches

### Decision: validator-error-envelope-5-key

- **Decision:** The new `verify-not-isolated` validator check returns the 5-key envelope every other `_plan_validate.py` check uses: `{check, batch, card, path, message}`. `card:` is `None` because the verify field is per-batch, not per-card. `path:` carries the offending verify string so the mill-plan mechanical-fix dispatcher can read and rewrite it. `batch:` is the per-batch file's stem (e.g. `01-verify-isolation`).
- **Rationale:** `_plan_validate.run()` sorts errors via `(e["batch"] or "", e["card"] or 0, e["check"])` (line 855); any check that omits `card` raises `KeyError` at sort time. Conforming also means the existing mill-plan dispatcher needs no schema changes.
- **Applies to:** all batches

### Decision: ascii-stdout-only

- **Decision:** All new and modified `print()` / `_log()` output is ASCII only -- em-dash -> ` -- `, arrow -> ` -> ` per CLAUDE.md.
- **Rationale:** Windows cp1252 stdout crashes on non-ASCII. CLAUDE.md hard rule.
- **Applies to:** all batches

## All Files Touched

- `CLAUDE.md`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/templates/plan-overview.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
