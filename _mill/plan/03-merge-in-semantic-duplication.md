# Batch: merge-in-semantic-duplication

```yaml
task: "Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure"
batch: "merge-in-semantic-duplication"
number: 3
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Fixes #718: the conflict-resolution sub-agent can resolve a conflict by keeping both sides when the correct resolution is recognizing one side moved content that shouldn't be re-added. This batch adds a two-branch instruction (confident-drop vs. ambiguous-keep-both) to `merge-in-conflict-brief.md`, extends its Report section so the ambiguous outcome is reachable and surfaced via the existing `discarded` field, and generalizes `mill-merge-in/SKILL.md` Step 3's operator-facing wording so it correctly describes a kept-both entry (nothing lost, risk is duplication) rather than only a drop (something lost). Per `_mill/discussion.md`'s `merge-in-semantic-duplication (#718)` Decision, this is prompt/prose content, not unit-testable — verified by inspection of the two worked examples this batch adds. No other batch touches either file.

## Cards

### Card 12: Add the move-vs-duplicate instruction with two branches and two worked examples

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Instructions` section of `plugins/mill/templates/merge-in-conflict-brief.md`, add a new numbered instruction immediately after the existing step 3 ("combine both edits" for disjoint-region conflicts, currently the paragraph ending in "it does not discard either"). The new instruction: before keeping content from either side inside a conflict hunk, search the rest of the file (outside the hunk) for that same content, with two explicit branches:
  - **Confident case:** if the content clearly already exists elsewhere and the surrounding context makes it unambiguous that this is the same item having been moved (not two independent, separately-intended copies) — do not re-add it in the hunk; keep only the other side's unrelated edit.
  - **Ambiguous case:** if you cannot confidently tell whether this is the same moved content or a legitimate independent duplication — fall back to step 3's existing default (keep both) rather than guessing, and report the ambiguity via the `discarded` field (see Report section) with the description `"kept both sides of a conflict, ambiguous move-vs-duplicate"`.
  Make explicit that this instruction is scoped to this specific judgment call only — it does NOT apply to every ordinary step-3 disjoint-region combine (e.g. the column-A/column-B worked example already in step 3), which remains today's silent, high-confidence success path. Add two worked examples directly beneath the new instruction, mirroring step 3's existing "if `ours` changes column A and `theirs` changes column B..." example style: (1) confident case — a roadmap item that moved from a `## Planned` section to a `## Done` section on one side while the other side made an unrelated edit elsewhere in the file; the resolution keeps the item only in `## Done`, not re-added under `## Planned`. (2) ambiguous case — a similarly-worded item appears in two different sections and the sub-agent cannot tell whether it is the same item moved or a legitimate second, independently-added item; the resolution keeps both occurrences and reports the ambiguity via `discarded`.
- **Commit:** `feat(merge-in): add move-vs-duplicate instruction with confident/ambiguous branches (#718)`

### Card 13: Extend the Report section so the ambiguous kept-both outcome is a documented `discarded` shape

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/merge-in-conflict-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Report` section of `plugins/mill/templates/merge-in-conflict-brief.md` (the `discarded` field description, currently "if you had to drop content from one side... list each dropped item"), add a sentence documenting that `discarded` also carries the Card 12 ambiguous-case entry `"kept both sides of a conflict, ambiguous move-vs-duplicate"` even though nothing was technically dropped in that case — the field's purpose is "surface anything the operator should double-check before `git merge --continue`," which covers both a genuine drop and a kept-both ambiguity. Do not change the field's JSON key or shape (still a list under `"discarded"` on a `{"status":"success",...}` envelope) — only the prose description of what may populate it.
- **Commit:** `docs(merge-in): document the ambiguous kept-both discarded entry in the brief's report contract (#718)`

### Card 14: Generalize `mill-merge-in/SKILL.md` Step 3's operator-facing `discarded` wording

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-merge-in/SKILL.md`'s Step 3 "Real code conflicts" table row (line 73), the current operator-facing wording — "report each discarded item and recommend a manual diff against the parent branch (`git diff <parent-branch>..HEAD`) to verify nothing load-bearing was lost" — is accurate for a genuine drop but wrong for a Card 12 ambiguous kept-both entry (nothing was lost in that case; the risk is duplication/self-contradiction). Generalize the wording so it covers both, based on each `discarded` entry's own description: for a drop-shaped entry, keep the existing "verify nothing load-bearing was lost" guidance; for a kept-both/ambiguous-shaped entry (identifiable by its `"kept both sides..."` description text from Card 12), instead recommend checking the resolved file for duplication or self-contradiction between the two kept occurrences. Keep the rest of the row's dispatch/success/stuck-handling prose unchanged — only the operator-facing recommendation sentence changes.
- **Commit:** `docs(mill-merge-in): generalize discarded-field operator guidance for drop vs. kept-both cases (#718)`

## Batch Tests

Not unit-testable — both edited files are prose (an LLM prompt template and a SKILL.md instruction document), per `_mill/discussion.md`'s Testing section for #718. Verified by inspection: Card 12's two worked examples must each read as internally consistent and mutually distinguishable (confident case produces a drop; ambiguous case produces a kept-both `discarded` entry), and Card 14's generalized wording must correctly branch on the `discarded` entry's own description text.
