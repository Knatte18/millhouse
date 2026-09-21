# Plan: mill-go/mill-merge-in orchestration robustness gaps, round 2

```yaml
task: mill-go/mill-merge-in orchestration robustness gaps, round 2
slug: mill-go-merge-in-orchestration-robustness-r2
approved: true
started: "20260921-174106"
parent: main
root: ""
verify: null
discussion_sha: a7570b885d3f8f88a7bf1954e916b3e49735a9ab
```

## Batch Index

```yaml
batches:
  - number: 1
    name: finalize-completeness-and-baseline-robustness
    file: 01-finalize-completeness-and-baseline-robustness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-verify-baseline.py
  - number: 2
    name: orchestration-skill-doc-fixes
    file: 02-orchestration-skill-doc-fixes.md
    depends-on: []
    verify: null
  - number: 3
    name: plan-validate-build-tag-coverage
    file: 03-plan-validate-build-tag-coverage.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
  - number: 4
    name: merge-in-conflict-and-verify-robustness
    file: 04-merge-in-conflict-and-verify-robustness.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py test-merge-in-subagent.py test-config.py
  - number: 5
    name: self-resolve-card-insertion-auto-renumber
    file: 05-self-resolve-card-insertion-auto-renumber.md
    depends-on: [2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
```

## Shared Decisions

### Decision: grouping is by shared file, not by source issue

- **Decision:** the twelve source GitHub issues (#1104, #1091, #1090, #1089, #1069, #1068, #1065, #1061, #1060, #1059, #1057, #1047) are grouped into five batches by which files they edit, not one batch per issue: batch 1 groups every `_implementer_common.py`/`_verify_baseline.py` fix (#1104, #1061, #1060, #1089); batch 2 groups the two pure-doc `SKILL.md` fixes (#1091, #1090); batch 4 groups every `millpy-merge-in-subagent.py`/its templates/config fix (#1065, #1059, #1047, #1068); batch 3 and batch 5 are each a single issue (#1069, #1057) but both touch `_plan_validate.py`, so batch 5 declares `depends-on: [3]` (alongside `depends-on: [2]` for its shared `mill-go-base/SKILL.md` edit) to avoid a `parallel-modifies-overlap` finding on either shared file.
- **Rationale:** matches `_mill/discussion.md`'s own Technical context grouping and this hub's own established convention (see the already-landed `mill-infra-reliability-misc-r2` plan's "eight independent batches, no cross-batch dependencies" Decision) of avoiding a `parallel-modifies-overlap` validator conflict by declaring a dependency edge whenever two batches would otherwise touch the same file with no ordering between them.
- **Applies to:** all batches.

### Decision: test convention

- **Decision:** every code-touching batch extends an existing unit-test file in `plugins/mill/unit_tests/` rather than creating a new one: `test-implementer-common.py`, `test-verify-baseline.py`, and `test-plan-validate.py` are actually edited with new cases; `test-millpy-merge-in-subagent.py` and `test-config.py` are actually edited in batch 4. `test-merge-in-subagent.py` is a distinct case — batch 4 runs it (shared fixtures against the same module) but does not edit it, purely as a regression check, per that batch's own `## Batch Tests`. Verify commands run only the relevant file(s), never the unbounded suite.
- **Rationale:** matches this repo's own `## Testing` conventions and keeps each batch's verify scope proportional to its diff.
- **Applies to:** batches 1, 3, 4, 5 (batch 2 is pure documentation with no runnable surface — see its own `## Batch Tests`).

### Decision: doc-only batch uses `verify: null`

- **Decision:** batch 2 edits only `SKILL.md` prose (no code, no new test). Its frontmatter `verify:` is `null`.
- **Rationale:** there is no runnable surface to verify — `## Batch Tests` states the self-review alternative, matching this project's established pattern for documentation-only plan batches (see the already-landed `mill-infra-reliability-misc-r2` plan's batches 6-8).
- **Applies to:** batch 2.

### Decision: #1102 dependency already satisfied

- **Decision:** this plan makes no change to `mill-infra-reliability-misc-r2`'s already-landed lazy on-demand baseline computation (`_verify_baseline.compute_batch_baseline_on_demand`, the `baseline_parent_sha` pinning, the removed eager pre-flight). Batch 1's #1060 and #1089 cards build strictly on top of that existing mechanism.
- **Rationale:** per `_mill/discussion.md`'s Problem section, that dependency task has already merged to `main`; re-litigating its own Decision here would duplicate a separate, already-completed task's deliberately narrow scope.
- **Applies to:** batch 1.

## All Files Touched

- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_plan_dag.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/scripts/millpy-merge-in-subagent.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-merge-in/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-config.py`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-verify-baseline.py`
