# Plan: 10 (B) — Plan-template format-forbedringer

```yaml
task: 10 (B) — Plan-template format-forbedringer
slug: plan-template-quality
approved: true
started: 20260506T135532Z
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - name: batch-numbering
    file: 01-batch-numbering.md
    depends-on: []
    verify: python plugins/mill/unit_tests/test-plan-dag.py && python plugins/mill/unit_tests/test-plan-validate.py
  - name: field-rename
    file: 02-field-rename.md
    depends-on: [batch-numbering]
    verify: python plugins/mill/unit_tests/test-plan-validate.py && python plugins/mill/unit_tests/test-review-common.py
  - name: guidance
    file: 03-guidance.md
    depends-on: [field-rename]
    verify: null
```

## Shared Decisions

### Decision: backward-compat

- **Decision:** `_plan_dag.py` accepts both integer `depends-on:` entries (new format) and string `depends-on:` entries (legacy format). Integer deps are validated against `number:` values; string deps against `name:` values. Mixed types in one entry's `depends-on:` list are rejected. The `number:` field itself is optional — plans without it use the legacy string format.
- **Rationale:** Tasks 9 (`wiki-enhance`) and 11 (`review-code-enhancements`) have existing approved plans with name-based `depends-on:`. They must remain valid after this task merges.
- **Applies to:** batch-numbering

### Decision: field-rename-scope

- **Decision:** Rename `Reads:` → `Context:` and `Modifies:` → `Edits:` in all card-field templates, regex constants, required-field lists, review criteria text, error messages, docstrings, and SKILL.md instructions. `Creates:` and `Deletes:` are unchanged.
- **Rationale:** `Context:` signals read-only background; `Edits:` is unambiguous about modification. The old overlap between `Reads:` and `Modifies:` was the root of the redundancy bug.
- **Applies to:** field-rename

### Decision: guidance-approach

- **Decision:** Strengthen mill-plan SKILL.md Principles section and plan-batch.md template to mandate stable identifiers in `Requirements:` and declare `Context:` as an allowlist. Add BLOCKING plan-review criteria for vague Requirements and incomplete Context listings.
- **Rationale:** These are instruction changes only — no new code. The review criteria enforce the rules at plan-review time.
- **Applies to:** guidance

## All Files Touched

- `plan/01-batch-numbering.md`
- `plan/02-field-rename.md`
- `plan/03-guidance.md`
- `plugins/mill/scripts/_plan_dag.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/implementer-brief.md`
- `plugins/mill/templates/plan-batch.md`
- `plugins/mill/templates/plan-overview.md`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-plan-dag.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-common.py`
