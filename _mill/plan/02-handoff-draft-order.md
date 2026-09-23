# Batch: handoff-draft-order

```yaml
task: 'mill-setup/wiki/docs/build-env: misc small bugs, round 3'
batch: handoff-draft-order
number: 2
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes GitHub issue #1138: the `handoff` skill (`plugins/mill/skills/handoff/SKILL.md`) tells the
agent that a prior handoff document must never become a structural template, but doesn't say *when*
to read the old file relative to drafting the new one — so an agent that reads the old file first
(as is natural, since it exists on disk) ends up producing a new handoff with nearly the same
section order anyway, exactly what the rule forbids. This batch makes the read-after-draft ordering
explicit in the skill's own instructions, per `discussion.md`'s `1138-handoff-reorder` Decision. No
external interface — self-contained single-file prose fix.

## Cards

### Card 2: Sequence handoff/SKILL.md's old-file read after the new draft, not before

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/handoff/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the paragraph that currently begins
  `**If this handoff replaces an existing handoff document, re-derive every section from this skill's own rules.**`
  (its full current text: "Treat the previous file only as a source of facts (e.g. \"PR #183 is
  still open\") — never as a section template or outline to inherit. Copying a prior handoff's
  structure carries forward any violation it contained.") with a version that makes the reading
  order explicit and enforceable, not just the outcome:

  Open with a bolded lead sentence making the ordering itself the rule:
  `**If this handoff replaces an existing handoff document, draft the new document first — before opening the old file.**`
  Follow it with: draft every section from this skill's own rules (the "This document carries
  current state and durable facts" test, the anti-pattern-heading rejections, the "suggested
  skills" section, etc. — all already stated earlier in this same file), using only the current
  conversation and current state (git status, worktree state, task status); do not open the old
  handoff file at this stage. Only once that full draft is complete, read the previous handoff file
  once, as a fact-check pass: pick up any fact that is still true and still open (the skill's own
  example, "PR #183 is still open", plus e.g. an unresolved finding from an earlier session) and
  fold it into the already-drafted structure — never let the old file's own structure or section
  order influence the draft at this or any later point. Keep the existing closing sentence,
  "Copying a prior handoff's structure carries forward any violation it contained.", as the
  rationale for why the ordering matters.

  Do not change any other paragraph in this file (the file-location rule, the first-line
  instruction to load `mill:prose`/`mill:conversation`, the "suggested skills" instruction, the
  durable-facts test, the anti-pattern-heading rejections, the redaction instruction, or the
  argument-handling instruction).
- **Commit:** `fix(handoff): sequence the old-handoff read after the new draft, not before`

## Batch Tests

`verify: null` — this is a prose-only `SKILL.md` instruction change with no runnable surface;
`handoff` is loaded and followed by an LLM, not executed as code, so no unit test applies. Manual
verification at implementation time: confirm the reordered instructions read correctly as a
two-step sequence (draft first, then fact-check against the old file) and that the "never a section
template" rule is now structurally enforced by that ordering, not merely asserted.
