# Batch: batch-verify-list-validation

```yaml
task: Batch verify/baseline/completeness gates produce false positives or time out
batch: batch-verify-list-validation
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Fixes #638: a batch's `verify:` `--only` test-file list can accidentally include a test file unrelated to that batch's own cards, causing a pre-existing failure on the task's parent branch to falsely block a fully-correct batch (`stuck_type: verify`). This batch adds a new deterministic plan-time validator, `_check_verify_unrelated_test_files`, to `_plan_validate.py`'s existing `_check_verify_*` family: for each batch's `verify:` command, any candidate test-file token that is both untouched by that batch's own Files Touched and byte-identical to the task's resolved parent branch (via `_parent_branch.resolve`, NOT a hardcoded `"main"` — this task's own parent is `hanf/linux-port-more`) is flagged for mill-plan to drop from the verify command during Phase: Plan Review's Step 1.5 mechanical-fix pass. This batch is a root batch — it touches `_plan_validate.py`, `millpy-review-plan.py`, and `mill-plan/SKILL.md`, none of which overlap with any other batch in this plan.

## Cards

### Card 11: New validator `_check_verify_unrelated_test_files`

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new function `_check_verify_unrelated_test_files(batch_files: list[Path], project_root: Path, git_root: Path, parent_branch: str | None) -> list[dict]`, placed alongside the existing `_check_verify_*` family (near `_check_verify_not_isolated`, `_check_verify_full_suite`, `_check_verify_malformed_cwd`, `_check_verify_mixed_cwd`). Behavior:
  1. If `parent_branch is None`: return `[]` immediately for all batches — no parent resolved, nothing to diff against, fail-safe no-op (do not guess or fall back to a literal branch name).
  2. For each batch file: parse its `verify:` frontmatter via `_plan_dag.parse_verify_field(frontmatter, project_root, project_root)` exactly as `_check_verify_not_isolated` does (only the command string is needed, not the resolved cwd — pass `project_root` for both `hub_root` and `git_root` args of `parse_verify_field` here, mirroring `_check_verify_not_isolated`'s own call shape). Skip the batch (no findings) if `command is None` or a `ValueError` is raised (malformed cwd mapping — `_check_verify_malformed_cwd` is the sole reporter for that, per the existing convention documented on `_check_verify_not_isolated`).
  3. Extract candidate test-file tokens from the command string: regex-match `--only\s+(.+)$` to capture everything after `--only`, then split on whitespace, keeping tokens matching `^[\w.-]+\.(py|go)$` (stops naturally at the next `--flag`-shaped token, since those don't match the basename pattern). If the command has no `--only` segment, there are no candidate tokens — skip.
  4. Compute this batch's own Files Touched: the union of its `Edits:`, `Creates:`, and `Moves:` target paths (reuse whichever existing per-batch ref-extraction helpers this file already has for those three fields — do not re-parse the batch file with new ad hoc regex when an existing helper already extracts the same data for other checks in this module).
  5. For each candidate token NOT present (by basename match) in that batch's Files Touched: resolve it to an absolute path via `resolve_existing_paths([token], project_root, None, wiki_root=None, git_root=git_root)` (the same helper `_check_non_existent_path` uses). If it resolves to exactly one path: run `git -C <git_root> diff <parent_branch> -- <resolved-path>` via `_subprocess_util.run`. If the diff output is empty (byte-identical to the parent branch): append a finding `{"check": "verify-unrelated-test-file", "batch": batch_path.stem, "card": None, "path": token, "message": f"verify command includes '{token}', which is untouched by this batch's own Files Touched and unchanged vs. parent branch '{parent_branch}' -- likely an unrelated pre-existing test"}`.
  6. This function must never raise — any subprocess failure for an individual token is treated as "cannot confirm identical, don't flag" (skip that token), not a crash.
- **Commit:** `feat(_plan_validate): add verify-unrelated-test-file check for batch verify lists`

### Card 12: Wire the check into `run()`, resolve `parent_branch` at both call sites, add the SKILL.md fix-table row

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. In `_plan_validate.py`: add `parent_branch: str | None = None` as a new keyword parameter to `run()`. Call `_check_verify_unrelated_test_files(batch_files, project_root, effective_git_root, parent_branch)` and extend `errors` with its result, alongside the other `_check_verify_*` calls already in `run()`.
  2. In `millpy-review-plan.py`: at BOTH existing `validate_run(...)` call sites (the `--stage prepare` branch and the `full` branch), resolve `parent_branch` before the call: `status_path = _paths.require_status_path(project_root, cfg)` then `try: parent_branch = _parent_branch.resolve(status_path, interactive=False) except Exception: parent_branch = None` (matching the exact try/except fail-safe shape `millpy-implement.py` already uses for its own `parent_branch` resolution). Pass `parent_branch=parent_branch` as a new keyword argument to both `validate_run(...)` calls.
  3. Do NOT modify `millpy-validate-plan.py` (the separate standalone manual/debugging CLI) — it already omits `git_root` from its own `_plan_validate.run()` call, a pre-existing gap unrelated to this fix; leaving `parent_branch` unresolved there means the new check simply no-ops for that CLI (fail-safe, not a regression), which is acceptable for a lesser-used ad hoc tool.
  4. In `plugins/mill/skills/mill-plan/SKILL.md`'s Step 1.5 fix table, add a new row: `verify-unrelated-test-file` → "Remove the named token (the payload's `path:` field) from the offending batch's `verify:` command frontmatter (identified by the payload's `batch:` field). Log what was dropped and why in the validator-fix commit message, so the drop is auditable rather than silent."
- **Commit:** `fix(review-plan): resolve parent_branch and wire verify-unrelated-test-file check`

### Card 13: Unit tests for `_check_verify_unrelated_test_files`

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `def test_*() -> int` functions (matching this file's existing convention — collected into the `tests` list `main()` already iterates) using the existing in-memory/tempfile git fixture pattern already used by the other `_check_verify_*` tests in this file. Cover: (a) a candidate `--only` token that is NOT in the batch's Files Touched and IS byte-identical to a deliberately-non-`main` parent branch (e.g. a fixture branch named `hanf/some-parent`, exercising the exact discrepancy round 4 of discussion review flagged against this task's own non-`main` parent) → flagged; (b) a candidate token that IS in the batch's Files Touched → not flagged, regardless of parent-branch diff; (c) a candidate token that IS NOT in Files Touched but DIFFERS from the parent branch (legitimately changed by something else, or simply not identical) → not flagged; (d) `parent_branch=None` passed to the check → no findings at all, regardless of any other condition (fail-safe no-op); (e) a `verify:` command with no `--only` segment → no candidate tokens, no findings.
- **Commit:** `test(plan-validate): cover verify-unrelated-test-file against a non-main parent branch`

## Batch Tests

`verify:` (frontmatter above) runs `test-plan-validate.py`, the only test file this batch touches (Card 13's new cases for `_check_verify_unrelated_test_files`).
