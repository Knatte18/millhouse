# Plan: '29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent'

```yaml
task: '29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent'
slug: mill-merge-subagent
approved: true
started: 20260507-083235
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
    name: cli-and-templates
    file: 01-cli-and-templates.md
    depends-on: []
    verify: null
  - number: 2
    name: skill-and-config
    file: 02-skill-and-config.md
    depends-on: [1]
    verify: null
  - number: 3
    name: unit-tests
    file: 03-unit-tests.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: lean-builder

- **Decision:** The Builder (Opus) reads only JSON verdicts from `millpy-merge-in-subagent.py`. It never reads source files, diffs, or test output directly.
- **Rationale:** Mirrors the `mill-go` lean-Builder principle. Conflict resolution and verify-fix are context-heavy; delegating them to a Sonnet sub-agent keeps the Builder context budget for orchestration.
- **Applies to:** all batches

### Decision: _forward_output-convention

- **Decision:** `_forward_output(output, project_root)` always returns 0 (success or stuck). Exit code 1 from the CLI means a pre-launch error with no JSON emitted. This matches the convention in `millpy-implement.py`.
- **Rationale:** The SKILL.md reads the JSON verdict to decide success vs rollback; it does not inspect the exit code for stuck detection.
- **Applies to:** batch cli-and-templates, batch unit-tests

### Decision: no-status-tracking

- **Decision:** `millpy-merge-in-subagent.py` does not write to `task/status.md` or any wiki file. It is a stateless dispatcher: config in, JSON out.
- **Rationale:** merge-in is not a task-lifecycle operation; adding status writes would couple merge-in to the task lifecycle unnecessarily.
- **Applies to:** batch cli-and-templates

### Decision: verify-fix-is-single-shot

- **Decision:** The CLI is single-shot for verify-fix. It runs the verify command once; on failure, spawns one sub-agent session and passes `<VERIFY_FIX_ROUNDS>` in the brief. The sub-agent self-fixes internally. The SKILL calls the CLI once per failing verify command.
- **Rationale:** Consistent with the batch implementer self-fix pattern. The SKILL stays lean; the sub-agent owns fix iteration.
- **Applies to:** batch cli-and-templates, batch skill-and-config

## All Files Touched

- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
- `plugins/mill/templates/merge-in-verify-brief.md`
- `plugins/mill/templates/wiki-config.yaml`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
