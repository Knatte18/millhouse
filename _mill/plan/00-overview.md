# Plan: 51 (D) -- Config infra: env interpolation + agents.yaml inheritance

```yaml
task: '51 (D) -- Config infra: env interpolation + agents.yaml inheritance'
slug: config-env-interpolation
approved: false
started: 20260517-051920
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: strand-a-env-interp
    file: 01-strand-a-env-interp.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py

  - number: 2
    name: strand-b-extends
    file: 02-strand-b-extends.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints._

### Decision: Two independent strands ship in parallel

- **Decision:** Strand A (env interpolation in `_config.py`) and Strand B (extends inheritance in `_reviewers.py`) touch disjoint files and have no functional dependency. Each lives in its own batch with `depends-on: []`; mill-go schedules them in parallel.
- **Rationale:** Discussion bundles them as "two unrelated config improvements." No shared module, no shared test file, no rollout coupling between strands.
- **Applies to:** all batches.

### Decision: ASCII-only in all new error messages and log strings

- **Decision:** Every new `raise ConfigError(...)` / `raise ReviewerError(...)` message and every new `print()` call uses ASCII only. Em-dash -> ` -- `; right-arrow -> ` -> `. Docstrings and comments are exempt.
- **Rationale:** CLAUDE.md hard rule; Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** both batches.

### Decision: Tests use `tempfile` + `_test_*` fixture helpers; no real git / no real LLM

- **Decision:** New tests follow the existing pattern in `test-config.py` / `test-reviewers.py`: write fixture YAML via `_write_yaml` into `tempfile.TemporaryDirectory()`, never invoke `subprocess.run(["git", ...])` outside the existing `_git_init` helper, never invoke `claude`. Tests that touch `os.environ` restore the prior value in a `finally:` block.
- **Rationale:** CLAUDE.md unit-test rule; the existing test files already follow this pattern, so new tests slot in without infrastructure work.
- **Applies to:** both batches.

### Decision: Single-pass, non-recursive parser semantics for both strands

- **Decision:** `_substitute_string` performs one regex pass and does NOT re-scan substituted output for new `${...}` patterns. `_reviewers.load()` resolves multi-level extends chains via single top-down walk per leaf; resolved entries are not re-scanned for further `extends:` fields.
- **Rationale:** Eliminates surprise loops; matches shell `${VAR:-default}` convention; trivial mental model for readers.
- **Applies to:** both batches.

## All Files Touched

- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_reviewers.py`
- `plugins/mill/templates/reviewers.yaml`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-reviewers.py`
- `wiki/agents.yaml`
