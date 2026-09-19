# Batch: context-completeness-exemptions-docs

```yaml
task: '_plan_validate.py context-completeness: path-token exemption list gaps'
batch: context-completeness-exemptions-docs
number: 3
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch syncs the one planner-facing doc that describes `context-completeness`'s exemption
phrasings, `plugins/mill/skills/mill-plan/SKILL.md`'s `## Principles` section, with the three new
exemptions batch 1 added. It is its own batch because it touches a third, independently large file
(`mill-plan/SKILL.md`, ~28k context-token estimate) that would combine with either other batch's file
to approach or exceed `pipeline.max_batch_context_tokens` (120000) — see `00-overview.md`'s Shared
Decisions. It carries no functional dependency on batches 1 or 2 (the new sentences are fully
specified in Card 7's own `Requirements:` below, not derived by reading the implementation), so
`depends-on: []` — mill-go may schedule it any time after batch 1 exists on disk, but nothing breaks
if it runs before batch 2.

## Cards

### Card 7: Sync mill-plan's Principles-section exemption docs

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `mill-plan/SKILL.md`'s `## Principles` section has a bullet beginning "**Phrase Requirements:
  prohibitions on one line; avoid double negatives**" that documents, for planners writing plan
  cards, the `context-completeness` check's negation/contrast-citation/quoting exemption phrasings
  (the same three sentences: "A contrast citation ...", "A path inside a fenced block ...", "A
  not-involved mention is exempt only when ..."). Append three new sentences to that same bullet,
  immediately after the existing "A forward reference to a path a later card in the plan declares
  ..." sentence and before the existing "A not-involved mention is exempt only when phrased as one of
  three clause-scoped templates ..." sentence, documenting the three exemptions
  `01-context-completeness-exemptions.md` added to `_check_context_completeness`:
  `A same-line phrase naming another card/batch as the path's owner (e.g. "batch 8 fixes
  \`foo.py\`", "card 23 corrects ... \`bar.py\`") is exempt regardless of comma placement on the
  line -- this exemption is line-wide, not clause-scoped. A line listing 3 or more backtick-quoted
  literal values (e.g. table-driven test inputs) is exempt in full when at least one of those values
  is not itself path- or symbol-shaped -- do not rely on this for a line that is a genuine multi-file
  dependency list, since an all-path-shaped enumeration is never exempt by this rule. A line naming a
  rendered/emitted/printed/displayed/output value (e.g. "emitting the bare \`x.md\`") is exempt as an
  illustrative output citation, not a read dependency.`
- **Commit:** `docs(mill-plan): document the three new context-completeness exemptions`

## Batch Tests

`verify: null` — this is a pure documentation edit to a skill's Markdown instructions with no
runnable surface; there is no test file for `mill-plan/SKILL.md`'s own prose.
