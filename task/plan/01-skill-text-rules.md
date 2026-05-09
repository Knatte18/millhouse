# Batch: skill-text-rules

```yaml
task: 39 (A) — mill-start question-format UX
batch: skill-text-rules
number: 1
cards: 4
verify: null
depends-on: []
```

## Batch Scope

Pure SKILL.md text edits. This batch updates four skill files to enforce the new "(Recommended) = always option 1" rule and adds the question-batch cap to mill-start. There is no runnable surface; the changes are read-only at runtime by Claude when each skill is invoked. The batch is independent of the other two and can be reviewed/merged in any order.

External interface: the `mill-receiving-review` and `mill-go` skills do not consume rules from `conversation/SKILL.md` directly, so no downstream skill needs updating in this batch. Other skills that present numbered menus (`mill-claim` already complies; `mill-groom` is updated in card 3; `mill-ghissues-to-tasks` in card 4) are listed in scope below.

Batch-local decisions: none beyond `## Shared Decisions` in the overview.

## Cards

### Card 1: conversation/SKILL.md — strengthen `(Recommended)` rule

- **Context:**
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/conversation/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/conversation/SKILL.md` under `## User Choices`, replace the existing line 34 bullet that reads `Always use numbered text lists. Print each option as 1) Label — description. Recommended option gets (Recommended) suffix.` with a strengthened version: `Always use numbered text lists. Print each option as 1) Label — description. The recommended option, if any, MUST be option 1; remaining options follow in any order. The (Recommended) suffix appears after the label of option 1.` Do not touch any other lines in the file. Do not change the section heading or any other rule.
- **Commit:** `docs(conversation): require Recommended option to be position 1`

### Card 2: mill-start/SKILL.md — cap each batch at ≤5 questions

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/skills/conversation/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-start/SKILL.md` under the existing `### Phase: Discuss` heading, append a new sentence to the existing introductory paragraph that ends `Prefer multiple-choice (A/B/C with trade-offs) when there are distinct options.` so the paragraph reads `Interview the user relentlessly about every aspect of the task. Ask questions in **focused batches**. Questions that don't depend on each other's answers can be asked together. For each question, provide your **recommended answer**. Prefer multiple-choice (A/B/C with trade-offs) when there are distinct options. Cap each batch at ≤5 questions; ask the rest in subsequent batches after the user answers.` Do not modify the categories list (Scope/Constraints/Architecture/Edge cases/Security/Testing). Do not modify any other Phase heading or the Principles/Board-discipline sections.
- **Commit:** `docs(mill-start): cap question batches at ≤5`

### Card 3: mill-groom/SKILL.md — swap recommended option into position 1

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/skills/conversation/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-groom/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-groom/SKILL.md` under `## Step 4 — Per-task action menu`, the "Otherwise (unmarked, `[s]`)" branch currently shows a fixed-order menu (`1) Keep as-is / 2) Shorten / 3) Fold into <slug> / 4) Drop / 5) Extract to proposal`) and appends `(Recommended)` to whichever option the heuristic picks (lines 122–125). Replace this with a description of a swap-into-position-1 reorder: when the heuristic recommends an option other than `Keep as-is`, the recommended option moves to position 1, and the remaining options retain their relative order from the canonical sequence (Keep / Shorten / Fold / Drop / Extract). Update the bullet list of heuristic→outcome mappings to use the swap form. Provide three concrete example menus inline: (a) heuristic recommends "Drop" → `1) Drop (Recommended) / 2) Keep as-is / 3) Shorten / 4) Fold into <slug> / 5) Extract to proposal`; (b) heuristic recommends "Extract" → `1) Extract to proposal (Recommended) / 2) Keep as-is / 3) Shorten / 4) Fold into <slug> / 5) Drop`; (c) no heuristic recommendation → menu unchanged at `1) Keep as-is / 2) Shorten / 3) Fold / 4) Drop / 5) Extract`. The "On user selection" sub-list directly below must continue to map decisions by name (Keep/Shorten/Fold/Drop/Extract), not by fixed number, since the number now varies. Update the bullet labels (currently `` `1` (Keep) ``, `` `2` (Shorten) ``, etc.) to use names instead: `Keep`, `Shorten`, `Fold`, `Drop`, `Extract`. Do not touch Step 1, Step 2, Step 3, or Step 5+.
- **Commit:** `docs(mill-groom): swap recommended option into position 1`

### Card 4: mill-ghissues-to-tasks/SKILL.md — recommended always at position 1

- **Context:**
  - `task/discussion.md`
  - `plugins/mill/skills/conversation/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` line 58 (the bullet that reads `Append (Recommended) to option 1 if there is no obvious overlap with current Home.md tasks; to option 2 if the title or first paragraph overlaps with an existing entry (assistant judgement, not a hard heuristic).`), replace the conditional with a position-1-always rule: when the issue does not overlap with any current Home.md task, present the menu as `1) New task (Recommended) / 2) Fold into <slug>`; when it overlaps, swap the order so it reads `1) Fold into <slug> (Recommended) / 2) New task`. The recommended option is always at position 1; the conditional decides which content lands there. Keep the "assistant judgement, not a hard heuristic" caveat about how overlap is detected. Do not modify any other section of this file.
- **Commit:** `docs(mill-ghissues): make Recommended option always position 1`

## Batch Tests

Pure docs batch with no runnable surface — `verify: null`. The reviewer reads the four files and the updated rules to confirm wording is unambiguous and consistent. No unit test, no integration test, no manual verification step.
