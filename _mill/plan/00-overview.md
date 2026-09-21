# Plan: mill-plan/mill-start planning-process gaps, round 2

```yaml
task: mill-plan/mill-start planning-process gaps, round 2
slug: mill-plan-process-gaps-r2
approved: false
started: 20260921-153215
parent: main
root: ""
verify: null
discussion_sha: "6bbba7566936657a8b31ebf5691a20acd8a22103"
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: doc-fixes
    file: 01-doc-fixes.md
    depends-on: []
    verify: null
  - number: 2
    name: allow-missing-refs
    file: 02-allow-missing-refs.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-plan-flow.py
  - number: 3
    name: write-brief-warning
    file: 03-write-brief-warning.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-agent-dispatch.py
  - number: 4
    name: cross-batch-build-break
    file: 04-cross-batch-build-break.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-plan-validate-cross-batch-build-break.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: All four batches are independent roots

- **Decision:** Every batch has `depends-on: []`. None of the four fixes share a file, and none depends on another's code landing first for correctness — batch 1 is pure documentation, batches 2–4 each touch a disjoint set of script/test files.
- **Rationale:** batch 1's card 7 (the `cross-batch-build-break` fix-table row) documents the exact check name and remedy text that batch 4's card 13 implements; both cards were written from the same source (`_mill/discussion.md`'s `1056-cross-batch-build-break-check` Decision) with identical wording, so no runtime or textual inconsistency exists regardless of which batch lands first.
- **Applies to:** all batches.

### Decision: `done_gate` and this plan's own module-wide `verify:` stay `null`

- **Decision:** Neither `mill-config.yaml`'s `pipeline.done_gate` (already `null` in the hub config; unchanged by this plan) nor this overview's own top-level `verify:` field is set.
- **Rationale:** `uvx ruff check plugins/mill/scripts` was run against this worktree's current tip before writing this plan and exits 1 with 310 pre-existing findings unrelated to this task (per "Done-gate reminder" in `mill-plan/SKILL.md`). Defaulting either field to that command would make every future task in this hub depend on unrelated pre-existing lint debt being fixed first. Each batch's own scoped `verify:` (targeted unit-test runs) is the regression gate for this task's actual changes.
- **Applies to:** all batches.

### Decision: batch 1 (doc-fixes) has no automated `verify:`

- **Decision:** Batch 1's frontmatter `verify:` is `null`.
- **Rationale:** every card in batch 1 is a text edit to a `SKILL.md` file — prose read by an orchestrator, not executed code. No unit test in this repo exercises `SKILL.md` prose content. Batch Tests (in `01-doc-fixes.md`) states this explicitly per the template's own "if `verify: null`, state why" instruction.
- **Applies to:** batch 1 (`doc-fixes`) only.

### Decision: `cross-batch-build-break` test lives in its own new file, not the existing `test-plan-validate.py`

- **Decision:** Batch 4's card 14 creates `plugins/mill/unit_tests/test-plan-validate-cross-batch-build-break.py` rather than appending to `plugins/mill/unit_tests/test-plan-validate.py`.
- **Rationale:** `test-plan-validate.py` is 584KB (~146,083 tokens) — editing it directly as an `Edits:` target on a card would put that single file alone well over `pipeline.max_batch_context_tokens` (120,000, the `batch-oversized` validator's per-card cap). This repo already has exactly this precedent: `plugins/mill/unit_tests/test-plan-validate-card-numbering.py`'s own header comment states it was "kept as its own standalone file rather than appended to test-plan-validate.py (323KB)" for the identical reason. `run-all.py` auto-discovers every `test-*.py` file via `glob`, so the new file needs no separate registration.
- **Applies to:** batch 4 (`cross-batch-build-break`) only.

## All Files Touched

- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/unit_tests/test-agent-dispatch.py`
- `plugins/mill/unit_tests/test-plan-validate-cross-batch-build-break.py`
- `plugins/mill/unit_tests/test-review-common.py`
