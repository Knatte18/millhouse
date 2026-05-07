# Plan: 28 (A) — review-plan robustness

```yaml
task: '28 (A) — review-plan robustness'
slug: review-plan-robustness
approved: true
started: 20260507-083139
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: backend-fixes
    file: 01-backend-fixes.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 2
    name: validator-skip-checks
    file: 02-validator-skip-checks.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 3
    name: cli-skip-checks
    file: 03-cli-skip-checks.md
    depends-on: [2]
    verify: python plugins/mill/unit_tests/run-all.py

  - number: 4
    name: skill-md-fixes
    file: 04-skill-md-fixes.md
    depends-on: [3]
    verify: null
```

## Shared Decisions

### Decision: error-handling-posture

- **Decision:** All error paths produce valid JSON output rather than raising exceptions. ERROR entries use `{"scope": ..., "round": ..., "verdict": "ERROR", "blocking_count": 0, "file": ..., "error": "...", "session_id": ...}` shape. LLMError and ReviewError are caught at the same level and produce identical entry shapes.
- **Rationale:** Consistent with existing per-batch handling; callers receive JSON they can act on instead of exit-1.
- **Applies to:** batch 1 (bug B holistic error entry shape)

### Decision: skip-checks-filtering-position

- **Decision:** Filtering `skip_checks` happens after all checks run and after the existing `errors.sort(...)` call, not inside individual `_check_*` functions.
- **Rationale:** Simplest correct implementation — no changes needed inside individual check functions; silently ignores unknown names by design; forward-compatible with new check names.
- **Applies to:** batch 2, batch 3

### Decision: resume-mode-holistic-only

- **Decision:** When `resume_round is not None`, `_disk_reviews` are NOT included in `reviews[]`; only the fresh holistic entry is returned.
- **Rationale:** Stale per-batch entries were already processed; including them inflates `blocking_count` with fixed findings. The holistic reviews the full plan and catches any unfixed issues.
- **Applies to:** batch 1 (bug C)

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-validate-plan.py`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
