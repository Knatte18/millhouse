# Batch: plan-validate-deletes

```yaml
task: "Fix agent error recovery, implementer/review false-success contracts, VS Code watcher, and plan-validator Deletes"
batch: "plan-validate-deletes"
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

Fixes issue #494: the `_plan_validate` "all-files-touched-mismatch" check (check 8) requires `Deletes:`-only paths in the overview's "All Files Touched", but the template (`plan-overview.md`) and `mill-plan/SKILL.md` both define that section as `Edits ∪ Creates` only. This batch brings the validator code into line with the already-correct docs and adds the missing regression test. Self-contained; no other batch depends on it.

## Cards

### Card 1: Exclude Deletes-only paths from all-files-touched check

- **Context:**
  - `plugins/mill/templates/plan-overview.md`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `_plan_validate.py`, in the check-8 function `_check_all_files_touched_mismatch`, the `cards_set` union is currently built from `_parse_edits_only(batch_path)`, `_parse_deletes_only(batch_path)`, and `compute_creates_union(...)`. Remove the `cards_set |= _parse_deletes_only(batch_path)` term so the union is `Edits ∪ Creates` only. Do NOT remove the `_parse_deletes_only` function — it is still used by check 1 (`non-existent-path`) and elsewhere; only its call inside `_check_all_files_touched_mismatch` is removed.
  - Update the two error-message strings in the same function so they no longer mention Deletes: the `overview_set - cards_set` message currently reads "...but not in any card's Edits:, Creates:, or Deletes:" — change to "...but not in any card's Edits: or Creates:". The `cards_set - overview_set` message currently reads "path '{p}' in card Edits:/Creates:/Deletes: but missing from overview's All Files Touched" — change to "path '{p}' in card Edits:/Creates: but missing from overview's All Files Touched".
  - In `test-plan-validate.py`, add a regression test for check 8 (place it near the existing `test_check_all_files_touched_mismatch_dirty`). The fixture: a plan whose card has a `Deletes:` path that is NOT in any card's `Edits:`/`Creates:` and is absent from the overview's "All Files Touched" (the git-mv rename shape — `Deletes: old/path`, `Creates: new/path`, with only the created path in All Files Touched). Assert that `_check_all_files_touched_mismatch` produces **zero** `all-files-touched-mismatch` errors for the Delete-only path. The existing check-8 tests (`_clean_no_section`, `_dirty`) must still pass unchanged.
- **Commit:** `fix(plan-validate): exclude Deletes-only paths from all-files-touched check`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-plan-validate.py` (standalone `__main__` runner). It covers all `_plan_validate` checks including the new check-8 Deletes regression and the existing check-1 Deletes-aware tests. Scoped to the single test file because this batch touches only `_plan_validate.py`.
