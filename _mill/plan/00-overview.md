# Plan: Improve diagnosability of plan-validate errors and finalize verify-replay failures

```yaml
task: Improve diagnosability of plan-validate errors and finalize verify-replay failures
slug: mill-validate-verify-diagnostics-gaps
approved: false
started: '2026-08-02T16:31:04Z'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: plan-validate-line-field
    file: 01-plan-validate-line-field.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
  - number: 2
    name: plan-validate-line-field-tests
    file: 02-plan-validate-line-field-tests.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
  - number: 3
    name: status-batch-baseline-field
    file: 03-status-batch-baseline-field.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
  - number: 4
    name: implementer-common-signature-diff
    file: 04-implementer-common-signature-diff.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py
  - number: 5
    name: verify-baseline-refactor
    file: 05-verify-baseline-refactor.md
    depends-on: [4]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-verify-baseline.py
  - number: 6
    name: baseline-stage-wiring
    file: 06-baseline-stage-wiring.md
    depends-on: [3, 4, 5]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-implement.py
  - number: 7
    name: baseline-waiver-integration-test
    file: 07-baseline-waiver-integration-test.md
    depends-on: [6]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-baseline-waiver.py
```

## Shared Decisions

### Decision: two unrelated gaps share one plan but never share code

- **Decision:** Gap 1 (`_plan_validate.py`'s context-completeness `line` field, batch 1) and Gap 2 (per-batch verify baseline, batches 2-6) touch entirely disjoint file sets and have no runtime dependency on each other. Batch 1 has `depends-on: []` and can run in any order relative to the others.
- **Rationale:** `_mill/discussion.md` documents both gaps as independent diagnosability fixes filed from separate GitHub issues (#772, #770) and folded into one task only for scheduling convenience.
- **Applies to:** batch 1 vs. batches 2-7.

### Decision: fail-safe default is always "strict" when baseline state is missing or ambiguous

- **Decision:** Every new gate this plan introduces (per-batch `verify_baseline_failures` subset-diff) treats an absent, `None`, or empty baseline, or an absent/empty replay `signatures` list, as "never waived — block as today." A waiver only fires on a non-vacuous subset match.
- **Rationale:** Mirrors the existing `module_verify_baseline` fail-safe direction: a false "clean" merely costs one over-strict gate later; a false waiver would silently mask a genuine regression. See `_mill/discussion.md`'s `gap2-subset-diff-semantics` and `gap2-signatures-field-on-stuck-dict` Decisions.
- **Applies to:** batches 4, 5, 6.

### Decision: raw (unnormalized) failure lines are for humans; normalized lines are for comparison only

- **Decision:** `_extract_failure_signatures` always returns raw, verbatim lines. Normalization (stripping volatile duration substrings via `_normalize_failure_signature`) is a separate step applied ONLY when building or comparing baseline/finalize signature sets — never applied to the human-facing truncation excerpt or to what gets stored/displayed as `signatures` on a stuck dict.
- **Rationale:** Comparing raw lines would make a genuinely pre-existing failure almost never string-match between runs (different elapsed time each run), defeating the subset-diff; but a human reading a stuck reason wants the real line, not a scrubbed one.
- **Applies to:** batch 4 (extraction/normalization helpers, verify-gate signatures field), batch 5 (per-batch baseline storage).

### Decision: one shared parent-branch checkout for module-wide and every per-batch verify command

- **Decision:** `--stage baseline` performs exactly one transient parent-branch checkout per invocation whenever the module-wide command AND at least one per-batch command both need computing this invocation — the module-wide command is computed via `_run_module_wide_verify_algorithm` directly against that shared checkout, bypassing `compute_baseline` entirely (which would re-checkout). When only per-batch commands need computing (module-wide is unconfigured or already cached), the shared checkout still covers all of them. When only the module-wide command needs computing (no per-batch work this invocation), the existing standalone `compute_baseline` path runs unchanged — there is nothing to share a checkout with. Dependency-junction linking happens once per distinct effective cwd fragment actually present (at most two: git_root-anchored, hub-anchored).
- **Rationale:** Checkout + junction setup is the expensive part of the mechanism; batching avoids N+1 checkouts. See `_mill/discussion.md`'s `gap2-shared-transient-checkout` and `gap2-checkout-teardown-extraction` Decisions.
- **Applies to:** batches 5, 6.

### Decision: per-batch computation failures are isolated; only shared-setup failures are not

- **Decision:** Each batch's own verify-command computation is wrapped in its own try/except so one batch's infrastructure failure never aborts sibling batches or the module-wide sub-step. The ONE exception is the shared checkout/junction-linking setup, which runs once for the whole per-batch sub-step and is caught once — its failure marks every batch needing computation as errored.
- **Rationale:** See `_mill/discussion.md`'s `gap2-per-batch-computation-failure-isolation` Decision.
- **Applies to:** batch 6.

### Decision: no change to `module_wide_verify_cmd`'s existing binary contract

- **Decision:** The existing module-wide baseline mechanism (`compute_baseline`'s `"clean"`/`"pre-existing-failures"` binary verdict, its 3-run/control-check corroboration) is reused via extraction, never replaced or reshaped. The new per-batch mechanism is a parallel, differently-shaped addition (signature-set union-of-two-runs, not a binary verdict).
- **Rationale:** Scope explicitly excludes changing `module_wide_verify_cmd` semantics; see `_mill/discussion.md`'s Scope "Out" list and the `gap2-shared-transient-checkout` Decision's rejected alternatives.
- **Applies to:** batches 4, 5.

## All Files Touched

- `plugins/mill/integration_tests/test-baseline-waiver.py`
- `plugins/mill/scripts/_implementer_common.py`
- `plugins/mill/scripts/_plan_validate.py`
- `plugins/mill/scripts/_status.py`
- `plugins/mill/scripts/_verify_baseline.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/unit_tests/test-implementer-common.py`
- `plugins/mill/unit_tests/test-plan-validate.py`
- `plugins/mill/unit_tests/test-millpy-implement.py`
- `plugins/mill/unit_tests/test-status.py`
- `plugins/mill/unit_tests/test-verify-baseline.py`
