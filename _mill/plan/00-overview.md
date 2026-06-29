# Plan: Add first-class Moves/Renames field to plan cards for rename-heavy batches

```yaml
task: "Add first-class Moves/Renames field to plan cards for rename-heavy batches"
slug: "mill-plan-rename-moves"
approved: false
started: "20260629-165500"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: move-parsing-foundation
    file: 01-move-parsing-foundation.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
  - number: 2
    name: validator-move-checks
    file: 02-validator-move-checks.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-millpy-validate-plan.py
  - number: 3
    name: templates-skill-config
    file: 03-templates-skill-config.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
  - number: 4
    name: review-backends
    file: 04-review-backends.md
    depends-on: [1, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-plan-flow.py test-language-skills-directive.py test-moves-check.py
```

## Shared Decisions

### Decision: single-moves-parser

- **Decision:** One Moves parser lives in `_review_common.py` (`parse_moves`, `compute_moves_union`). Every consumer (the validator `_plan_validate.py`, the review backends `_review_plan.py` / `_review_code.py`, and `_agent_dispatch.py`) imports it — no per-module re-implementation. This deliberately differs from the older per-field `_parse_edits_only` / `_parse_creates_only` duplication in `_plan_validate.py`; new code reuses the shared parser.
- **Rationale:** a move's grammar (two backtick paths + arrow) is non-trivial; a single source avoids drift between the validator and the bulkers.
- **Applies to:** all batches.

### Decision: moves-grammar

- **Decision:** A card's `Moves:` field is the literal `none` inline (`- **Moves:** none`) or multi-line sub-bullets, each EXACTLY `` `<src>` -> `<dst>` `` — two backtick-wrapped paths separated by ASCII ` -> ` (space-hyphen-greater-space). No Unicode arrow. `Moves:` sits immediately after `Deletes:` and before `Requirements:` in every card.
- **Rationale:** fits the existing backtick-bullet card grammar; ASCII-only per the repo's cp1252 constraint.
- **Applies to:** all batches.

### Decision: move-endpoint-accounting

- **Decision:** Across all path machinery a Move **source** behaves like a `Deletes:` token (it disappears) and a Move **target** behaves like a `Creates:` token (it appears). Concretely: targets are suppressed in `non-existent-path` like creates; targets count in `All Files Touched` (sources excluded, mirroring the existing Deletes exclusion); both endpoints count as "touched" for `parallel-modifies-overlap`; sources count toward the `batch-oversized` context estimate (targets excluded). For review bulks, plan review adds Move **sources** (exist pre-impl), code review adds Move **targets** (exist post-impl).
- **Rationale:** a rename is semantically delete-old + create-new preserving identity; reusing established rules keeps the validator coherent and avoids false non-existent-path errors on downstream cards.
- **Applies to:** validator-move-checks, review-backends.

### Decision: mechanical-rename-check-advisory

- **Decision:** The code-review mechanical rename check is **advisory NIT only, never auto-BLOCKING**. It runs in **per-batch code review only** (skipped in holistic; requires a batch `start_sha`). It uses `git diff --name-status --find-renames=<thr>% <start_sha>..HEAD` with `<thr>` from `pipeline.rename_detect_pct` (default 30). A planned Move pair not reported as a rename (`R`) yields a NIT advising confirmation that `git mv` + surgical edits were used. The LLM code-review criterion is the layer that escalates a genuine full rewrite to BLOCKING.
- **Rationale:** git detects renames by content similarity at diff time (it does not record renames), and the motivating workload (renames + kernel/seam extractions) legitimately drops similarity below git's default 50%; a deterministic BLOCKING would false-block the very work this task targets.
- **Applies to:** review-backends, templates-skill-config.

### Decision: python-verify-shape

- **Decision:** Every non-null per-batch `verify:` starts with `PYTHONPATH= ` (empty value, single space) and runs via `uv run --project plugins/mill python ...`. Scoped with `--only <files>` to the batch's tests. ASCII-only in all generated text and `print()` output.
- **Rationale:** mill convention for Python projects (validator `verify-not-isolated` enforces the prefix; cp1252 stdout requires ASCII).
- **Applies to:** all batches.

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/_moves_check.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-language-skills-directive.py`
- `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- `plugins/mill/unit_tests/test-moves-check.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
