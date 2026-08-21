# Batch: verdict-derivation-fix

```yaml
task: 'millpy-review-plan: finalize envelope verdict silently diverges from the review file''s own written verdict'
batch: verdict-derivation-fix
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-cli-error-envelope.py
depends-on: []
```

## Prior failure

- Round 1 finalize: `/bin/sh: 1: uv: not found` — environment PATH gap (uv was installed on disk
  but not reachable from the orchestrator shell's PATH), not a card defect. Self-resolved by
  symlinking the existing `uv`/`uvx` binaries into `~/.local/bin` (already on PATH); no plan or
  card edit was needed. Re-firing the implementer fresh for this batch.

## Batch Scope

This batch is the whole task: fix `_review_common.py::finalize_scope()`'s verdict-recomputation
block so a reviewer's own `REQUEST_CHANGES`-with-zero-`BLOCKING` verdict is preserved verbatim
(in both the returned envelope and the persisted review file) instead of being silently
force-downgraded to `APPROVE`, and add the regression tests that lock in both the fix and the
one genuinely-uncovered pre-existing bug (#864's missing-`--agent-output` usage-error
classification). No external interface changes — the function signature and return-dict shape
of `finalize_scope()` are unchanged; only the value it computes for `verdict` in one previously-
buggy branch changes. This is one batch because the fix (card 1) and its regression tests (cards
2-3) are inseparable — a fix with no test proving it is not a complete unit of work here, and all
three cards touch the same narrow, already-fully-explored code region (no other batch's work
depends on or blocks this one).

No batch-local decisions beyond the two `## Shared Decisions` entries in the overview — both
apply to this batch (the only batch).

## Cards

### Card 1: Fix finalize_scope() verdict derivation to stop downgrading non-demoted REQUEST_CHANGES

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `finalize_scope()` (`plugins/mill/scripts/_review_common.py`), replace the
  verdict-recomputation block currently reading exactly:
  ```python
    verdict = original_verdict
    if verdict != "NEED_CONTEXT":
        verdict = "REQUEST_CHANGES" if blocking_count > 0 else "APPROVE"
  ```
  with:
  ```python
      verdict = original_verdict
      if verdict != "NEED_CONTEXT":
          if blocking_count > 0:
              verdict = "REQUEST_CHANGES"
          elif demoted_any:
              verdict = "APPROVE"
  ```
  Do not touch any other line in `finalize_scope()` — the
  `if demoted_any and verdict != original_verdict: raw_text = rewrite_verdict_token(raw_text, verdict)`
  gate immediately below this block, and the `if demoted_any: raw_text = append_demotion_note(...)`
  block after that, are both unchanged and must continue firing exactly as today (this block only
  changes what `verdict` is *set to* in the `blocking_count == 0` branch; it does not change
  `demoted_any`'s computation or either downstream gate's own condition).

  Also update `finalize_scope()`'s own docstring. The paragraph currently reading exactly:
  ```
    The returned `verdict` is recomputed from the post-ceiling findings, per the
    verdict-derives-from-surviving-blocking-count Shared Decision: when `parse_verdict` returned
    `NEED_CONTEXT`, that value passes through unchanged;
    otherwise the returned verdict is `REQUEST_CHANGES` when `blocking_count > 0`, else `APPROVE`.
    The reviewer's own `verdict:` line is advisory only past this point.
  ```
  becomes:
  ```
      The returned `verdict` is recomputed from the post-ceiling findings, per the
      escalate-always-downgrade-only-on-this-call-demotion Shared Decision: when `parse_verdict`
      returned `NEED_CONTEXT`, that value passes through unchanged; when `blocking_count > 0`, the
      verdict is always `REQUEST_CHANGES` (an escalation safety net against a reviewer that
      under-reports its own findings); when `blocking_count == 0` and this call's blocking-class
      ceiling demoted at least one finding (`demoted_any`), the verdict is `APPROVE`; when
      `blocking_count == 0` and `demoted_any` is `False`, the verdict is left as the reviewer's own
      `original_verdict` unchanged (no forced recompute), since there is nothing this call did to
      reconcile.
  ```
- **Commit:** `fix(review): stop force-downgrading REQUEST_CHANGES to APPROVE when blocking_count is zero and no ceiling demotion occurred`

### Card 2: Add verdict-preservation regression tests for the non-demotion downgrade case

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add two new test functions to `test-review-class-taxonomy.py`, placed immediately after
  `test_verdict_token_rewritten_for_plan_and_code_types` (the function ending around the file's
  existing line 560), following the exact helper conventions that function and
  `test_verdict_token_unchanged_when_no_demotion` already use (`_finalize`, `_verdict_yaml`,
  `_verdict_section`, `_heading`, `resolve_blocking_classes`, `RECOGNIZED_CLASSES`):

  1. `test_verdict_preserved_when_reviewer_writes_request_changes_with_zero_blocking() -> bool` —
     for review_type `"discussion"`: build `raw` as
     `_verdict_yaml("REQUEST_CHANGES") + _verdict_section("REQUEST_CHANGES") + _heading("NIT", "consistency", "reviewer judgment call")`
     (a NIT-only response — `blocking_count` is naturally 0 and no ceiling demotion can occur
     regardless of which `blocking_classes` is passed, since there is no `[BLOCKING]` heading to
     demote). Call `_finalize(tmpdir, "discussion", raw, blocking_classes=resolve_blocking_classes({}, "discussion", None))`
     and return the conjunction of: `result["verdict"] == "REQUEST_CHANGES"`,
     `result["blocking_count"] == 0`, `"verdict: REQUEST_CHANGES" in written_text`, and
     `"## Verdict\n\nREQUEST_CHANGES\n<summary>\n" in written_text` — the envelope and the
     persisted file both keep the reviewer's own `REQUEST_CHANGES`, with no rewrite and no
     demotion note.

  2. `test_verdict_preserved_for_plan_and_code_types() -> bool` — mirrors
     `test_verdict_token_rewritten_for_plan_and_code_types`'s two-part structure: a `plan_ok`
     check using `resolve_blocking_classes({}, "plan", "holistic")` for `blocking_classes`, and a
     `code_ok` check using `frozenset(RECOGNIZED_CLASSES)` for `blocking_classes`. Each part
     builds the identical NIT-only `raw` shape from function 1 above (review_type `"plan"` and
     `"code"` respectively) and asserts the same two conditions per part
     (`"verdict: REQUEST_CHANGES" in written_text` and
     `"## Verdict\n\nREQUEST_CHANGES\n<summary>\n" in written_text`). Return `plan_ok and code_ok`.

  Register both new functions in the `TESTS` list near the end of the file, as new `(label,
  test_fn)` tuples inserted immediately after the existing
  `"verdict token rewritten for plan and code review types"` entry, formatted identically to the
  surrounding multi-line tuple entries. Do not modify any existing test function body or any
  existing `TESTS` entry — this card only adds two new functions and two new list entries.
- **Commit:** `test(review): lock in verdict preservation for REQUEST_CHANGES with zero blocking and no demotion`

### Card 3: Add #864 regression test for the missing --agent-output usage-error classification

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Extend the `_run_cli_test` helper method on `TestReviewCliErrorEnvelope` with a new `stage: str
  | None = None` keyword parameter (added after the existing `round_arg: int | None = None`
  parameter). In the argv-building block currently reading exactly:
  ```python
        argv = []
        if cli_name == "plan" and skip_validate_flag:
            argv.append("--skip-validate")
        if round_arg is not None:
            argv.extend(["--round", str(round_arg)])
  ```
  add, immediately after the `round_arg` block:
  ```python
          if stage is not None:
              argv.extend(["--stage", stage])
  ```
  Update the method's own docstring `Args:` list to document `stage` with one line in the same
  style as the existing `round_arg` line (e.g. "stage: when not None, appends '--stage <stage>'
  to argv").

  Add three new test methods to `TestReviewCliErrorEnvelope`, one per CLI, each placed
  immediately after that CLI's existing `..._pre_launch_error_includes_round` test —
  `test_discussion_pre_launch_error_includes_round`, `test_code_pre_launch_error_includes_round`,
  and `test_plan_pre_launch_error_includes_round` respectively (the plan test already exists in
  this file, at lines 333-343 as of plan-writing time — do not skip it):

  - `test_discussion_finalize_missing_agent_output_is_usage_error(self)`
  - `test_code_finalize_missing_agent_output_is_usage_error(self)`
  - `test_plan_finalize_missing_agent_output_is_usage_error(self)`

  Each method calls `self._run_cli_test("<cli_name>", stage="finalize")` — no `backend_return`,
  no `raise_find_slug`, no `round_arg`, and critically no `--agent-output` in argv, which is the
  exact #864 repro (`--stage finalize` invoked with the required `--agent-output` flag omitted
  entirely). Each asserts, on the returned `(exit_code, stdout, stderr)`: `exit_code == 1`;
  `json.loads(stdout)["verdict"] == "ERROR"`; `json.loads(stdout)["round"] == 0`;
  `json.loads(stdout)["reviews"][0]["error_kind"] == "usage"`; and
  `"agent-output required for finalize stage" in stderr`.
- **Commit:** `test(review-cli): cover missing --agent-output finalize usage-error classification`

## Batch Tests

`verify:` runs `run-all.py --only test-review-class-taxonomy.py test-review-cli-error-envelope.py`
— both files this batch touches, plus every pre-existing test in each (in particular
`test_verdict_token_unchanged_when_mismatched_without_demotion`,
`test_verdict_token_rewritten_on_ceiling_flip`, and
`test_demotion_note_appended_when_verdict_flips` in `test-review-class-taxonomy.py`, which lock
in the escalation direction and the ceiling-demotion direction respectively and must continue
passing unchanged — card 1's fix must not touch either). No other test file imports
`finalize_scope`'s verdict-recomputation block directly enough to need inclusion in this batch's
scope; `test-review-common.py`'s `apply_actual_model_override`/cost-metadata tests exercise
`finalize_scope` too but through unrelated code paths (model override, cost injection) this batch
does not change.
