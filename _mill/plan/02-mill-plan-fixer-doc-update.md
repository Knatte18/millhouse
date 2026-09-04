# Batch: mill-plan-fixer-doc-update

```yaml
task: "_plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens"
batch: mill-plan-fixer-doc-update
number: 2
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
depends-on: [1]
```

## Batch Scope

`mill-plan/SKILL.md`'s Step 1.5 fixer-remediation table has a `context-completeness` row instructing the fixer to "add the referenced file" to a card's `Context:` list, sourcing the file from the finding's `path` field. That instruction is path-branch-specific: batch 1's new symbol branch keeps `path` as the original symbol token (never a file — e.g. `` `SaveState()` ``), and instead carries the resolved declaring file inside `message`, in the exact format decided in `_mill/discussion.md`'s "Fixer-remediation message format for symbol findings" Decision: `"...which resolves to '<resolved_relative_path>' -- not in this card's..."`. This batch updates the fixer row to branch on that message shape so a future `mill-plan` run's Step 1.5 auto-fix (and the docstring readers who rely on this table) reference the correct field for each case. This is a doc-only change with no functional dependency on batch 1's code, but depends on it logically — the message format wording batch 1 establishes is exactly what this batch's row text asserts, so it lands second.

## Cards

### Card 4: Update the context-completeness fixer row for the symbol case

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-plan/SKILL.md`'s Step 1.5 fix table (currently line 362), replace the `context-completeness` row's cell text with wording that branches on the finding's `message` shape, per this task's discussion notes' "Fixer-remediation message format for symbol findings" decision (the exact format is restated in full below, so no other file needs to be read to apply it):

  - When `message` contains the substring `"which resolves to '"` (the symbol case — e.g. `"card 3's Requirements: references symbol 'SaveState()', which resolves to 'internal/state.go' -- not in this card's Context:/Edits:/Creates:/Deletes:/Moves:-source"`): extract the quoted text between `"which resolves to '"` and the next `"'"` (in the example, `internal/state.go`) and add that path to the card's `Context:` list — NOT the finding's `path` field, which holds the original symbol token text (e.g. `SaveState()`), never a file.
  - Otherwise (the existing path case — `message` containing `"references '...' which is not in..."`, no `"which resolves to '"` substring): keep today's unchanged instruction — add the referenced file from the finding's `path` field to the card's `Context:` list (unless the card's own `Edits:`/`Creates:`/`Deletes:`/`Moves:`-source already covers it, in which case re-verify the check's own-list cross-reference before editing — the "add to Context:" remedy applies only when the token is absent from all five fields; a token that legitimately belongs to `Deletes:`/`Moves:`-source means the check should not have fired at all).
  - Keep the existing final sentence about the `line` field carrying the exact offending `Requirements:` line, applying to both cases unchanged.

  Do not touch any other row in the Step 1.5 fix table, and do not touch the `context-completeness` row's position within the table.
- **Commit:** `docs(mill-plan): branch the context-completeness fixer row on symbol vs path findings`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-skill-helper-drift.py`, the existing SKILL.md regression-lock suite (scans every mill-`SKILL.md` helper reference and locks several specific skill-doc invariants) — a cheap, relevant sanity check for a `SKILL.md` edit, even though this card's change is prose-only (a fix-table cell) and adds no new `_<module>.<fn>(`-shaped helper reference for the drift guard to newly validate. No other test file is affected by this batch.
