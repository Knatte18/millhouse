# Batch: docs-and-comments

```yaml
task: "Drop the eager verify-baseline pre-flight"
batch: "docs-and-comments"
number: 6
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-worktree.py test-plan-dag.py test-guards.py
depends-on: [1, 2, 3, 4, 5]
```

## Batch Scope

Removes the mill-go orchestration that drove the pre-flight (`### 0.5. Baseline pre-flight` and the entry-gate speculative launch in `mill-go-base/SKILL.md`), rephrases the present-tense comments that attribute behaviour to removed code, and runs the final repository grep.
Last in the DAG so the grep sees every other batch's result.
The kept done-gate mechanism (`### 0.55. Done-gate baseline pre-flight`, `pipeline.done_gate_baseline_preflight`, `_done_gate.py`) stays; only its cross-references to 0.5 change.

## Cards

### Card 14: Remove the baseline pre-flight from mill-go-base SKILL.md

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `### Entry-gate wait for upstream mill-plan`, delete the `**Speculative baseline launch.**` bullet and all its nested sub-bullets and its fenced bash block (from the bullet line down to, not including, the `Record `wait_started_epoch`` bullet).
  - Delete the section `### 0.5. Baseline pre-flight (first batch of the task only)` in full, from its heading down to (not including) `### 1. Implement`.
  - Rewrite the opening of `### 0.55. Done-gate baseline pre-flight (first batch of the task only)` so it no longer cites 0.5:
    the first sentence becomes "Immediately after "0. Wiki health-check" and before "1. Implement", for the task's **FIRST batch only** (not on every batch — only once per task run), read ..." (drop the "same guard shape as "0.5. Baseline pre-flight" below" clause);
    the skip sentence ends "proceed straight to "1. Implement."" instead of "0.5. Baseline pre-flight."
    Keep the existing semantic line breaks; do not otherwise change 0.55.
  - Then grep `plugins/mill/skills/mill-go-base/*.md` for `0.5.`, `"0.5`, `0.5/`, `baseline-preflight`, `--stage baseline`, `module_verify_baseline`, `verify_baseline_failures`, `Speculative baseline`, `Edit B` and rewrite or delete any surviving reference to the removed step (hits on `0.55` and on the done-gate "baseline" wording are expected and stay).
- **Commit:** `docs(mill-go): remove eager verify-baseline pre-flight steps`

### Card 15: Rephrase present-tense comments that cite removed code

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:**
  - `plugins/mill/scripts/_long_path.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** comment/docstring edits only; no code change.
  - `_long_path.py` module docstring: replace "during verify-baseline teardown" with "during worktree teardown"; the rest stays.
  - `_worktree.py` `_is_retryable_lock_error` docstring: replace "left over from a ``--stage baseline`` verify run" with "left over from a verify run"; keep the "GitHub #1032" reference.
  - `_plan_dag.py` `parse_verify_field` docstring: change "(implementer, fixer, baseline, merge-in, plan-validate)" to "(implementer, fixer, merge-in, plan-validate)".
  - `test-worktree.py`, the comment above the "remove_safe prunes a stale nested-worktree registration" test: replace the "reproduces the exact orphan scenario from GitHub issue tracking `_verify_baseline.py`'s transient nested worktree — a task worktree force-removed mid computation leaves ..." wording with a description of the scenario itself: a nested worktree whose enclosing task worktree was force-removed leaves its administrative entry behind in the hub's common gitdir until `git worktree prune` clears it.
  - `test-worktree.py`, the comment above the "remove_safe passes -c core.longpaths=true" test: drop the trailing ", mirroring _verify_baseline.py's creation-side placement" clause; nothing replaces it.
  - Do not touch `test-long-path.py`, `test-cleanup.py`, `doc/turn-reduction-audit.md` or `plugins/mill/unit_tests/BENCHMARK.md` (historical text, discussion Decision `historical-docs-untouched`).
- **Commit:** `docs: drop references to removed verify-baseline code in comments`

### Card 16: Final grep for leftover references

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-long-path.py`
  - `plugins/mill/unit_tests/BENCHMARK.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - From the worktree root run `grep -rn -E "_verify_baseline|verify_baseline_failures|module_verify_baseline|batch_verify_baseline|baseline_verify_timeout_minutes|stage baseline|recompute-baseline|recompute_baseline|baseline-preflight|_normalize_failure_signature|NONZERO_EXIT|pre-existing-failures" plugins mill-config.yaml`.
  - Allowed hits only: the historical comments in `plugins/mill/unit_tests/test-cleanup.py` and `plugins/mill/unit_tests/test-long-path.py`, `plugins/mill/unit_tests/BENCHMARK.md`, and the absence/rejection assertions the earlier batches added in `test-millpy-implement.py`, `test-millpy-merge-in-subagent.py`, `test-status.py`, `test-millpy-fix.py`, `test-fix-finalize.py`, `test-implementer-common.py`.
  - Any other hit is a defect: report it as stuck with the file and line, naming the batch that owns that file — do not edit here.
  - Also confirm `plugins/mill/scripts/_done_gate.py` still imports `_extract_failure_signatures` and calls it without `returncode`.
- **Commit:** none

## Batch Tests

`verify:` runs `test-worktree.py` (the edited test file), `test-plan-dag.py` (the module whose docstring changed) and `test-guards.py`, which reads `mill-go-base/SKILL.md`.
All three were green on the task branch tip before planning.
`test-long-path.py` is deliberately absent: it is red on `main` and this batch does not edit it; the `_long_path.py` change is docstring-only.
