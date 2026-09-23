# Batch: prose-cleanup

```yaml
task: "Deactivate codeguide integration in millhouse"
batch: prose-cleanup
number: 2
cards: 7
verify: null
depends-on: []
```

## Batch Scope

Update every remaining piece of prose that describes or depends on the two call sites batch 1 deletes -- three brief templates and two skill files that promise `codeguide-update` runs from `git-commit`, plus CLAUDE.md's and git-clone's stale claim that mill-setup clones a codeguide sibling (confirmed false by reading `mill-setup/SKILL.md` in full during discussion: it has no codeguide-specific setup code at all). This batch has no file overlap with batch 1 and no dependency on its edits landing first -- both batches independently make the codebase consistent with codeguide being deactivated -- so it is a second root batch, not a dependent of batch 1. `verify: null` because every edit here is a markdown-prose rewrite with no runnable surface; batch 3's own verify is the check that both this batch and batch 1 actually removed the promised behavior.

## Cards

### Card 5: implementer-brief.md -- drop the codeguide-update promise

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the exact sentence
```text
The skill runs language-appropriate lint on staged files and, if `_codeguide/Overview.md` exists, triggers `codeguide-update` so the next batch's implementer sees the updated codeguide.
```
  with
```text
The skill runs language-appropriate lint on staged files.
```
  Then delete the following sentence in full:
```text
Skipping the skill means the next batch reads a stale map.
```
  The surrounding bullet's first sentence ("Stage the affected files and commit...") and its "**Do not call raw `git commit`.**" sentence are unchanged, as is the next bullet about the literal "none" `Commit:` value.
- **Commit:** `docs(implementer-brief): drop codeguide-update promise`

### Card 6: fixer-batch-brief.md -- drop the codeguide-update promise

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/fixer-batch-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the exact sentence
```text
After each fix, commit using the `git-commit` skill (so lint and `codeguide-update` run per commit).
```
  with
```text
After each fix, commit using the `git-commit` skill (so lint runs per commit).
```
- **Commit:** `docs(fixer-batch-brief): drop codeguide-update promise`

### Card 7: fixer-holistic-brief.md -- drop the codeguide-update promise

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/fixer-holistic-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the exact sentence
```text
After each fix, commit using the `git-commit` skill (so lint and `codeguide-update` run per commit).
```
  with
```text
After each fix, commit using the `git-commit` skill (so lint runs per commit).
```
- **Commit:** `docs(fixer-holistic-brief): drop codeguide-update promise`

### Card 8: mill-go-base/SKILL.md -- drop the codeguide-update promise

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the "**Commits go through `git-commit`.**" bullet, replace the exact sentence
```text
every per-card commit invokes the `git-commit` skill so lint + `codeguide-update` run per-commit.
```
  with
```text
every per-card commit invokes the `git-commit` skill so lint runs per-commit.
```
  Then delete the following sentence in full:
```text
Batch N+1's implementer then reads a codeguide that already reflects batch N's additions.
```
  The bullet's opening clause ("`implementer-brief.md` already instructs this, but enforce it if the implementer asks for confirmation:") is unchanged, as is the following "**One task per worktree.**" bullet.
- **Commit:** `docs(mill-go-base): drop codeguide-update promise`

### Card 9: mill-quick/SKILL.md -- drop the codeguide-update promise

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-quick/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the exact sentence
```text
The skill runs language-appropriate lint on staged files and triggers `codeguide-update` when `_codeguide/Overview.md` exists.
```
  with
```text
The skill runs language-appropriate lint on staged files.
```
- **Commit:** `docs(mill-quick): drop codeguide-update promise`

### Card 10: CLAUDE.md -- remove the stale codeguide sibling-clone line

- **Context:** none
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the container-layout ASCII diagram under `## Project shape`, delete the line
```text
codeguide/                     ← codeguide clone
```
  in full (the line sits between `wiki/                          ← wiki clone` and `portals/`). Leave every other line in the diagram, including `wiki/` and `portals/`, unchanged.
- **Commit:** `docs(CLAUDE): remove stale codeguide sibling-clone line`

### Card 11: git-clone/SKILL.md -- fix the stale mill-setup claim

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/git-clone/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the exact sentence
```text
mill-setup later adds `<repo>/wiki/`, `<repo>/codeguide/`, and `<repo>/portals/` as siblings of `wts/`.
```
  with
```text
mill-setup later adds `<repo>/wiki/` and `<repo>/portals/` as siblings of `wts/`.
```
- **Commit:** `docs(git-clone): fix stale mill-setup sibling-clone claim`

## Batch Tests

`verify: null` -- every card in this batch is a markdown-prose rewrite with no runnable surface (skill files and templates, not code). Batch 3's own `verify:` greps both this batch's and batch 1's target files for the removed strings, giving an end-of-plan check that these rewrites actually landed.
