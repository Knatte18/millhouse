# Batch: cli-skip-checks

```yaml
task: '28 (A) — review-plan robustness'
batch: cli-skip-checks
number: 3
cards: 3
verify: python plugins/mill/unit_tests/run-all.py
depends-on: [2]
```

## Batch Scope

Add `--skip-check <CHECK>` (repeatable) to both `millpy-review-plan.py` and `millpy-validate-plan.py`, forwarding the collected names to `_plan_validate.run(skip_checks=frozenset(...))`. Add CLI-level tests in `test-millpy-validate-plan.py`.

This batch depends on batch 2 for the `skip_checks` parameter in `_plan_validate.run()`. Batch 4 (SKILL.md) depends on this batch so that `--skip-check wiki-config-mutation` is a real CLI flag when SKILL.md references it.

## Cards

### Card 8: Bug E — add --skip-check flag to millpy-review-plan.py

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-review-plan.py`'s `main()`:
  1. Add this argparse argument after the `--skip-validate` argument:
     ```python
     parser.add_argument(
         "--skip-check",
         action="append",
         dest="skip_checks",
         default=[],
         metavar="CHECK",
         help="Skip a named validator check (repeatable). Silently ignores unknown names.",
     )
     ```
  2. In the `if not args.skip_validate:` block where `validate_run(plan_dir, project_root, wiki_root=wiki_root)` is called, change the call to: `errors = validate_run(plan_dir, project_root, wiki_root=wiki_root, skip_checks=frozenset(args.skip_checks))`.
  3. Update the module docstring Flags section to add: `--skip-check <CHECK>  Skip a named validator check (repeatable). Silently ignores unknown names.`
- **Commit:** `feat(millpy-review-plan): add --skip-check flag (#188)`

### Card 9: Bug E — add --skip-check flag to millpy-validate-plan.py

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-validate-plan.py`'s `main(argv=None)`:
  1. Add `import argparse` at the top of `main()` (or at module level).
  2. Create a parser: `parser = argparse.ArgumentParser(description="Run the static plan pre-validator for the active task.")`.
  3. Add the same `--skip-check` argument as card 8.
  4. Parse: `args = parser.parse_args(argv)`.
  5. Change the existing `_plan_validate.run(plan_dir, project_root, wiki_root=wiki_root)` call to: `_plan_validate.run(plan_dir, project_root, wiki_root=wiki_root, skip_checks=frozenset(args.skip_checks))`.
  6. Update the module docstring: replace `No flags.` with `Flags: --skip-check <CHECK>  Skip a named validator check (repeatable). Silently ignores unknown names.`
- **Commit:** `feat(millpy-validate-plan): add --skip-check flag (#188)`

### Card 10: Tests — --skip-check CLI flag in test-millpy-validate-plan.py

- **Context:**
  - `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-validate-plan.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add two test functions to `test-millpy-validate-plan.py`. Study the existing test helpers `_make_overview`, `_make_batch_file`, `_write_plan`, and `test_cli_clean_exits_zero_no_findings` for the mock-patch pattern used to invoke `_vp_mod.main()`. Add after existing tests:

  **Test: --skip-check suppresses target check**
  Create a plan with one batch that has `wiki/config.yaml` in Edits: (add an `edits` kwarg to `_make_batch_file` — if that helper doesn't support it, write the batch file text directly with `- **Edits:** \`wiki/config.yaml\``). Invoke `_vp_mod.main(["--skip-check", "wiki-config-mutation"])`. Assert: return code is 0; JSON `errors` list is empty. Use the same `unittest.mock.patch` context as existing tests.

  **Test: multiple --skip-check flags suppress multiple checks**
  Create a plan with one batch that has `wiki/config.yaml` in Edits: AND is missing the `Commit:` field. Invoke `_vp_mod.main(["--skip-check", "wiki-config-mutation", "--skip-check", "card-missing-field"])`. Assert: return code is 0; JSON `errors` list is empty.

  Add both new tests to the `tests` list in `main()` at the bottom of the file. Follow the same try/except return-int pattern as existing test functions.
- **Commit:** `test(millpy-validate-plan): add --skip-check CLI tests (#188)`

## Batch Tests

`verify: python plugins/mill/unit_tests/run-all.py` runs all unit tests. Relevant tests in `test-millpy-validate-plan.py`:
- New `--skip-check` CLI tests (2 new)
- Existing tests must pass (regression check)
