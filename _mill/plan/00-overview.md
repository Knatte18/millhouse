# Plan: _plan_validate and baseline verify gate gaps

```yaml
task: "_plan_validate and baseline verify gate gaps"
slug: "plan-verify-gate-gaps"
approved: false
started: "20260924-060625"
parent: "main"
root: ""
verify: null
discussion_sha: "548bb20b5445acfb3318c90679e39a2312c30238"
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: plan-validate-checks
    file: 01-plan-validate-checks.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py test-plan-validate-card-numbering.py test-plan-validate-indent-drift-line.py
  - number: 2
    name: baseline-short-circuit
    file: 02-baseline-short-circuit.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-verify-baseline.py test-millpy-implement.py test-millpy-fix.py
```

## Shared Decisions

### Decision: two-independent-batches

- **Decision:** Batch 1 covers the two `_plan_validate.py` changes (#1142, #1143); batch 2 covers the baseline short-circuit change (#1144).
  The batches share no files, so both have `depends-on: []`.
- **Rationale:** the two halves touch disjoint modules and disjoint test files; each stays well under the card and context caps.
- **Applies to:** all batches

### Decision: new-tests-in-standalone-files-where-cheap

- **Decision:** new `_plan_validate` tests for the line locator go in a new standalone file `test-plan-validate-indent-drift-line.py` (self-contained fixtures, direct calls to the private check functions), and the starts-at-1 tests extend the existing standalone `test-plan-validate-card-numbering.py`.
  Only the one frozen-message test and any fixture broken by the new numbering check are edited inside the 15k-line `test-plan-validate.py`.
- **Rationale:** avoids loading and re-editing the giant test file for new cases, matching this repo's existing "new standalone test file" convention.
- **Applies to:** plan-validate-checks

### Decision: seeded-pair-guard-is-defensive

- **Decision:** the `_is_short_circuit_baseline` guard at pair-cache seeding time is implemented exactly as `_mill/discussion.md` specifies and tested with a hand-built all-synthetic seed.
  Today `compute_baseline` extracts signatures without a return code, so a real module-wide seed never carries `NONZERO_EXIT:` lines and the guard does not fire in production; a silent-failing compound module-wide run seeds `[]`, which waives nothing and is already strict.
  `compute_baseline` is deliberately left untouched.
- **Rationale:** one detector, no bypass if `compute_baseline` later threads the return code through.
- **Applies to:** baseline-short-circuit

### Decision: no-skill-doc-changes

- **Decision:** the `mill-plan` SKILL.md fix-table rows for `requirements-quote-indent-drift` and `card-numbering` stay unchanged; the new `line` field and message suffix are additive and the existing row wording still matches.
- **Rationale:** keeps scope to what #1142-#1144 report.
- **Applies to:** all batches

## All Files Touched

- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/unit_tests/test-millpy-fix.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-plan-validate-card-numbering.py`
- `plugins/mill/unit_tests/test-plan-validate-indent-drift-line.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-verify-baseline.py`
