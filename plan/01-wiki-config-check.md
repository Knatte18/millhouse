# Batch: 01 — wiki-config-mutation check

```yaml
task: '6 (A) — Plan reviewer: detect self-applying layout changes that strand in-flight state'
batch: 01 — wiki-config-mutation check
cards: 3
verify: "uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Implements the full `wiki-config-mutation` check: adds `_parse_creates_only` helper and `_check_wiki_config_mutation` function to `_plan_validate.py`, wires the check into `run()` and updates the module docstring, adds the self-applying layout change criterion to both plan review templates, and adds five unit tests to `test-plan-validate.py`. All changes are in the same logical feature — no downstream batches consume an interface from this batch.

## Cards

### Card 1: Add `_parse_creates_only` and `_check_wiki_config_mutation` to `_plan_validate.py`

- **Reads:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Modifies:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Insert `_parse_creates_only(batch_path: Path) -> set[str]` immediately after `_parse_modifies_only` (before `_parse_deletes_only`). The implementation is a verbatim copy of `_parse_modifies_only` with `"Modifies"` replaced by `"Creates"` in the guard condition and the docstring updated accordingly.

  Insert `_check_wiki_config_mutation(batch_files: list[Path]) -> list[dict]` in a new section between Check 6 and Check 8. The function iterates `batch_files`; for each batch, computes `writes = _parse_modifies_only(batch_path) | _parse_creates_only(batch_path)`. If `"wiki/config.yaml"` is in `writes`, append one error dict: `{"check": "wiki-config-mutation", "batch": batch_path.stem, "card": None, "path": "wiki/config.yaml", "message": "batch modifies or creates wiki/config.yaml — self-applying layout change risk; use --skip-validate if a bootstrap card is present"}`. At most one error per batch regardless of how many fields contain the token.

  Update the module docstring's `Checks performed` list to add:
  `    wiki-config-mutation  — batch Modifies:/Creates: contains wiki/config.yaml (self-applying layout risk)`

  Add the call `errors.extend(_check_wiki_config_mutation(batch_files))` inside `run()` after the `_check_reads_not_backtick_path` call and before `_check_all_files_touched_mismatch`.
- **Commit:** `feat(_plan_validate): add wiki-config-mutation check`

### Card 2: Add self-applying layout change criterion to review templates

- **Reads:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Modifies:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  In `review-plan-batch.md`, add the following bullet to the `## Criteria (apply briefly)` section, after the `- **Integration test reachability**` bullet and before `- **Explore targets**`:
  ```
  - **Self-applying layout change** — BLOCKING if any batch `Modifies:` or `Creates:` `wiki/config.yaml` (the shared config governing where task state lives) without an explicit bootstrap step for the currently-shipping task. A task running under the old layout cannot safely migrate its own state mid-flight.
  ```

  In `review-plan-holistic.md`, add the identical bullet in the `## Criteria (apply to the plan as a whole)` section, after the `- **Integration test reachability**` bullet and before `- **Explore targets**`.

  Both additions must be placed at the identical relative position (after integration test reachability, before explore targets) so the reviewer sees the rule in context with nearby structural concerns.
- **Commit:** `feat(templates): add self-applying layout change criterion to plan review`

### Card 3: Add unit tests for `wiki-config-mutation` check

- **Reads:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
  - `plugins/mill/scripts/_plan_validate.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add the following five test functions to `test-plan-validate.py`, following the existing pattern (return 0 on pass, 1 on fail; print PASS/FAIL to stderr; use tempfile.TemporaryDirectory; call `_plan_validate.run(plan_dir, project_root)`):

  `test_wiki_config_mutation_clean` — batch with `wiki/config.yaml` only in `Reads:` (not in Modifies/Creates) → zero `wiki-config-mutation` errors. Asserts `len(check_errors) == 0`.

  `test_wiki_config_mutation_modifies` — batch with `wiki/config.yaml` in `Modifies:` → exactly one `wiki-config-mutation` error. Asserts shape: `check == "wiki-config-mutation"`, `batch == "01-alpha"` (stem of batch file), `card is None`, `path == "wiki/config.yaml"`.

  `test_wiki_config_mutation_creates` — batch with `wiki/config.yaml` in `Creates:` → exactly one `wiki-config-mutation` error. Same shape assertions.

  `test_wiki_config_mutation_multi_batch` — two batches, each with `wiki/config.yaml` in `Modifies:` → exactly two `wiki-config-mutation` errors (one per batch).

  `test_wiki_config_mutation_modifies_and_creates` — one batch with `wiki/config.yaml` in both `Modifies:` and `Creates:` → exactly one `wiki-config-mutation` error (deduplicated; file-level check, one error per batch).

  For the clean test, pass `wiki/config.yaml` as a `reads` argument to `_make_batch_file`. For dirty tests, pass it as `modifies` and/or `creates`. The batch file used in dirty tests is named `01-alpha.md`; stem is `01-alpha`.

  Register all five new functions in `main()`'s `tests` list, after the existing `test_deletes_*` entries. The list entries are just function references (no invocation parens).

  Do not add a `# Check N` comment section header — the wiki-config-mutation check is an unnumbered addition; use a blank line separator from the preceding tests.
- **Commit:** `test(_plan_validate): add wiki-config-mutation check tests`

## Batch Tests

The batch `verify:` runs `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` from the worktree root. This invokes all `test-*.py` files including the updated `test-plan-validate.py`. The five new test functions validate Card 1's implementation. Card 2 (template changes) has no automated test surface — correctness is validated by the plan review pass that follows implementation.
