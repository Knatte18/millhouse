# Plan: Make implementer model configurable via config.yaml

```yaml
task: Make implementer model configurable via config.yaml
slug: implementer-model-config
approved: false
started: 20260515-090924
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: core-modules
    file: 01-core-modules.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 2
    name: wiki-and-template
    file: 02-wiki-and-template.md
    depends-on: []
    verify: null

  - number: 3
    name: cli-scripts
    file: 03-cli-scripts.md
    depends-on: [1]
    verify: null

  - number: 4
    name: unit-tests
    file: 04-unit-tests.md
    depends-on: [3]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: Named registry entries, not raw model IDs

- **Decision:** The implementer model is specified as a named entry (e.g. `sonnethigh`) that resolves in `agents.yaml`, not a raw model-ID string. Effort is implicit in the named entry.
- **Rationale:** Consistent with reviewer config; model version pinning happens once in `agents.yaml`.
- **Applies to:** all batches.

### Decision: `_reviewers.py` loads `agents.yaml` with backward-compat fallback

- **Decision:** `_reviewers.load()` tries `agents.yaml` first; if absent, falls back to `reviewers.yaml`. Error message always cites `agents.yaml` as the canonical name.
- **Rationale:** Existing external hubs with `reviewers.yaml` keep working after `update-plugins`.
- **Applies to:** batch 1 (code), batch 2 (wiki rename), batch 4 (backward-compat test).

### Decision: `_implementer_claude.py` has required kwargs, no defaults for `model`/`effort`

- **Decision:** Both `model: str` and `effort: str | None` are required keyword-only parameters on `run()`. No defaults, so callers can't silently fall back to a stale value.
- **Rationale:** Prevents accidental use of a hardcoded model if a caller forgets to thread through the config value.
- **Applies to:** batch 1 (module), batch 3 (CLI callers), batch 4 (test mocks).

### Decision: `_implementer_sonnet.py` deleted in batch 3 after all callers updated

- **Decision:** `_implementer_sonnet.py` is deleted in batch 3, after all three CLI scripts are migrated to `_implementer_claude`. Unit tests still reference the old name until batch 4; batch 3 has `verify: null` for this reason.
- **Rationale:** Keeps the delete co-located with the migration that makes it safe.
- **Applies to:** batch 3 (delete), batch 4 (test mock targets updated).

### Decision: Wiki operations use `_wiki.wiki_lock` + `git -C wiki_path`

- **Decision:** All wiki file mutations in batch 2 happen inside a `with _wiki.wiki_lock(wiki_path, slug):` block. Git operations use `git -C wiki_path` subprocess calls (never `cd wiki_path`).
- **Rationale:** Required by CLAUDE.md wiki access conventions; prevents lock races.
- **Applies to:** batch 2.

## All Files Touched

- `plugins/mill/scripts/_implementer_claude.py`
- `plugins/mill/scripts/_implementer_sonnet.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/scripts/_test_registry.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-reviewers.py`
