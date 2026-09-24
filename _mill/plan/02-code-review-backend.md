# Batch: code-review-backend

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
batch: code-review-backend
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-review-cli.py test-review-cli-error-envelope.py test-review-finalize.py
depends-on: [1]
```

## Batch Scope

Removes per-batch code review from the code-review backend and its CLI, together with the machinery only per-batch review used: the `start_sha` diff-scoping and the advisory rename-NIT check (`_moves_check.py`).
`_review_code.prepare` / `finalize` lose `scope`; `_review_code.run` loses `batch_name`; `millpy-review-code.py` loses `--batch`.
`_review_common.bulk_files_with_diff` loses its only caller here; batch 4 deletes it.

## Cards

### Card 4: Strip per-batch code review from _review_code.py

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/scripts/_moves_check.py`
  - `plugins/mill/unit_tests/test-moves-check.py`
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_review_code.py`:
  - `_collect_batch_files`: drop the `batch_name` and `overview_path` parameters and the single-batch lookup; it returns every `NN-<name>.md` file in `plan_dir` except `00-overview.md`, as its `batch_name=None` branch does today.
    Update its two former call sites.
  - `_build_artefact_section`: drop the `start_sha`, `diff_threshold` and `project_root` keyword parameters and the `bulk_files_with_diff` branch; source files are always bulked in full (the existing non-diff path).
    Keep `roots`.
  - `prepare`: remove the `scope` keyword parameter and every `scope is not None` branch — the `roles.code-review.batch.rounds` round-cap lookup, the status.md `start_sha` read and the `diff_scope_threshold` read, the `roles.code-review.batch.reviewer` lookup, the `"review-code-batch"` template choice and the `batch_name` prompt token.
    The round is `discover_round(reviews_dir, "code", "holistic")`, the round cap is `roles.code-review.holistic.rounds` (still overridable by `max_rounds`), the reviewer is `roles.code-review.holistic.reviewer`, the template is `"review-code-holistic"`, and the returned dict carries `"scope": "holistic"`.
    Update the docstring.
  - Delete `_splice_rename_nit_findings` and `_insert_nit_blocks_before_verdict` (the latter's only caller is the former; confirm with a search of the file), and the `import _moves_check` line.
  - `finalize`: remove the `scope` keyword parameter and the `if scope is not None:` rename-splice call.
    Use `"holistic"` for the scope label, call `resolve_blocking_classes(cfg, "code", "holistic")`, and pass `scope="holistic"` to `finalize_scope` / `write_review_file`.
    Drop the docstring paragraph about the per-batch rename NIT check.
  - `run`: remove the `batch_name` parameter and its branches (batch round-cap lookup, batch reviewer lookup, the `bulk_timeout` choice — always `cfg["llm"]["holistic_timeout"]`); drop `scope=batch_name` from the `prepare`, `finalize` and `write_review_file` calls inside it (pass `scope="holistic"` to `write_review_file`).
  - Remove imports left without a reference (`_status`, `extract_batch_index`, `PlanDAGError`, `bulk_files_with_diff`, `re`, `_subprocess_util` — check each with a search of the file before removing; these are import names only, no file read needed).
  - Rewrite the module docstring: drop the `bulk_files_with_diff` / `start_sha` bullet, the mechanical-rename-check bullet and the "Two modes, selected by `scope`" section; list `prepare` / `finalize` / `run` with their new signatures.

  Delete `plugins/mill/scripts/_moves_check.py` and its test `plugins/mill/unit_tests/test-moves-check.py`.
- **Commit:** `refactor(review-code): drop per-batch code review, diff-scoping and rename check`

### Card 5: Drop --batch from millpy-review-code.py

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/millpy-review-code.py`:
  - Delete the `--batch` argument and the "Guard for per-batch reviews" block that calls `_paths.require_status_path` only when `args.batch` is set (remove the `_paths.TaskHubError` handling with it if nothing else uses it).
  - In the `prepare` stage, delete the unused local `scope = args.batch or "holistic"` and drop `scope=args.batch` from the `prepare(...)` call; drop `scope=args.batch` from the `finalize(...)` call and `batch_name=args.batch` from the `run(...)` call.
  - `--max-rounds` help and the module docstring: "Override roles.code-review.holistic.rounds for this invocation. Default: use the config value."
  - Remove the `--batch` entry from the module docstring's flag list.
- **Commit:** `refactor(review-code): remove the --batch flag`

### Card 6: Update code-review tests for the holistic-only backend

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
  - `plugins/mill/unit_tests/test-review-finalize.py`
  - `plugins/mill/integration_tests/test-go-assets.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-review-code-flow.py`:
  - Delete the tests that exercise per-batch code review: `prepare(..., scope="<batch>")`, `run(..., batch_name=...)`, the `start_sha` diff-scoped prompt test (test33, the `bulk_files_with_diff` branch), and the rename-NIT splice tests (the ones around `_splice_rename_nit_findings`, e.g. Test 25).
  - Before deleting a per-batch test, check whether a holistic test in the file already asserts the same behaviour; when none does and the behaviour still exists on the holistic path (not diff-scoping or the rename check, which are gone), rewrite the test against the holistic path instead.
  - Drop `scope=None` / `scope="holistic"` from every remaining `prepare(...)` / `finalize(...)` call.

  In `plugins/mill/unit_tests/test-review-cli-error-envelope.py`, change the mocked `ReviewResult` review entries' `"scope": "batch"` to `"scope": "holistic"`, and remove any `--batch` argument passed to the code CLI.

  In `plugins/mill/unit_tests/test-review-finalize.py`, update the comment that describes the `finalize` positional/keyword shape so it no longer lists `scope=None`.

  In `plugins/mill/integration_tests/test-go-assets.py`, convert the per-batch `_review_code.run(..., batch_name="foundation")` end-to-end test to a holistic run: drop `batch_name`, glob for `*-code-review-r1.md`, and change the PASS message's "(per-batch)" to "(holistic)".
  This file is not part of `verify:`; keep it syntactically valid (`python -m py_compile`).
- **Commit:** `test(review-code): cover the holistic-only code-review backend`

## Batch Tests

`verify:` runs `test-review-code-flow.py` (backend), `test-review-cli.py` and `test-review-cli-error-envelope.py` (code CLI) and `test-review-finalize.py` (CLI finalize stage for both review types).
`test-moves-check.py` is deleted with the module it tested.
The integration test only gets a `py_compile` check.
