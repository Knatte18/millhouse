# Plan: mill-plan/verify/implement pipeline: misc small bugs, round 3

```yaml
task: 'mill-plan/verify/implement pipeline: misc small bugs, round 3'
slug: mill-plan-verify-implement-misc-r3
approved: false
started: 20260923-115220
parent: main
root: ""
verify: null
discussion_sha: a02c7b5d50e05708dbac36e0b3deb4ef0dba92cb
```

## Batch Index

```yaml
batches:
  - number: 1
    name: plan-validate-dotnet-scoping
    file: 01-plan-validate-dotnet-scoping.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-subprocess-util.py
  - number: 2
    name: status-path-coercion
    file: 02-status-path-coercion.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
  - number: 3
    name: verify-guidance-docs
    file: 03-verify-guidance-docs.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agents-defs.py
```

## Shared Decisions

### Decision: already-fixed-issues-get-no-code-change

- **Decision:** #1120/#1121 (merge-in `--recompute-baseline` dict crash) and #1082 (per-path `git check-ignore` breadcrumb noise) are already fixed on `main` (commits `5d111edf` and `599a2c1b`) with regression tests. This plan changes no code for them; the only #1082 residue is the stale `_subprocess_util` module docstring (card 2).
- **Rationale:** the reporting sessions ran a stale plugin cache; re-fixing would duplicate shipped work.
- **Applies to:** all batches

### Decision: batches-are-independent

- **Decision:** the three batches touch disjoint files and have no ordering dependency, so every batch has `depends-on: []`.
- **Rationale:** the six issues are mutually unrelated; grouping is by file/subsystem only.
- **Applies to:** all batches

### Decision: python-prefix-on-verify

- **Decision:** every `verify:` starts with `PYTHONPATH= ` and uses `run-all.py --only <files>` scoped to the batch's own test files.
- **Rationale:** CLAUDE.md "Verify command shape" — keeps the test subprocess off the plugin-cache `PYTHONPATH`.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/agents/mill-implementer-high.md`
- `plugins/mill/agents/mill-implementer-low.md`
- `plugins/mill/agents/mill-implementer-max.md`
- `plugins/mill/agents/mill-implementer-medium.md`
- `plugins/mill/agents/mill-implementer-xhigh.md`
- `plugins/mill/agents/mill-implementer.md`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_subprocess_util.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-agents-defs.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-status.py`
