# Batch: moves-target-docs-and-messages

```yaml
task: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash
batch: moves-target-docs-and-messages
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: []
```

## Batch Scope

`_plan_validate.py`'s `_check_all_files_touched_mismatch` (the `all-files-touched-mismatch` check) already requires the overview's `## All Files Touched` section to include `Moves:` target paths alongside `Edits:`/`Creates:` — this is intentional, shipped behavior (issue #494, commit `2eed551c`). But three pieces of prose still describe the required set as "Edits + Creates" only: the `plan-overview.md` template, the `mill-plan` SKILL's Step 1.5 fix-table row, and the check's own two runtime error-message strings. This batch corrects all three to match the validator's actual (unchanged) logic. No check logic changes — only prose and message text.

## Cards

### Card 1: Correct plan-overview.md template's All Files Touched wording

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/plan-overview.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## All Files Touched` section (the line immediately following the `## All Files Touched` heading), replace the sentence currently reading exactly:

  `_Full union of every `Creates:` / `Edits:` across every batch, sorted`
  `alphabetically. mill-go reads this to warn if two parallel batches`
  `touch the same file — a sign of a misplaced dependency._`

  with:

  `_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path`
  `across every batch, sorted alphabetically (Move **source** paths are`
  `excluded — they disappear, like `Deletes:` tokens). mill-go reads this`
  `to warn if two parallel batches touch the same file — a sign of a`
  `misplaced dependency._`

  Preserve the surrounding blank lines and the `- `path/to/file.py`` example bullet immediately below unchanged.
- **Commit:** `docs(mill-plan): state All Files Touched includes Moves: target paths`

### Card 2: Correct mill-plan SKILL.md's all-files-touched-mismatch fix-table row

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the Step 1.5 fix table, locate the row whose first column is `all-files-touched-mismatch`. Its current fix-instruction cell reads exactly: "Update the overview's All Files Touched to match the union of every card's Edits: + Creates:. (The overview list is derivative; the cards are the source of truth.)". Replace it with: "Update the overview's All Files Touched to match the union of every card's Edits: + Creates: + Moves: target paths (Move source paths are excluded — they disappear, like Deletes: tokens). (The overview list is derivative; the cards are the source of truth.)". Keep the row's table-cell formatting (leading/trailing pipe alignment) consistent with the other rows in the same table.
- **Commit:** `docs(mill-plan): fix-table row for all-files-touched-mismatch includes Moves targets`

### Card 3: Correct _check_all_files_touched_mismatch's two error-message strings

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_check_all_files_touched_mismatch` (function defined under the `# Check 8 — all-files-touched-mismatch` section banner), there are two `errors.append({...})` blocks that build `"message"` f-strings naming `Edits:`/`Creates:` but omitting `Moves:`:

  1. In the `for p in sorted(overview_set - cards_set):` loop, the message is built as:
     ```
     f"path '{p}' listed in overview's All Files Touched "
     f"but not in any card's Edits: or Creates:"
     ```
     Change the second f-string line to:
     ```
     f"but not in any card's Edits:/Creates:/Moves: target"
     ```

  2. In the `for p in sorted(cards_set - overview_set):` loop, the message is built as:
     ```
     f"path '{p}' in card Edits:/Creates: but missing "
     f"from overview's All Files Touched"
     ```
     Change the first f-string line to:
     ```
     f"path '{p}' in card Edits:/Creates:/Moves: target but missing "
     ```

  Do not change the `"check"`, `"batch"`, `"card"`, or `"path"` keys in either dict, and do not change the check's pass/fail logic (the `overview_set - cards_set` / `cards_set - overview_set` set arithmetic, and the existing `cards_set` computation that already unions `_parse_edits_only`, `compute_creates_union`, and `compute_moves_union`'s target half via `_, move_targets = compute_moves_union(...)`). This card changes message text only.
- **Commit:** `fix(plan-validate): all-files-touched-mismatch messages name Moves: targets`

## Batch Tests

`verify:` runs the existing `test-plan-validate.py` suite (`--only test-plan-validate.py`) to confirm Card 3's message-text edit does not break any existing assertion (no existing test in this suite asserts the old message text verbatim — confirmed during discussion — so this is a pure regression check, not an expected-to-fail-then-fix cycle). Cards 1 and 2 are documentation-only edits to a template and a SKILL.md fix table with no executable surface; they are covered by inspection (the edited wording is given verbatim in each card's Requirements) rather than an automated test.
