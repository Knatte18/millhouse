# Batch: regression-tests

```yaml
task: '_plan_validate: context-completeness fires on forbidding/explanatory file mentions'
batch: regression-tests
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [1]
```

## Batch Scope

Add regression-test coverage for the negation+verb word-set predicate introduced in batch `prohibition-regex-generalization` (Card 1): the 6 previously-untested existing prohibition markers, the new verb/negation combinations the redesign adds, `write`'s irregular inflected forms, and two negative cases (one per conjunct) proving a genuine dependency is not accidentally exempted. One batch, one card — all five test functions exercise the same `_is_prohibition_exempt` predicate and belong in the same file/section as the existing prohibition-marker tests.

## Cards

### Card 3: Add regression tests for the negation+verb prohibition predicate

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/unit_tests/test-plan-validate.py`, add five new test functions immediately after `test_check_context_completeness_clean_prohibition_marker_change_modify` (the function ending `return 1` right before `test_check_requirements_quote_indent_drift_clean_exact_match`). Each function follows the exact structural pattern already used by `test_check_context_completeness_clean_prohibition_marker_change_modify` (a `tempfile.TemporaryDirectory()`, `plan_dir`/`project_root` under it, real placeholder files written to `project_root / "src"`, one `_make_overview([{"name": "alpha", "file": "01-alpha.md"}])`, one `_make_batch_file("alpha", edits=["src/a.py"], requirements=...)`, `_write_plan(plan_dir, overview, [("01-alpha.md", batch)])`, `result = _plan_validate.run(plan_dir, project_root)`, filter `result` to `check == "context-completeness"`, assert, `print("PASS ...")` / `print(f"FAIL ...", file=sys.stderr)`, `return 0`/`return 1`):

  1. `test_check_context_completeness_clean_prohibition_marker_untested_existing` — creates `src/a.py` (the dummy `edits` target) plus `src/m1.py` through `src/m6.py`, and passes `requirements` covering the 6 currently-untested existing markers, one per line:
     ```python
     requirements=(
         "  Implementers must never touch `src/m1.py` as part of this card.\n"
         "  Implementers must not touch `src/m2.py` as part of this card.\n"
         "  Implementers do not touch `src/m3.py` as part of this card.\n"
         "  Reviewers should not touch `src/m4.py` for this card.\n"
         "  This card must never change `src/m5.py`.\n"
         "  This card must never modify `src/m6.py`.\n"
     ),
     ```
     Asserts `len(check_errors) == 0`.

  2. `test_check_context_completeness_clean_prohibition_marker_new_verbs` — creates `src/a.py` plus `src/n1.py` through `src/n5.py`, and passes:
     ```python
     requirements=(
         "  Implementers do not edit `src/n1.py` as part of this card.\n"
         "  Implementers do not add `src/n2.py` as part of this card.\n"
         "  Implementers do not link `src/n3.py` as part of this card.\n"
         "  Implementers do not read `src/n4.py` as part of this card.\n"
         "  Implementers don't touch `src/n5.py` as part of this card.\n"
     ),
     ```
     Asserts `len(check_errors) == 0`.

  3. `test_check_context_completeness_clean_prohibition_marker_write_irregular` — creates `src/a.py` plus `src/w1.py` and `src/w2.py`, and passes:
     ```python
     requirements=(
         "  Implementers do not write to `src/w1.py` as part of this card.\n"
         "  Implementers must not have written `src/w2.py` as part of this card.\n"
     ),
     ```
     Asserts `len(check_errors) == 0`. This is the dedicated regression case for `write`'s irregular inflected forms (`write`/`written`) called out in this task's discussion notes.

  4. `test_check_context_completeness_dirty_prohibition_marker_unrelated_negation_not_exempted` — creates `src/a.py` plus `src/dep.py` (the latter NOT listed in the card's `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:`), and passes:
     ```python
     requirements=(
         "  The parser doesn't stop early; consult `src/dep.py` for the shared logic.\n"
     ),
     ```
     Asserts `len(check_errors) == 1` and `check_errors[0]["path"] == "src/dep.py"`. This proves a line containing a negation word (`doesn't`) but no `_PROHIBITION_VERB_FORMS` match ("stop", "consult", "shared", "logic" are none of the 20 verb bases) does NOT exempt a genuine, unrelated dependency reference — the negative/regression case required by this task's discussion notes.

  5. `test_check_context_completeness_dirty_prohibition_marker_verb_without_negation_not_exempted` — creates `src/a.py` plus `src/dep2.py` (the latter NOT listed in the card's `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:`), and passes:
     ```python
     requirements=(
         "  Read `src/dep2.py` to understand the shared helper.\n"
     ),
     ```
     Asserts `len(check_errors) == 1` and `check_errors[0]["path"] == "src/dep2.py"`. This is the symmetric counterpart to test 4: a line containing a `_PROHIBITION_VERB_FORMS` match (`read`) but no `_PROHIBITION_NEGATIONS` match ("Read", "to", "understand", "the", "shared", "helper" match none of the negation entries) does NOT exempt a genuine, unrelated dependency reference — both conjuncts of the `_is_prohibition_exempt` AND predicate are independently proven necessary.

  Name each function's PASS/FAIL print messages after the function's own name, matching every existing test in this file (e.g. `print("PASS test_check_context_completeness_clean_prohibition_marker_untested_existing")`).

  Then register all five new function names in the `tests` list inside `main()`, inserted immediately after the existing `test_check_context_completeness_clean_prohibition_marker_change_modify,` entry (which sits under the `# context-completeness check (#742)` comment, immediately before the `# requirements-quote-indent-drift check (mill-plan-requirements-byte-exactness-gap)` comment), in the same order as the five function definitions above.
- **Commit:** `test(plan-validate): regression coverage for negation+verb prohibition predicate`

## Batch Tests

`verify:` runs the full `test-plan-validate.py` suite directly (single file, no `--only` needed) — this now includes the 4 new tests plus every pre-existing test in the file, confirming both the new coverage passes and nothing else in the module regressed.
