# Plan: Migrate wiki task store to TinyDB

```yaml
task: Migrate wiki task store to TinyDB
slug: wiki-tinydb
approved: false
started: 20260523-132841
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: Data Layer
    file: 01-data-layer.md
    depends-on: []
    verify: null
  - number: 2
    name: Server Integration
    file: 02-server.md
    depends-on: [1]
    verify: null
  - number: 3
    name: Tests
    file: 03-tests.md
    depends-on: [2]
    verify: "python plugins/mill/unit_tests/test-wiki-store.py && python plugins/mill/unit_tests/test-wiki-render.py && python plugins/mill/integration_tests/test-wiki-daemon-tinydb.py"
```

## Shared Decisions

### Decision: TinyDB JSONStorage

- **Decision:** Use TinyDB's default `JSONStorage` with the database file at `<wiki_path>/tasks.json`. The daemon holds one `TinyDB` instance for its entire lifetime.
- **Rationale:** Default storage requires no extra dependencies and gives transparent JSON persistence.
- **Applies to:** batch 1 (Store), batch 2 (Server)

### Decision: ASCII-only stdout

- **Decision:** All `print()` and `_log()` calls use ASCII characters only. Use ` -- ` not `—`, ` -> ` not `→`. Windows cp1252 crashes on non-ASCII stdout.
- **Rationale:** Documented in CLAUDE.md.
- **Applies to:** all batches

### Decision: Test fixtures in .scratch/

- **Decision:** Integration test fixtures (temp git repos, wiki clones) go in `.scratch/<test-subdir>/`, never in `/tmp/` or `%TEMP%`.
- **Rationale:** Documented in CLAUDE.md and `mill:conversation` skill.
- **Applies to:** batch 3

### Decision: No inline comments unless WHY is non-obvious

- **Decision:** Write no comments. Only add one when the WHY is non-obvious: a hidden constraint, workaround, or surprising invariant.
- **Rationale:** Project default per CLAUDE.md.
- **Applies to:** all batches

### Decision: Error types from wiki/__init__.py

- **Decision:** All raised exceptions use the existing hierarchy from `wiki/__init__.py` (`WikiError`, `WikiPathError`, `WikiPushError`, etc.). No new exception classes.
- **Rationale:** Keeps the error namespace stable for callers.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/integration_tests/test-wiki-daemon-tinydb.py`
- `plugins/mill/pyproject.toml`
- `plugins/mill/scripts/wiki/_parse.py`
- `plugins/mill/scripts/wiki/_render.py`
- `plugins/mill/scripts/wiki/_server.py`
- `plugins/mill/scripts/wiki/_store.py`
- `plugins/mill/unit_tests/test-wiki-render.py`
- `plugins/mill/unit_tests/test-wiki-store.py`
