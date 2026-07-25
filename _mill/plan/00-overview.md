# Plan: mill-plan review severity counting and validation schema gaps

```yaml
task: mill-plan review severity counting and validation schema gaps
slug: mill-plan-review-validation-gaps
approved: true
started: 20260725-132313
parent: hanf/linux-port-more
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: severity-failloud-core
    file: 01-severity-failloud-core.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
  - number: 2
    name: severity-failloud-legacy-callsites
    file: 02-severity-failloud-legacy-callsites.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-common.py
  - number: 3
    name: severity-vocabulary-docs
    file: 03-severity-vocabulary-docs.md
    depends-on: []
    verify: null
  - number: 4
    name: commit-none-validator
    file: 04-commit-none-validator.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-dag.py test-plan-validate.py
  - number: 5
    name: commit-none-implementer-brief
    file: 05-commit-none-implementer-brief.md
    depends-on: []
    verify: null
  - number: 6
    name: commit-none-backend-gate
    file: 06-commit-none-backend-gate.md
    depends-on: [4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
```

## Shared Decisions

### Decision: fail-loud, not silent-drop, for unrecognized severities

- **Decision:** Any finding whose severity label is neither of the two severities a review type recognizes (`BLOCKING`/`NIT` for plan and code review, `GAP`/`NOTE` for discussion review) is counted toward the blocking-equivalent bucket (`blocking_count` for plan/code, the same field for discussion since `ReviewResult`/`finalize_scope` reuse the `blocking_count`/`nit_count` field names generically across all three review types) — never silently dropped from both counters.
- **Rationale:** three independent production incidents (issues #663, #685, #695) showed reviewer LLMs emitting `[MAJOR]`/`[MINOR]`/`[MEDIUM]`/`[HIGH]` instead of the documented vocabulary, and the existing counters silently dropped them from both `blocking_count` and `nit_count`, letting `mill-plan`'s step 4c auto-approve rounds containing real blocking findings.
- **Applies to:** `01-severity-failloud-core`, `02-severity-failloud-legacy-callsites`, `03-severity-vocabulary-docs`.

### Decision: unrecognized-severity scan covers both output formats, unconditionally

- **Decision:** the fail-loud scan for unrecognized severities always inspects both markdown `### [XXX]` headings (case-sensitive match) AND any fenced ` ```yaml ` `findings:` block entries (case-insensitive `severity:` match) — every time, regardless of which format the two known severities used in that particular review. It does not attempt to infer a single "active" format for the whole document.
- **Rationale:** `parse_blocking_count` picks headings-vs-YAML independently per known-severity call; a single global AND/OR gate on the known severities' heading counts could miss a mixed-format document (e.g. real `### [NIT]` headings present, but an unrecognized severity expressed only in a YAML `findings:` entry). Running both scans unconditionally sidesteps the ambiguity entirely (see `_mill/discussion.md`'s discussion-review round-2 GAP for the incident this decision closes).
- **Applies to:** `01-severity-failloud-core`.

### Decision: `Commit: none` requires every other card field to also be `none`

- **Decision:** `_plan_validate.py`'s new cross-field check rejects a card whose `Commit:` field is the literal `none` when that same card's `Edits:`, `Creates:`, `Deletes:`, or `Moves:` field has any non-`none` content. A `Commit: none` card must be genuinely diff-free (verification-only).
- **Rationale:** issue #664's actual use case is a pure verification gate (e.g. a grep confirming earlier cards finished, no edits of its own). Allowing `Commit: none` alongside real edits would let a card silently leave changes uncommitted.
- **Applies to:** `04-commit-none-validator`, `05-commit-none-implementer-brief`, `06-commit-none-backend-gate`.

### Decision: the no-content-commit-gate carve-out signal is code-derived, never implementer self-reported

- **Decision:** the set of card numbers whose `Commit:` field is `none` (`commit_none_card_ids`) is computed by the orchestrator/CLI from the batch plan file on disk — never trusted from anything the implementer's own JSON report claims about itself.
- **Rationale:** `_implementer_common.py`'s no-content-commit gate is deliberately immune to self-report ("unaffected by cards_done: zero commits means zero work regardless of any self-report" — see the gate's own docstring). The existing `nits_only` exemption this carve-out mirrors is itself orchestrator-supplied (a CLI flag from `millpy-fix.py --nits-only`), not an implementer claim. A self-reported carve-out signal would let a session falsely claim "no commit needed" to bypass the zero-work check.
- **Applies to:** `06-commit-none-backend-gate`.

### Decision: ASCII-only diagnostic output

- **Decision:** any new `print()`/stderr diagnostic text added by this plan uses ASCII only (no em-dash, no Unicode arrows) per project convention.
- **Rationale:** `CLAUDE.md` — Windows cp1252 stdout crashes on non-ASCII output from mill scripts.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_plan_dag.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-plan-dag.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
