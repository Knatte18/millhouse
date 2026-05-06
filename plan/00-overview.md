# Plan: 14 (D) — Holistic-fix agent for cross-batch funn (conflicts with 15)

```yaml
task: '14 (D) — Holistic-fix agent for cross-batch funn (conflicts with 15)'
slug: holistic-fix-agent
approved: true
started: '20260506-171853'
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
    name: foundation-extract
    file: 01-foundation-extract.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: holistic-implement
    file: 02-holistic-implement.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
```

## Shared Decisions

### Decision: from-import-style

- **Decision:** Use `from _implementer_common import _forward_output` in both `millpy-implement.py` and `millpy-implement-holistic.py`.
- **Rationale:** Keeps both call sites identical to the pre-refactor code (`return _forward_output(output)`); the test's `millpy_implement._forward_output` reference still resolves because Python binds the imported name in the importer's namespace.
- **Applies to:** foundation-extract, holistic-implement

### Decision: phase-names-no-round

- **Decision:** Holistic phase names are `holistic-reviewing`, `holistic-fixing`, `holistic-approved` — no embedded round number.
- **Rationale:** There is no batch name to embed, and the round counter belongs to mill-go. Embedding the round would require the CLI to accept and re-echo it into the phase name, adding complexity with no benefit.
- **Applies to:** holistic-implement

### Decision: no-resume

- **Decision:** `millpy-implement-holistic.py` has no `--resume` flag; holistic dispatch is always cold-start.
- **Rationale:** Cross-batch findings span the whole worktree; there is no warm per-batch session to resume. Adding resume would require persisting `holistic_session_id` in status.md — schema complexity with no operational payoff (per discussion decision `session-id-ephemeral`).
- **Applies to:** holistic-implement

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/millpy-implement-holistic.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/implementer-holistic-brief.md`
- `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `wiki/config.yaml`
