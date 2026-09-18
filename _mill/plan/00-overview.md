# Plan: Review output reliability: metadata misattribution and factual-accuracy failures

```yaml
task: 'Review output reliability: metadata misattribution and factual-accuracy failures'
slug: review-output-reliability-and-attribution-bugs
approved: false
started: '20260918-175444'
parent: main
root: ""
verify: null
discussion_sha: 5f403b519b518e0415fc75dd5953dccf0e95eb35
```

## Batch Index

```yaml
batches:
  - number: 1
    name: review-output-attribution-reliability
    file: 01-review-output-attribution-reliability.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-templates.py
```

## Shared Decisions

### Decision: reviewer_self_id removed, not repointed

- **Decision:** `reviewer_self_id` is deleted outright from every template and from the schema
  doc — not repointed to read from the dispatch envelope (issue #989's alternative suggestion).
- **Rationale:** `reviewer_model` is already dispatch-envelope-sourced (orchestrator-supplied at
  prepare time from the config alias, correctable via `--actual-model` at finalize time). Making
  `reviewer_self_id` read from the same source would just duplicate `reviewer_model` under a
  second name. Removal also eliminates the field's live footgun: an LLM writing an unreliable or
  outright wrong self-assessment into a permanent review file.
- **Applies to:** `review-output-attribution-reliability`.

### Decision: code-review templates gain the existing plan-review mechanism-claim rule verbatim

- **Decision:** `review-code-holistic.md` and `review-code-batch.md` receive the identical
  "Mechanism claims must be source-verified." paragraph already present in
  `review-plan-holistic.md` / `review-plan-batch.md` (added by commit `fbf501ea`), reused
  word-for-word, in the same position relative to the existing "Fabricating file contents…"
  sentence in each file's `## Source-grounding rule` section.
- **Rationale:** Issues #991 and #1003 are both holistic-code-review incidents of exactly the
  defect class this rule already closes for plan review — a reviewer asserting a specific,
  checkable fact about file content (a JSON key's presence, a SHA's character count) that turned
  out false on the file's actual bytes. Reusing the existing paragraph verbatim keeps the
  established repo convention in one place and lets `test_plan_mechanism_claim_rule_present`-style
  substring assertions extend cleanly to the code templates.
- **Applies to:** `review-output-attribution-reliability`.

### Decision: #1018 (reviewer_model misattribution under agent-mode override) requires no code change

- **Decision:** No batch or card in this plan touches `--actual-model` / `apply_actual_model_override()`
  / any orchestrator SKILL's Agent-mode dispatch instructions.
- **Rationale:** Verified by reading the current code (see `_mill/discussion.md`'s
  "reviewer-model-attribution-already-fixed" Decision for the full citation trail): the
  `--actual-model` CLI flag (`_review_common.py`), its SKILL-level dispatch threading
  (`mill-go-base/SKILL.md` "## Agent-mode dispatch" step 5, reused by mill-start, mill-plan, and
  mill-go for every reviewer dispatch), and its dedicated round-trip regression tests
  (`plugins/mill/unit_tests/test-review-finalize.py`) all already exist and all predate #1018's
  reported incident date. The mechanism the issue asks for is already built, already wired
  everywhere it needs to be, and already tested — there is nothing here for a plan to implement.
- **Applies to:** the task as a whole (no batch).

## All Files Touched

- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-templates.py`
