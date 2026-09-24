# Batch: plan-review-backend

```yaml
task: Remove batch review (plan-review.batch / code-review.batch)
batch: plan-review-backend
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-cli.py test-review-plan-finalize-round.py test-review-prepare-envelope.py
depends-on: []
```

## Batch Scope

Removes per-batch plan review from the plan-review backend and its CLI, leaving the holistic plan review as the only scope.
`_review_plan.prepare` / `finalize` / `run` lose their batch parameters and per-batch branches; `millpy-review-plan.py` loses `--holistic-only` / `--no-holistic`.
`_review_common.RE_BATCH` and `_review_common.detect_resume_round` stay defined in this batch (batch 4 deletes them); this batch only stops importing them from `_review_plan.py`.
The config keys under `roles.plan-review.batch` stay in the config files until batch 5; after this batch no plan-review code reads them.

## Cards

### Card 1: Strip per-batch plan review from _review_plan.py

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_review_plan.py`:
  - Delete the functions `_scan_approved_batches` and `_review_one_batch` entirely.
  - `prepare`: remove the `scope` keyword parameter and the whole `if scope is not None:` per-batch branch (the one that reads `cfg["roles"]["plan-review"]["batch"]["reviewer"]` and renders the `"review-plan-batch"` template).
    The former `else:` holistic body becomes the function body.
    The returned dict keeps `"scope": "holistic"`.
    Update the docstring: drop the `scope` Args entry and every sentence that describes batch-scope behaviour (e.g. "No-op when `scope is not None`", "both the batch-scope and holistic-scope build_tool_rule calls").
  - `finalize`: remove the `scope` keyword parameter.
    Use the literal `"holistic"` wherever the body used `scope_label`, call `resolve_blocking_classes(cfg, "plan", "holistic")`, and pass `scope="holistic"` to `finalize_scope` / `write_review_file` (both already produce the `<ts>-plan-review-r<N>.md` filename for `"holistic"`, so the file on disk is unchanged).
  - `run`: remove the `holistic_only` and `no_holistic` parameters, their mutual-exclusion check, `batch_max_rounds`, the batch-reviewer resolution (`batch_reviewer_name` / `batch_spec`), and the whole "4. Per-batch parallel section" (rounds-0 stub, mid-round resume via `detect_resume_round`, approved-batch carryforward via `_scan_approved_batches`, and the `ThreadPoolExecutor` fan-out over `_review_one_batch`).
    `max_rounds` now overrides only the holistic round cap.
    Replace the "batch and holistic reviewers are both null" error with a `ReviewError` raised when the holistic reviewer is null: `"plan-review holistic reviewer is null"`.
    The "5. Holistic" section runs unconditionally (drop the `not no_holistic` condition); keep its rounds-0 APPROVE stub, its all-ERROR aggregation, and the `reviewer_override` / `reviews_subdir` / `allow_missing_refs` parameters unchanged.
    Renumber the step comments and rewrite the `run` docstring so it describes a holistic-only review.
  - Remove the now-unused imports (`RE_BATCH`, `detect_resume_round`, `ThreadPoolExecutor` / `as_completed`, and any other name that no longer has a reference after the deletions — check each with a search of the file).
  - Rewrite the module docstring: drop "Per-batch reviews run in parallel via ThreadPoolExecutor", the "this hub disables plan batch review" sentence, and the `scope` parameter from the listed `prepare` / `finalize` signatures; describe `run` as the legacy holistic-only API.

  In `plugins/mill/scripts/_reviewer_test_stub.py`, reword the module-state comment that says ThreadPoolExecutor workers are spawned by `_review_plan.run`: `_review_plan.run` no longer spawns threads, so state the queue is module-level so every reviewer call in a test sees the same seeded queue.
  Leave the code unchanged.
- **Commit:** `refactor(review-plan): drop per-batch plan review from the backend`

### Card 2: Drop scope flags from millpy-review-plan.py

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/millpy-review-plan.py`:
  - Delete the `scope_group` mutually-exclusive argument group and its `--holistic-only` / `--no-holistic` arguments.
  - In the `run(...)` call of the `full` stage, drop the `holistic_only=` / `no_holistic=` keyword arguments.
  - In the `prepare(...)` and `finalize(...)` calls, drop the `scope=None` keyword argument (card 1 removed the parameter).
  - `--max-rounds` help text: "Override roles.plan-review.holistic.rounds for this invocation. Default: use the config value."
  - `--reviewer` help text: drop the sentence "Holistic scope only -- batch-scope reviewer is unaffected."
  - Update the module docstring's flag list to match: remove the `--holistic-only` / `--no-holistic` entries and the batch wording in the `--max-rounds` / `--reviewer` entries.
  - Remove the "# Agent mode uses holistic scope only" comment (there is no other scope).
- **Commit:** `refactor(review-plan): remove --holistic-only and --no-holistic flags`

### Card 3: Update plan-review tests for the holistic-only backend

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-cli.py`
  - `plugins/mill/integration_tests/test-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-review-plan-flow.py`:
  - Delete every test that exercises the per-batch flow: calls to `prepare(..., scope="<batch stem>")`, `run(..., no_holistic=True)`, the `holistic_only` + `no_holistic` mutual-exclusion test, mid-round resume, approved-batch carryforward, and per-batch fan-out counts.
  - Before deleting a per-batch test, check whether a holistic test in the same file already asserts the same behaviour (for example the #733 git-ignored `Context:` soft-fail, `Moves:` source bulking, cross-batch ancestor creates).
    When none does, rewrite that test against the holistic path (`prepare(cfg, SLUG, mill_dir=..., ...)` or `run(...)`) instead of deleting it.
  - Drop `scope=None` from every remaining `prepare(...)` / `finalize(...)` call and `holistic_only=...` from every remaining `run(...)` call.
    Adjust expected prompt counts: a `run` now fires exactly one reviewer call per round.
  - Delete the test asserting `reviewer_override` is a no-op outside holistic scope (test31e); there is no other scope.
  - Update fixtures that seed a `roles.plan-review.batch` block only when the fixture's own assertions depend on it; a leftover block in a fixture cfg dict is harmless.

  In `plugins/mill/unit_tests/test-review-cli.py`, remove the `"batch": {...}` blocks from the fixture `cfg_dict` roles (both the plan-review and code-review fixtures) and remove any `--holistic-only` / `--no-holistic` argument the plan-CLI tests pass.

  In `plugins/mill/integration_tests/test-review-plan.py`, change the assertions to the holistic-only contract: `reviews` has exactly 1 entry whose `scope` is `"holistic"`; drop the `scope='01-core'` check; update the module docstring and the fixture config text so it no longer declares a `batch` reviewer.
  This file needs a live `claude` and is not part of `verify:`; keep it syntactically valid (`python -m py_compile`).
- **Commit:** `test(review-plan): cover the holistic-only plan-review backend`

## Batch Tests

`verify:` runs `test-review-plan-flow.py` (backend prepare/finalize/run), `test-review-cli.py` (plan CLI flags and fixture cfg), `test-review-plan-finalize-round.py` and `test-review-prepare-envelope.py` (both drive `millpy-review-plan.py` stages, so they catch a broken `prepare` / `finalize` call signature).
The integration test needs a live reviewer and only gets a `py_compile` check.
