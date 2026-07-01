# Batch: skills-index-regen

```yaml
task: "Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis"
batch: skills-index-regen
number: 5
cards: 1
verify: null
depends-on: [3, 4]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

This batch regenerates `SKILLS.md` so it includes rows for the two new skills (`mill-triage-to-tasks`, `mill-report-to-tasks`) created in batches 2 and 3, and reflects any description change made to `mill-ghissues-to-tasks` in batch 4. It depends on both entry-skill batches (3 and 4) because the scanner reads every `SKILL.md`'s frontmatter from disk — running it before those skills exist (or before batch 4's edit lands) would produce an incomplete or stale table.

No batch-local decisions beyond `## Shared Decisions` in the overview.

## Cards

### Card 7: regenerate `SKILLS.md`

- **Context:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
  - `plugins/mill/skills/mill-triage-to-tasks/SKILL.md`
  - `plugins/mill/skills/mill-report-to-tasks/SKILL.md`
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Edits:**
  - `SKILLS.md`
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` (frontmatter-only fix — see note below)
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Run the `mill-skills-index` skill's documented entrypoint exactly as `plugins/mill/skills/mill-skills-index/SKILL.md` describes: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"`. Do not hand-edit `SKILLS.md` — the scanner is the source of truth and produces deterministic, byte-identical output for unchanged inputs.
  - Verify the regenerated `SKILLS.md` contains one row each for `mill-triage-to-tasks` and `mill-report-to-tasks` (sorted alphabetically among the `mill` plugin's skills per the scanner's documented ordering), and that the `mill-ghissues-to-tasks` row's description matches whatever frontmatter batch 4 shipped.
  - **Discovered scope extension:** the scanner run surfaced a pre-existing (already present on `main`, unchanged by batch 4) YAML frontmatter bug in `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` — its unquoted `description:` value contains a mid-sentence `: ` ("One-shot: the assistant...") which `yaml.safe_load` rejects as an invalid nested mapping, so the scanner skips the file entirely and the `mill-ghissues-to-tasks` row silently disappears from `SKILLS.md`. Since the batch's own requirement mandates that row stay present with the batch-4 description text, the frontmatter `description:` value is wrapped in double quotes (no textual change to the description itself) so it parses. This is the minimal fix that satisfies the batch's stated verification without touching the scanner script (out of this batch's declared scope).
- **Commit:** `chore: regenerate SKILLS.md`

## Batch Tests

`verify: null` — this batch only runs the existing, already-tested `millpy-skills-index.py` scanner; no new test surface is introduced. Confirm correctness by reading the regenerated `SKILLS.md` diff during code review (new rows present, alphabetical ordering preserved, no unrelated rows changed).
