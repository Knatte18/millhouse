# Plan: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash

```yaml
task: Fix mill-merge-in stale ref check, PowerShell 5.1 ConvertTo-Json, and _status str-path crash
slug: mill-script-fixes
approved: false
started: 20260706-171827
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: mill-merge-in-stale-ref
    file: 01-mill-merge-in-stale-ref.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
  - number: 2
    name: worktree-asarray
    file: 02-worktree-asarray.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-worktree.py
  - number: 3
    name: status-path-typeerror
    file: 03-status-path-typeerror.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
```

## Shared Decisions

### Decision: three independent bugfixes, no shared code

- **Decision:** Each batch fixes exactly one of the three unrelated GitHub issues (#600, #602, #597). No batch reads or edits another batch's files; all three are root nodes in the DAG with `depends-on: []` and may run in any order (or in parallel, if the orchestrator chooses to).
- **Rationale:** `_mill/discussion.md`'s Scope section explicitly bundles these three only because each is small and self-contained, not because they share design or code. Splitting into independent batches matches that framing and lets a single batch's failure/fix-loop never block the other two.
- **Applies to:** all batches

### Decision: ASCII-only new messages

- **Decision:** Any new `print()` output or exception message text introduced by this task (e.g. the `_status.py` `TypeError` message, any `test-merge.py` fixture output) must be ASCII-only — no em-dashes, arrows, or curly quotes.
- **Rationale:** `_mill/discussion.md`'s Constraints section: Windows cp1252 stdout crashes on non-ASCII, per CLAUDE.md convention.
- **Applies to:** all batches

### Decision: verify commands use the `PYTHONPATH= ` isolation prefix

- **Decision:** Every batch's `verify:` command is prefixed with the literal `PYTHONPATH= ` (empty value, single space) so the test subprocess loads worktree modules instead of the mill plugin cache's copies.
- **Rationale:** `_mill/discussion.md`'s Constraints section and CLAUDE.md's "Verify command shape" rule; this repo has `pyproject.toml` so the Python-project form applies.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/integration_tests/test-merge.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-worktree.py`
