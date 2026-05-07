# Batch: validator-skip-checks

```yaml
task: '28 (A) — review-plan robustness'
batch: validator-skip-checks
number: 2
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Implement bug E's backend change in `_plan_validate.py`: add a `skip_checks` parameter to `run()` that filters named checks from the result, and update the error message in `_check_wiki_config_mutation` to reference `--skip-check wiki-config-mutation` instead of `--skip-validate`. Add tests in `test-plan-validate.py`.

This batch delivers the updated `_plan_validate.py` with the new `skip_checks: frozenset[str] = frozenset()` parameter. Batch 3 depends on this to call `_plan_validate.run(..., skip_checks=...)`.

## Cards

### Card 5: Bug E — add skip_checks parameter to _plan_validate.run()

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_plan_validate.py`:
  1. Change the `run()` signature from `run(plan_dir: Path, project_root: Path, *, root: str | None = None, wiki_root: Path | None = None) -> list[dict]` to `run(plan_dir: Path, project_root: Path, *, root: str | None = None, wiki_root: Path | None = None, skip_checks: frozenset[str] = frozenset()) -> list[dict]`.
  2. After the existing `errors.sort(key=lambda e: (e["batch"] or "", e["card"] or 0, e["check"]))` line (currently the last statement before `return errors`), add: `if skip_checks: errors = [e for e in errors if e["check"] not in skip_checks]`.
  3. Return `errors` (unchanged).
  4. Update the module-level docstring Public API line to: `run(plan_dir, project_root, *, root=None, wiki_root=None, skip_checks=frozenset()) -> list[dict]`.
- **Commit:** `feat(_plan_validate): add skip_checks parameter to run() (#188)`

### Card 6: Bug E — update wiki-config-mutation error message

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_check_wiki_config_mutation()`, find the error message string `"use --skip-validate if a bootstrap card is present"` and change it to `"use --skip-check wiki-config-mutation if a bootstrap card is present"`. This is in the `errors.append({...})` call inside `_check_wiki_config_mutation`. The full message after the change should read: `"batch edits or creates wiki/config.yaml — self-applying layout change risk; use --skip-check wiki-config-mutation if a bootstrap card is present"`.
- **Commit:** `fix(_plan_validate): update wiki-config-mutation error message to --skip-check (#188)`

### Card 7: Tests — skip_checks filtering in test-plan-validate.py

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add three test cases to `test-plan-validate.py`. Study the existing fixture helpers (`_make_overview`, `_make_batch_file`, `_write_plan`) and the test structure in that file before writing. Add after the existing tests:

  **Test: skip_checks filters wiki-config-mutation**
  Create a plan with one batch where the batch file has `wiki/config.yaml` in Edits: (use `edits=["wiki/config.yaml"]` in `_make_batch_file`). Create `wiki_dir = tmp / "wiki"`, `wiki_dir.mkdir()`, and write a placeholder `(wiki_dir / "config.yaml").write_text("# placeholder", encoding="utf-8")` (matches pattern in `test_wiki_config_mutation_modifies`). Call `_plan_validate.run(plan_dir, project_root, wiki_root=wiki_dir, skip_checks=frozenset({"wiki-config-mutation"}))`. Assert result is an empty list (no errors).

  **Test: skip_checks does not suppress other checks**
  Create a plan with one batch that has `wiki/config.yaml` in Edits: AND is also missing the `Commit:` field (use `missing_fields={"Commit"}` in `_make_batch_file`). Create `wiki_dir` and `wiki_dir / "config.yaml"` as above. Call `run(..., skip_checks=frozenset({"wiki-config-mutation"}))`. Assert the result has exactly one entry with `check == "card-missing-field"` (wiki-config-mutation is suppressed; card-missing-field is not).

  **Test: unknown check name in skip_checks is silently ignored**
  Use a clean plan (no violations). Call `run(..., skip_checks=frozenset({"nonexistent-check"}))`. Assert no exception is raised and result is empty.

  Use `tempfile.TemporaryDirectory()` + `_write_plan()` for each test. Follow the same try/except/return-int pattern as existing tests in the file. Add them to the runner's test list at the bottom of the file.
- **Commit:** `test(_plan_validate): add skip_checks filtering tests (#188)`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` runs all unit tests. Relevant tests in `test-plan-validate.py`:
- New skip_checks tests (3 new)
- All existing tests must pass (regression check)
