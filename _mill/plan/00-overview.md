# Plan: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
task: 'mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)'
slug: mill-pipeline-dispatch-entrygate-gaps
approved: false
started: '2026-08-09T07:07:14Z'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: mill-go-dispatch-classification-observability
    file: 01-mill-go-dispatch-classification-observability.md
    depends-on: []
    verify: null
  - number: 2
    name: mill-go-treeguard-explicit-guard
    file: 02-mill-go-treeguard-explicit-guard.md
    depends-on: [1]
    verify: null
  - number: 3
    name: status-inferred-success-helper
    file: 03-status-inferred-success-helper.md
    depends-on: []
    verify: 'PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py'
  - number: 4
    name: implementer-brief-heartbeat-nudge
    file: 04-implementer-brief-heartbeat-nudge.md
    depends-on: []
    verify: null
  - number: 5
    name: mill-plan-revise-reentry
    file: 05-mill-plan-revise-reentry.md
    depends-on: []
    verify: null
  - number: 6
    name: review-plan-reviews-subdir-plumbing
    file: 06-review-plan-reviews-subdir-plumbing.md
    depends-on: []
    verify: 'PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-plan-finalize-round.py test-review-prepare-envelope.py'
  - number: 7
    name: mill-merge-status-absent-fallback
    file: 07-mill-merge-status-absent-fallback.md
    depends-on: []
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: doc-batches-preserve-file-conventions

- **Decision:** Every card in batches 1, 2, 4, 5, and 7 is a surgical prose edit to an existing `SKILL.md`/doc file, never a rewrite.
  Preserve the target file's own heading/numbering style exactly as it already exists at the edit site — do not introduce a new convention.
  Concretely: `mill-go/SKILL.md`'s `## Entry` and `## Agent-mode dispatch` sections use a bold-lead-in numbered-list style (`1. **Step 1 — Title.**`), while `mill-merge/SKILL.md`'s `## Steps` section uses `### N. Title` markdown headings (with a `### N.N. Title` precedent for inserted sub-steps, e.g. its existing `### 5.5.`) — match whichever convention governs the specific section being edited, never the other file's convention.
  Renumber a step/card only when the card's own `Requirements:` explicitly says so; otherwise insert alongside without shifting existing numbers.
- **Rationale:** These files are read by an autonomous orchestrator (mill-go/mill-plan/mill-merge itself) as executable prose — an inconsistent heading style or accidental renumbering silently breaks a downstream step's cross-reference (e.g. "see step 4(c)" or "per step 6's existing convention") without any test catching it, since these batches have `verify: null` by design (no runnable surface).
- **Applies to:** `mill-go-dispatch-classification-observability`, `mill-go-treeguard-explicit-guard`, `implementer-brief-heartbeat-nudge`, `mill-plan-revise-reentry`, `mill-merge-status-absent-fallback`

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `plugins/mill/docs/harness-tool-contracts.md`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-merge/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-status.py`
