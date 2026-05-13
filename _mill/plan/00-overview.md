# Plan: (A) -- Add status_md to paths config + refactor 14 callsites

```yaml
task: (A) -- Add status_md to paths config + refactor 14 callsites
slug: status-md-in-paths-config
approved: true
started: 20260513-074652
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: helper-foundation
    file: 01-helper-foundation.md
    depends-on: []
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
  - number: 2
    name: callsite-refactor
    file: 02-callsite-refactor.md
    depends-on: [1]
    verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
```

## Shared Decisions

### Decision: helper-signature

- **Decision:** The new helper has the signature `_paths.status_path(worktree_root: Path, cfg: dict) -> Path`. It reads `cfg["paths"]["status_md"]` (raises `KeyError` with a message naming `paths.status_md` when the key is absent) and delegates to `_paths.resolve_task_path(worktree_root, cfg_value)` so the `_mill/` -> `task/` compat fallback for in-flight worktrees is preserved with no duplication.
- **Rationale:** Every call site already loads `cfg`. Internal config re-reads inside the helper would force redundant disk hits and create a circular import edge between `_paths` and `_config`. Required `KeyError` (vs silent default) fails loud after this task adds the key to every shipped config.
- **Applies to:** all batches

### Decision: compat-fallback-ownership

- **Decision:** The `_mill/` -> `task/` compat fallback (and its `[compat]` stderr warning) remains owned by `_paths.resolve_task_path`. `_paths.status_path` is a thin wrapper that supplies the cfg-driven relative path and returns whatever `resolve_task_path` produces.
- **Rationale:** Single owner for the fallback rule. The `[compat]` warning fires once per resolution; duplicating logic risks double-warning or silent divergence on the next fallback bug.
- **Applies to:** all batches

### Decision: ascii-only-log-strings

- **Decision:** Any new `print()` / stderr / log strings introduced by this plan use ASCII only (em-dash -> ` -- `, right-arrow -> ` -> `). Docstrings and inline comments are exempt.
- **Rationale:** CLAUDE.md `## Conventions worth carrying` -- Windows cp1252 terminals crash on non-ASCII stdout/stderr. The existing `[compat]` line in `resolve_task_path` is already ASCII; `status_path` adds no new log lines of its own. The `KeyError` message is the only new operator-visible string and must be ASCII.
- **Applies to:** all batches

### Decision: test-shape

- **Decision:** New unit tests live in `plugins/mill/unit_tests/test-paths-status.py` (separate file from `test-paths.py`). Each case uses `tempfile.TemporaryDirectory()` for the worktree fixture and a plain dict for `cfg` (no `_config.load_config` call). Each case prints a `PASS ...` line on success, matching the existing `test-paths.py` `test_resolve_task_path` style.
- **Rationale:** The discussion explicitly named a new test file. Mirroring `test-paths.py`'s style (PASS lines, `contextlib.redirect_stderr` for the `[compat]` assertion) means `run-all.py` integrates without changes -- it iterates `test-*.py`.
- **Applies to:** batch 1 (helper-foundation)

### Decision: wiki-config-mutation-safety

- **Decision:** Adding `paths.status_md: _mill/status.md` to `wiki/config.yaml` is safe to ship mid-flight without a backwards-compat-rollout layer because (1) the key is a pure addition with zero existing readers, (2) every consumer of the key is being added in the same plan (in batches 1 and 2), and (3) any in-flight worktree or stale plugin cache that does not yet have the new helper continues to hardcode its path -- it does not read this key. The compat fallback inside `resolve_task_path` covers the inverse direction (old layout `task/status.md` still readable). The Home.md banner about wiki/config.yaml schema breakage applies to renames and removals of keys with existing readers; this case is neither.
- **Rationale:** Card 1's body documents this analysis in-tree so the `--skip-check wiki-config-mutation` flag used by the validator-fix path has a written justification a future reader can audit. The validator's wiki-config-mutation row in mill-plan's fix table requires either a bootstrap card (condition a) or zero-grep-hits proof (condition b) -- condition (a) is what Card 1 provides.
- **Applies to:** batch 1 (helper-foundation)

## All Files Touched

- `plugins/mill/scripts/_paths.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_spawn_core.py`
- `plugins/mill/scripts/millpy-abandon.py`
- `plugins/mill/scripts/millpy-claim.py`
- `plugins/mill/scripts/millpy-cleanup.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-inspect.py`
- `plugins/mill/scripts/millpy-spawn.py`
- `plugins/mill/scripts/millpy-status.py`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-paths-status.py`
- `wiki/config.yaml`
