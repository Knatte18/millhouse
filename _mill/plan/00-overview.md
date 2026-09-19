# Plan: _plan_validate.py context-completeness: path-token exemption list gaps

```yaml
task: '_plan_validate.py context-completeness: path-token exemption list gaps'
slug: plan-validate-context-completeness-path-branch-gaps
approved: false
started: 20260919-114105
parent: main
root: ""
verify: null
discussion_sha: 1cbdcfae269a1d22ef5b5316151f3f0007cb19be
```

## Batch Index

```yaml
batches:
  - number: 1
    name: context-completeness-exemptions
    file: 01-context-completeness-exemptions.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 2
    name: context-completeness-exemptions-tests
    file: 02-context-completeness-exemptions-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 3
    name: context-completeness-exemptions-docs
    file: 03-context-completeness-exemptions-docs.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: three new exemption mechanisms, mirroring existing precedent

- **Decision:** each new exemption (ownership-phrase, literal-enumeration, illustrative-output) is
  a standalone function inserted into `_check_context_completeness`'s existing per-token exemption
  chain (a `continue` guard, exactly like the ten existing exemptions), documented as exemptions
  11-13 in that function's own docstring numbered list. No existing exemption's behavior changes.
- **Rationale:** `_mill/discussion.md`'s Decisions section already worked out each mechanism's exact
  shape against `_plan_validate.py`'s existing conventions (`_PROHIBITION_VERB_FORMS`-style
  hand-spelled verb tables, `_CITATION_MARKERS`-style line-wide presence tests) through three rounds
  of discussion review; this plan implements those decisions verbatim rather than re-deriving them.
- **Applies to:** context-completeness-exemptions.

### Decision: verb-form dicts are hand-spelled, never suffix-generated

- **Decision:** `_OWNERSHIP_VERB_FORMS` and `_OUTPUT_VERB_FORMS` are Python dicts mapping a base verb
  to a tuple of its inflected forms (base, 3rd-person, past, gerund — 5 forms for `rewrite`, mirroring
  `write`'s own irregular entry in `_PROHIBITION_VERB_FORMS`), written out by hand, never derived by
  string concatenation — matching `_PROHIBITION_VERB_FORMS`'s own stated convention and comment.
- **Rationale:** `_mill/discussion.md`'s review round 2 (`_mill/reviews/20260919-113142-discussion-review-r2.md`)
  flagged an earlier `?`-suffix regex design as contradicting this exact convention; the fix committed
  in discussion-fix round 2 is what this plan implements.
- **Applies to:** context-completeness-exemptions.

### Decision: three batches, split by edited file, not by feature

- **Decision:** the plan is three batches — batch 1 edits only `_plan_validate.py`, batch 2 edits
  only `test-plan-validate.py`, batch 3 edits only `mill-plan/SKILL.md` — rather than one batch, or
  three batches split by exemption mechanism.
- **Rationale:** `plugins/mill/scripts/_plan_validate.py` (~44k estimated context tokens),
  `plugins/mill/unit_tests/test-plan-validate.py` (~118k), and `plugins/mill/skills/mill-plan/SKILL.md`
  (~28k) are each individually under `pipeline.max_batch_context_tokens` (120000), but any two
  combined in one batch exceed it — confirmed by running `_plan_validate.run` against an earlier
  single-batch draft of this plan, which raised `batch-oversized` at ~189250 tokens. Splitting by
  exemption mechanism instead (one batch per exemption, each batch touching both the source file and
  the test file) would not fix this: every such batch would still combine `_plan_validate.py` and
  `test-plan-validate.py` and re-trip the same cap. Splitting by file is the only grouping that stays
  under cap while keeping cards 1-3 (which build on each other's insertion point) in one
  batch/session together.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-plan-validate.py`
