# Batch: mill-start-skill

```yaml
task: "mill-go / mill-plan loop hardening"
batch: mill-start-skill
number: 7
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes the discussion-review sibling of #362/#378: mill-start's APPROVE-with-no-NOTE path
(Phase: Discussion Review step 4a) breaks straight to Handoff, and Handoff commits only
`status.md` — so the discussion review file under `reviews_dir` is never committed and is
lost at cleanup, exactly the gap fixed for holistic code review in batch 5 card 12.
SKILL-only prose; `verify: null`. Independent of the code batches (root in the DAG).

## Cards

### Card 15: commit the discussion review file at mill-start handoff

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `mill-start/SKILL.md` Phase: Handoff so its commit stages the reviews directory alongside `status.md`: change `git -C <worktree> add <status_path>` to `git -C <worktree> add <status_path> <reviews_dir>` (keep the existing `mill-start: handoff {slug}` message). This captures the discussion review file produced by the step-4a APPROVE-with-no-NOTE path, which otherwise reaches Handoff with the review file uncommitted (#362/#378). The change is idempotent for the 4b path, whose own commit already staged `<reviews_dir>` — nothing new remains to stage there. Add a one-line note in step 4a that the review file is committed at Handoff (so the path is auditable), consistent with how 4b records its fixer report. Do not alter the GAPS_FOUND path or the `--auto` subsections beyond this staging change.
- **Commit:** `docs(mill-start): commit discussion review file at handoff (#362, #378)`

## Batch Tests

`verify: null` — this batch edits only `mill-start/SKILL.md`. Verified by the holistic plan
reviewer; there is no runnable surface.
