# Plan: _plan_validate: context-completeness fires on forbidding/explanatory file mentions

```yaml
task: '_plan_validate: context-completeness fires on forbidding/explanatory file mentions'
slug: plan-validate-context-completeness-gaps
approved: false
started: '2026-08-12T18:26:48Z'
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
    name: prohibition-regex-generalization
    file: 01-prohibition-regex-generalization.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: regression-tests
    file: 02-regression-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
```

## Shared Decisions

### Decision: Negation-word-set + verb-word-set regex, not phrase-tuple enumeration or structural markup

- **Decision:** Replace the fixed `_PROHIBITION_MARKERS` phrase-tuple list in `_plan_validate.py` with two word sets — a negation-word/phrase set and a verb-word set (each verb expanded to its full inflected-form set) — and treat a `Requirements:` physical line as prohibition-exempt when it contains at least one negation word/phrase AND at least one verb form, matched anywhere on the same line (line-wide, not positionally adjacent), each via word-boundary (`\bword\b`) regex.
- **Rationale:** the existing enumerated-phrase-tuple list has already been patched twice ("round 2", "round 3" per commit history) and keeps missing real phrasings (issues #814, #828, #841). The negation+verb word-set design matches the issue reporters' own suggested direction, stays inside the existing single-function/line-scan architecture, and needs no new plan-authoring syntax.
- **Applies to:** batch `prohibition-regex-generalization` (the only batch that edits `_plan_validate.py`'s marker logic). Batch `regression-tests` exercises the resulting behavior but does not re-derive it.
- **Known, accepted tradeoff:** line-wide (not adjacency-scoped) matching means a multi-clause `Requirements:` line naming a genuine dependency alongside an unrelated negation+verb clause could be silently exempted. This is accepted (see `_mill/discussion.md`'s Decisions) because the alternative failure mode (false-positive `context-completeness` errors blocking valid plan cards) is worse, and Requirements lines are short prose in practice. Batch `regression-tests` includes a partial-mitigation regression case: a line with an unrelated negation word but NO verb-form match still fires `context-completeness` on a genuine dependency.
- **Known, accepted gaps (not fixed by this plan):** nested-bullet/multi-line prohibitions (negation on a parent bullet, path on a child bullet) and double-negative phrasing (e.g. "do not skip touching `foo.py`") are both documented as limitations, not fixed — see batch 1 Card 1's docstring requirement and the `mill-plan/SKILL.md` guidance note in Card 2.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
