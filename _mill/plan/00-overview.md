# Plan: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
task: "_plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens"
slug: plan-validate-context-completeness-missing-symbol-refs
approved: false
started: "20260904-092721"
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: symbol-reference-check
    file: 01-symbol-reference-check.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: mill-plan-fixer-doc-update
    file: 02-mill-plan-fixer-doc-update.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
```

## Shared Decisions

### Decision: no git subprocess dependency in new production code

- **Decision:** The new symbol-resolution code (`_resolve_symbol_files` and its supporting helpers) uses a plain recursive filesystem walk (`os.walk`/`pathlib`) — never `git grep`, `git ls-files`, or any other git subprocess call.
- **Rationale:** Keeps the new unit tests git-free, matching the large majority of `test-plan-validate.py`'s existing fixtures (real git is used today only by `verify-unrelated-test-file`, which has an inherent need for `git diff` against a parent branch; this check has no equivalent need). See `_mill/discussion.md`'s "Resolvability gate" Decision.
- **Applies to:** symbol-reference-check.

### Decision: new tests follow the file's existing end-to-end convention

- **Decision:** Every new test added to `test-plan-validate.py` calls `_plan_validate.run(plan_dir, project_root, ...)` against a tempfile-based fixture tree and filters `result` by `e["check"] == "context-completeness"` — the same pattern every existing test in this file already uses. No test calls an internal helper function (e.g. `_symbol_candidate_shape`, `_resolve_symbol_files`) directly; grepping the file confirms zero existing precedent for unit-testing internal helpers in isolation, so new tests do not introduce a second testing style.
- **Rationale:** Consistency with 100% of this file's existing ~150 test functions. The one exception — a call-counting wrapper around `_resolve_symbol_files` for the cache-invocation test (batch `symbol-reference-check`, card 3) — still exercises the wrapped function only through the public `_plan_validate.run()` entry point; it monkeypatches the module attribute for the duration of one test (restored via `try`/`finally`) rather than calling the helper directly.
- **Applies to:** symbol-reference-check.

### Decision: `pipeline.done_gate` stays `null`

- **Decision:** `mill-config.yaml`'s `pipeline.done_gate` is left at its current value (`null`) — this plan does not change it.
- **Rationale:** Per mill-plan's "Done-gate reminder" guidance, `uvx ruff check .` was run against the current worktree tip from `git_root` before planning: it exits 1 with 1942 pre-existing findings unrelated to this task (repo-wide lint debt). Defaulting `done_gate` to it would make this task (and every future task in the hub) depend on that unrelated debt being fixed first, so it is left `null` and recorded here instead, per the guidance's explicit instruction for this exact case.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
