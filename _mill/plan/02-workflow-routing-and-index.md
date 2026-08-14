# Batch: workflow-routing-and-index

```yaml
task: Extract a language-agnostic code-comments skill; add a general docstring-length ceiling, purpose-not-mechanism rule, mandatory file/module header, and prohibit measured-result/design-rationale narrative
batch: workflow-routing-and-index
number: 2
cards: 3
verify: null
depends-on: [1]
```

## Batch Scope

Close the pre-existing gap that Go has no row in `workflow.md`'s Language Detection table (so `git-commit`/`git-pr` never auto-detect Go projects for `golang-build` lint/format routing — see the `workflow-md-go-row` discussion decision), then regenerate `SKILLS.md` so the new `code-comments` skill (created in batch 1) is discoverable via the skill index. This is a separate batch from batch 1 because it is a distinct concern — build/routing tooling, not comment-content — and it depends on batch 1 because the `SKILLS.md` regeneration reads `plugins/mill/skills/code-comments/SKILL.md`'s frontmatter, which must exist on disk first.

No batch-local decisions beyond `workflow-md-go-row` (already captured in `_mill/discussion.md`; not restated in the overview's Shared Decisions because it applies only to this batch's card 6).

## Cards

### Card 6: Add a Go row to `workflow.md`'s Language Detection table

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/workflow/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the "## Language Detection" table, add a new row after the existing `.csproj`, `.sln` row and before the closing "If multiple languages are present..." sentence:

  ```markdown
  | `go.mod` | Go | `@golang:golang-build`, `golang-comments`, `golang-testing` |
  ```

  The table's existing two rows (`pyproject.toml`/`setup.py`/`setup.cfg` → Python, `.csproj`/`.sln` → C#) are unchanged.
- **Commit:** `docs(workflow): add Go row to language detection table`

### Card 7: Regenerate `SKILLS.md`

- **Context:** none
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  From the worktree root (git_root), run the worktree's own copy of the skills-index script — not the plugin cache copy, per this repo's self-hosted-repo source-verification rule — so it scans the just-edited `plugins/*/skills/**/SKILL.md` files on disk and regenerates `SKILLS.md` deterministically from their frontmatter (`name`, `description`):

  ```bash
  PYTHONPATH=plugins/mill/scripts "$MILL_PYTHON" plugins/mill/scripts/millpy-skills-index.py
  ```

  This must pick up a new row for `code-comments` (added in batch 1, card 1) alongside every pre-existing skill row, unchanged otherwise.
- **Commit:** `docs(skills-index): regenerate SKILLS.md to include code-comments`

### Card 8: Verify batch 2 — routing table and index updated

- **Context:**
  - `SKILLS.md`
  - `plugins/mill/skills/workflow/SKILL.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  1. Confirm `plugins/mill/skills/workflow/SKILL.md`'s Language Detection table contains the exact Go row from card 6, and that the two pre-existing rows are unchanged.
  2. `grep -n "code-comments" SKILLS.md` — must return at least one match (confirms card 7's regeneration picked up the new skill).
- **Commit:** none

## Batch Tests

`verify:` is `null` — see `no-automated-tests` in the overview's `## Shared Decisions`. Card 8 performs the manual/textual verification in place of an automated `verify:` command.
