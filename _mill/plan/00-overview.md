# Plan: millpy-review-plan: finalize envelope verdict silently diverges from the review file's own written verdict

```yaml
task: 'millpy-review-plan: finalize envelope verdict silently diverges from the review file''s own written verdict'
slug: millpy-review-plan-verdict-envelope-bugs
approved: true
started: '20260821-090752'
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
    name: verdict-derivation-fix
    file: 01-verdict-derivation-fix.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-cli-error-envelope.py
```

## Shared Decisions

### Decision: escalate always, downgrade only on this-call ceiling demotion

- **Decision:** In `_review_common.py::finalize_scope()`, the verdict-recomputation block changes
  from an unconditional `verdict = "REQUEST_CHANGES" if blocking_count > 0 else "APPROVE"` to a
  three-way branch: `blocking_count > 0` always forces `REQUEST_CHANGES` (unchanged escalation
  safety net); `blocking_count == 0` and `demoted_any` forces `APPROVE` (unchanged
  ceiling-demotion path); `blocking_count == 0` and not `demoted_any` leaves `verdict` as
  `original_verdict` (the fix — no forced recompute).
- **Rationale:** See `_mill/discussion.md`'s "Verdict derivation: escalate always, downgrade only
  on this-call demotion" Decision. Restores `mill-plan/SKILL.md` step 4c
  (`REQUEST_CHANGES AND blocking_count == 0`) to reachability without touching either of the two
  behaviors that are already correct and tested (the escalation direction and the
  ceiling-demotion direction).
- **Applies to:** verdict-derivation-fix

### Decision: #864 and #867 need regression tests only, not re-implementation

- **Decision:** #864 (missing-`--agent-output` usage-error classification) has zero existing test
  coverage anywhere in the suite and gets a new test in this plan. #867 (`--actual-model`
  overriding `reviewer_model`) is already fully covered by
  `test-review-common.py`'s existing `finalize_scope: actual_model override is reflected in the
  written file` case (raw text with a self-reported `reviewer_model: sonnetmax` line, overridden
  to `sonnet`, asserting the written file carries `sonnet` and not `sonnetmax` — the exact repro
  shape #867 describes) and needs no new test.
- **Rationale:** Verified directly against the current test suite during plan-writing (grepped
  for `agent_output`/`agent-output` across every unit test file — zero hits for the missing-flag
  case; read `test-review-common.py` lines 862-878 directly — the `actual_model` override case is
  already parametrized exactly as #867 describes).
- **Applies to:** verdict-derivation-fix

## All Files Touched

- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
