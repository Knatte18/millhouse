# Batch: plan-validate-verify-cwd

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
batch: plan-validate-verify-cwd
number: 6
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [3]
```

## Batch Scope

Updates `_plan_validate.py`'s verify-command validators for the new `{cwd, command}` mapping form and closes two gaps identified during discussion review: `_check_verify_not_isolated` / `_check_verify_full_suite` currently only inspect `batch_files` (never the overview's module-wide `verify:`), and there is no check today for the mixed-cwd-across-batches conflict that batch 5's holistic-scope fixer joining (Card 20) must reject at runtime — catching it here at plan-review time means a bad plan never reaches the fixer at all. Depends on batch 3 for `parse_verify_field` / `iter_batch_verifies`.

## Cards

### Card 23: Accept the mapping form and add the overview-level check

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In both `_check_verify_not_isolated` and `_check_verify_full_suite`, replace the `verify = parsed.get("verify"); if verify is None or not isinstance(verify, str): continue` guard with a call that also accepts the mapping form: attempt `command, _cwd = _plan_dag.parse_verify_field(parsed, project_root, project_root)` (both roots the same is sufficient here — these checks only need the extracted command string, not the resolved cwd), and on a `ValueError` (malformed mapping) emit the finding described in Card 24 instead of raising; otherwise apply the existing string checks (`PYTHONPATH=` prefix check, `run-all.py --only` filter check) to `command`. Extend both functions to also check the overview file's own `verify:` frontmatter field (previously batch-file-only) using the same `parse_verify_field` extraction, iterating it alongside the existing per-batch loop.
- **Commit:** `feat(plan-validate): accept the verify cwd mapping form and check overview-level verify (#604)`

### Card 24: Add malformed-mapping and mixed-cwd checks

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new check function (e.g. `_check_verify_malformed_cwd(batch_files, overview_path, project_root) -> list[dict]`) that calls `parse_verify_field` on every batch file's frontmatter plus the overview's, catching `ValueError` per file and emitting a finding dict with `check: "verify-malformed-cwd"`, the offending `batch`/`path`, and a `message` quoting the `ValueError` text — surfacing the malformed mapping as a `_plan_validate` finding rather than an uncaught exception, matching how the rest of `_plan_validate.py` reports problems. Add a second new check function (e.g. `_check_verify_mixed_cwd(batch_files, overview_text, project_root, git_root) -> list[dict]`) that mirrors `iter_batch_verifies`'s DAG-order traversal, collects each batch's resolved `cwd` via `parse_verify_field`, and emits a `check: "verify-mixed-cwd"` finding naming the conflicting batches when more than one distinct non-`None` cwd value appears — this is the plan-review-time counterpart to the runtime `ValueError` batch 5's Card 20 raises in the fixer, catching the same conflict before a plan is ever approved. Register both new check functions in `run()`'s `errors.extend(...)` sequence alongside the existing `_check_verify_not_isolated` / `_check_verify_full_suite` calls.
- **Commit:** `feat(plan-validate): add verify-malformed-cwd and verify-mixed-cwd checks (#604)`

### Card 25: Extend test-plan-validate.py

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a case where a batch's `verify` is authored as a valid `{cwd, command}` mapping, asserting `_check_verify_not_isolated` / `_check_verify_full_suite` still validate the extracted `command` string correctly (Card 23). Add a case asserting both validators now also flag a non-compliant overview-level `verify:` (previously silently ignored). Add a case asserting a malformed mapping (invalid `cwd` value, or missing `command` key) surfaces as a `verify-malformed-cwd` finding rather than an uncaught exception (Card 24). Add a case with two batches resolving to mixed `cwd` values, asserting a `verify-mixed-cwd` finding names both conflicting batches (Card 24).
- **Commit:** `test(plan-validate): cover the verify cwd mapping form and new checks (#604)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py` runs the full file, covering all four new/updated cases from Card 25.
