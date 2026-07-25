# Batch: commit-none-implementer-brief

```yaml
task: mill-plan review severity counting and validation schema gaps
batch: commit-none-implementer-brief
number: 5
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Updates the four instruction points in `implementer-brief.md` that assume every card produces a commit, so an implementer executing a batch containing `Commit: none` verification-only cards (validated by batch 4) knows to skip the commit step for them and doesn't misreport its own progress. Pure prompt text for an LLM implementer -- no code, no test surface (per `_mill/discussion.md`'s Testing section, this is validated by reading the rendered brief for a plan containing a `Commit: none` card, not by `run-all.py`). Independent of every other batch: it references the `Commit: none` convention conceptually but does not import or read any file another batch edits.

## Cards

### Card 14: Add `Commit: none` handling to all four implementer-brief.md instruction points

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Make four edits to `implementer-brief.md`:
  1. **Commit-skip instruction** (currently: "Stage the affected files and commit by invoking the `git-commit` skill with the card's `Commit:` message as the argument. **Do not call raw `git commit`.**" inside the "Work through `## Cards` in order" numbered step): add, immediately after that sentence, a new bullet-level instruction: `If the card's **Commit:** value is the literal "none", it is a verification-only card (validated by the plan review's commit-none-with-content check to have zero Edits:/Creates:/Deletes:/Moves:) -- do NOT invoke the git-commit skill, do NOT stage anything, and do NOT make any commit for this card. Perform only what its Requirements: describes (e.g. run a grep, confirm an earlier card's outcome) and move to the next card.`
  2. **Resume-after-incomplete matching** (currently: "run `git -C <PROJECT_ROOT> log <START_SHA>..HEAD --oneline` and match each commit subject against the cards' `Commit:` messages. When `<START_SHA>` is empty, derive the range start via ... Implement only the remaining cards -- do not re-edit or re-commit cards whose `Commit:` message already appears in the log."): add a new sentence at the end of this instruction: `A card whose Commit: is "none" never appears in this log by definition -- exclude it from this matching scan entirely. Treat a Commit: none card as complete once you have (re-)performed its Requirements: verification step this turn (or a prior turn, per your own judgment from the batch's current state); it needs no log entry to be considered done.`
  3. **Card-count self-check** (currently: "Run `git -C <PROJECT_ROOT> log <range-start>..HEAD --oneline` and match commit subjects against the batch file's `## Cards` `Commit:` messages to get an exact count."): add a clause: `-- Commit: none cards are never expected to appear in this log; do not count them as part of the expected total when comparing your committed-card count against the batch's declared card count, and do not report an unqualified "all complete" claim as false just because Commit: none cards produced no matching log entries.`
  4. **Report-section carve-out** (currently: "**`commit_sha` MUST be a real content commit distinct from the batch start commit.** An implementer that made edits but did not run the per-card `git-commit` skill must report `status: stuck` instead."): add a new sentence immediately after: `**Exception:** if every card you are reporting as done this turn (via cards_done) has Commit: none, you legitimately made zero content commits -- report commit_sha as the batch-start commit SHA (or your most recent real content commit, if this turn's Commit: none cards followed earlier cards that did commit) instead of reporting stuck. This exception does not apply if ANY card in cards_done this turn has a real Commit: message and you made no commit for it -- that remains a stuck-worthy failure exactly as today.` Do not claim this self-reported exception is what the backend gate trusts -- batch 6 makes the backend gate's actual enforcement code-derived (re-scanning the batch file itself), independent of what this brief tells the implementer to write; this brief text exists so the implementer's own report is honest and consistent with what the backend will independently verify, not so the backend defers to it.
- **Commit:** `docs(implement): support Commit: none verification-only cards in implementer brief`

## Batch Tests

`verify: null` -- this batch edits only the implementer-brief.md prompt template; there is no runnable surface. Validate by reading the rendered brief output for a plan containing a `Commit: none` card during manual/integration review of the finished plan (per `_mill/discussion.md`'s Testing section).
