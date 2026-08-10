# Plan: _review_common/_review_plan: verdict/count consistency and path-suppression gaps

```yaml
task: '_review_common/_review_plan: verdict/count consistency and path-suppression gaps'
slug: mill-review-backend-consistency-gaps
approved: true
started: '2026-08-10T18:02:40Z'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: review-plan-context-soft-fail
    file: 01-review-plan-context-soft-fail.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-plan-flow.py
  - number: 2
    name: finalize-verdict-rewrite
    file: 02-finalize-verdict-rewrite.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-finalize.py
  - number: 3
    name: review-loop-min-rounds
    file: 03-review-loop-min-rounds.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-config.py
```

## Shared Decisions

### Decision: no-new-test-files

- **Decision:** All new test coverage extends an existing test file (`test-review-plan-flow.py`, `test-review-class-taxonomy.py`). No new test files are created by this plan.
- **Rationale:** All three items land in files that already carry dedicated coverage for the mechanisms being touched (per discussion.md's Testing section and Q&A log).
- **Applies to:** all batches.

### Decision: no-backend-change-for-798

- **Decision:** The `min_rounds` floor and the demoted-predicate termination check are orchestrator prose changes in `SKILL.md` files only. No new Python helper function is introduced.
- **Rationale:** `Finding.demoted` is already serialised via `Finding.to_dict()` (`_review_common.py:335-342`) and `ReviewResult.findings` (`_review_common.py:346-365`) already aggregates every sub-review's findings into the top-level `findings` key of the JSON envelope every `millpy-review-*.py` CLI prints (confirmed for discussion/plan/code via `ReviewResult.to_dict()` at each `ReviewResult(...)` construction site) — the orchestrator can read `envelope["findings"][*]["demoted"]` today, with zero backend change.
- **Applies to:** `review-loop-min-rounds`.

### Decision: 790-not-touched

- **Decision:** `_review_plan.py`'s resume-mode exclusion of `_disk_reviews` from the returned envelope (commit `8405e526`, `#184`) is correct as-is and is never modified by this plan.
- **Rationale:** per discussion.md's `drop-790-already-fixed` Decision — `#790` is out of scope. `test-review-plan-flow.py`'s existing resume-mode assertions (`len(r.reviews) == 1`, in the blocks documented in-file as "Test 9" and "Test 17") must continue to pass unchanged after batch 1's edits — batch 1's Card 5 explicitly re-runs the full file, not just the new cases, to guard this.
- **Applies to:** `review-plan-context-soft-fail`.

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
