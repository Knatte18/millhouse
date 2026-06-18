# Plan: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading

```yaml
task: Fix nested-junction teardown, Windows verify gate in merge-in, and review-plan --round threading
slug: mill-junction-and-agent-gaps
approved: false
started: 20260618-114407
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: junction-recursive-walk
    file: 01-junction-recursive-walk.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-junction.py
  - number: 2
    name: posix-shell-helper
    file: 02-posix-shell-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-merge-in-subagent.py test-millpy-merge-in-subagent.py
  - number: 3
    name: review-round-autodiscovery
    file: 03-review-round-autodiscovery.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-finalize-round.py
```

## Shared Decisions

### Decision: verify-command-isolation

- **Decision:** All verify commands start with `PYTHONPATH= ` (empty value, one space) so the test subprocess does not inherit the mill cache PYTHONPATH and loads worktree modules.
- **Rationale:** Mandated by CLAUDE.md for Python/mill projects; enforced by the `verify-not-isolated` plan validator.
- **Applies to:** all batches

### Decision: fail-loud-over-silent

- **Decision:** When a safety-critical operation cannot complete (e.g. PermissionError scanning a dir for junctions), print a warning to stderr and continue rather than swallowing the error silently.
- **Rationale:** Silent failures in junction stripping can lead to wiki destruction (as occurred on 2026-06-17). Visible warnings let the operator detect and investigate.
- **Applies to:** batch junction-recursive-walk (card 1)

### Decision: helper-extraction-over-duplication

- **Decision:** Extract `_posix_shell_run_args` as a module-level function in `_implementer_common.py`; import it in `millpy-merge-in-subagent.py` rather than inlining.
- **Rationale:** `millpy-merge-in-subagent.py` already imports from `_implementer_common`; the helper eliminates duplication of the bash-detection logic.
- **Applies to:** batch posix-shell-helper (cards 3-4)

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_junction.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/unit_tests/test-junction.py`
- `plugins/mill/unit_tests/test-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-review-plan-finalize-round.py`
