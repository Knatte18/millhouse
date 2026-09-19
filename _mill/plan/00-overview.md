# Plan: _config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args

```yaml
task: '_config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args'
slug: shared-helper-script-validation-gaps
approved: false
started: '20260919-112835'
parent: main
root: ""
verify: null
discussion_sha: dfe1f744067ebc2651db98ae64e4aea77ae4440e
```

## Batch Index

```yaml
batches:
  - number: 1
    name: config-treeguard-guards
    file: 01-config-treeguard-guards.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py test-treeguard.py
```

## Shared Decisions

### Decision: legacy-key hint table over auto-mapping or hard failure

- **Decision:** `_config.py`'s `warn_unknown_keys` gains a module-level `RENAMED_KEY_HINTS: dict[str, str]` mapping the two legacy dotted paths (`pipeline.max_review_rounds`, `pipeline.max_discussion_review_rounds`) to a hint string naming the real `roles.<role>.<scope>.rounds` key. When an unknown key is in this table, the warning appends the hint instead of printing the generic `[config] unknown key: ...` text alone. Every other unknown key is unaffected.
- **Rationale:** honoring the key is ambiguous (five distinct `roles.*.rounds` settings, no non-arbitrary target) and turning the whole unknown-key check into a hard failure is a bigger behavior change than this bug warrants, given the function's existing deliberately-permissive design (see the existing function-local `deprecated_keys` set). See `_mill/discussion.md`'s "Legacy-key hint table, not auto-mapping and not a hard failure" Decision for the full rationale and rejected alternatives.
- **Applies to:** config-treeguard-guards

### Decision: `_treeguard.py` gets its own module-local type guard, not a shared helper

- **Decision:** `_treeguard.check_and_restore` gains two inline `isinstance` checks (on `worktree` and, when not `None`, `git_root`) at the top of the function, raising `TypeError` in the exact message format `_status.py`'s private `_require_path` helper already uses (`"{fn}: {arg} must be a pathlib.Path, got {type}"`). The guard is a local reimplementation, not an import of `_status._require_path` (which is private to `_status.py`) and not a new shared `_argcheck`-style module.
- **Rationale:** `_treeguard.py` already documents and follows the "reimplement a private helper locally" convention in this codebase (see `_rebase_onto_hub`'s own docstring). Extracting a shared helper for a two-argument, two-call-site fix is disproportionate and would touch `_status.py` outside this task's scope. See `_mill/discussion.md`'s "`_treeguard.py` gets its own module-local `_require_path`-style guard" Decision for the full rationale, including why both arguments are guarded even though only a `str` `worktree` (in the nested-hub case) can trigger today's actual crash.
- **Applies to:** config-treeguard-guards

## All Files Touched

- `plugins/mill/scripts/_config.py`
- `plugins/mill/scripts/_treeguard.py`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-treeguard.py`
