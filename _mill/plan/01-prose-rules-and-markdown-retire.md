# Batch: prose-rules-and-markdown-retire

```yaml
task: 'Fix prose skill: staleness rule and missing loads'
batch: prose-rules-and-markdown-retire
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/scripts/millpy-skills-index.py && git diff --exit-code -- SKILLS.md
depends-on: []
```

## Batch Scope

This batch delivers the writing-rule content itself and retires the skill it supersedes.
Card 1 adds the staleness rule, the cut test, and the fenced-YAML metadata rule to `plugins/mill/skills/prose/SKILL.md`.
Card 2 reduces `code-comments`' duplicate statement of the caller-list rule to a pointer.
Card 3 deletes `plugins/mill/skills/markdown/SKILL.md` and repoints every surviving reference to it.
Card 4 regenerates `SKILLS.md` so the generated index no longer lists the deleted skill.
Cards 3 and 4 must run in that order — the regeneration is only correct once the skill file is gone.

The external interface batch 4 consumes is card 1's final wording: the inlined `## Writing style` block in batch 4 is a compressed restatement of `prose`'s rules for agents that cannot load skills, including the cut test card 1 adds here.

## Cards

### Card 1: Add the staleness rule, the cut test, and the fenced-YAML rule to `prose`

- **Context:**
  - `plugins/mill/skills/conversation/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/prose/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Make three additions to `plugins/mill/skills/prose/SKILL.md`, leaving every existing section otherwise unchanged.

  First, append one sentence to the existing `## No padding` section, after its current final line "If a sentence adds no new information, cut it.":

  ```
  Apply a per-sentence cut test: would the reader act differently if this sentence were missing? If not, cut it.
  ```

  Second, insert a new section titled `## Don't pin a perishable specific` between the existing `## Say it once` section and the existing `## Line breaks` section, with this body:

  ```
  Name the source, not the snapshot.
  A detail a reader could instead derive, and that changes independently of the prose around it, goes stale silently — an unrelated change elsewhere becomes a forced edit here, and nothing signals when the edit was missed.

  Three forms of the same mistake:

  - **A tally** — a count, a runtime, a file or test total.
  - **An enumerated consumer list** — naming every current caller, writer, or implementer of a shared symbol when the point doesn't depend on which ones currently do.
  - **A name cited descriptively** — referring to a function or file by what it does rather than as a stable identifier, so a rename falsifies the sentence with nothing to catch it.

  Write the derivation instead: point at the command that produces the number, the directory that holds the files, or the subsystem group rather than its current members.
  When a name is load-bearing, cite it as a stable identifier in backticks so a rename search finds it.

  Two exceptions:

  - **A closed set whose size is the contract** — an enum a test pins shut. Even that is stated once, at its definition site.
  - **A measurement report** — a benchmark table, a results document, a captured baseline. Such a document records one specific run at a point in time and is not claiming to stay true; going stale when a new run happens is what makes it useful.
  ```

  Third, add a second bullet to the existing `## Markdown` section, after its current "Headings structure the document, not decorate it." bullet:

  ```
  - **Fenced YAML for metadata in generated files.**
    Use fenced ` ```yaml ` blocks for metadata in generated `.md` files — status files, review reports, registry entries, any machine-written markdown.
    `---` frontmatter is reserved for skill definitions (`SKILL.md`) and plugin manifests, which the platform parses.
    Never use frontmatter for human-facing metadata in a generated file — previewers hide it.
  ```

  Do not change the file's own `---` frontmatter block, and do not change `plugins/mill/skills/conversation/SKILL.md` — it is listed above for reference only, to confirm the "Load `prose` first" line it carries stays as it is.
- **Commit:** `docs(prose): add staleness rule, cut test, and fenced-YAML metadata rule`

### Card 2: Reduce `code-comments`' caller-list rule to a pointer at `prose`

- **Context:**
  - `plugins/mill/skills/prose/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/code-comments/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace the `**No enumerated-consumer lists**` bullet, the final bullet under `## Prohibited patterns` in `plugins/mill/skills/code-comments/SKILL.md`, with a pointer that states the rule zero times and keeps the comment-specific illustration and rationale. The bullet currently reads:

  ```
- **No enumerated-consumer lists** — don't name every current caller, writer, consumer, or implementer of a shared symbol or resource when the comment's point doesn't depend on which ones currently do
  (e.g. "the logger, reed, shuttle, and burler all write it").
  That list goes stale whenever a subsystem is added or removed, turning an unrelated change elsewhere in the codebase into a forced edit here.
  Write "several of `<component>`'s own subsystems" or similar instead, unless the specific names are themselves load-bearing to the point being made.
```

  Replace it with:

  ```
- **No enumerated-consumer lists** — see `prose`'s "Don't pin a perishable specific".
  In a comment the form is naming every current caller or writer of a shared symbol
  (e.g. "the logger, reed, shuttle, and burler all write it"),
  which turns an unrelated change elsewhere in the codebase into a forced edit here.
  Write "several of `<component>`'s own subsystems" or similar instead, unless the specific names are themselves load-bearing to the point being made.
```

  Model the pointer form on the existing `## Line-wrap style` section a few lines above in the same file, which is one sentence deferring to `prose`'s Line-breaks rule.
  Leave every other bullet under `## Prohibited patterns` unchanged.
- **Commit:** `docs(code-comments): point enumerated-consumer rule at prose`

### Card 3: Delete the `markdown` skill and repoint every reference to it

- **Context:**
  - `plugins/mill/skills/prose/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/templates/review-output.schema.md`
  - `plugins/mill/scripts/millpy-skills-index.py`
  - `plugins/mill/scripts/tools/mdreflow/mdreflow.py`
- **Creates:** none
- **Deletes:**
  - `plugins/mill/skills/markdown/SKILL.md`
- **Moves:** none
- **Requirements:** Delete `plugins/mill/skills/markdown/SKILL.md` with `git rm`, then repoint the four surviving references.

  In `plugins/mill/skills/mill-go2/SKILL.md`, under `## Driver preamble`, the phrase "Load the `mill:code-quality` and `mill:markdown` skills via the Skill tool unconditionally" becomes "Load the `mill:code-quality` and `mill:prose` skills via the Skill tool unconditionally".
  Change nothing else on that line — the per-language skill trios that follow it stay as they are.

  In `plugins/mill/templates/review-output.schema.md`, the sentence "Note: `---`-style YAML frontmatter is reserved for SKILL.md and plugin manifests per the markdown skill." becomes "Note: `---`-style YAML frontmatter is reserved for SKILL.md and plugin manifests per `prose`'s Markdown section."
  The sentence that follows it ("Review output files must never use `---` frontmatter.") is unchanged, and no other line of that template changes.

  In `plugins/mill/scripts/millpy-skills-index.py`, `_extract_frontmatter`'s docstring says "This matches the SKILL.md convention — it is the one place `---` frontmatter is allowed by the markdown skill."
  Change the trailing clause to "allowed by the `prose` skill's Markdown section."

  In `plugins/mill/scripts/tools/mdreflow/mdreflow.py`, the module docstring's first line "One-shot repo sweep for the mill:markdown skill's semantic-line-break rule." becomes "One-shot repo sweep for the mill:prose skill's semantic-line-break rule.", and its later citation `plugins/mill/skills/markdown/SKILL.md`'s "No fixed-column hard-wrapping" section becomes `plugins/mill/skills/prose/SKILL.md`'s "Line breaks" section.
  Both edits are docstring text only — no executable line of that module changes.

  After the four edits, confirm with `grep -rn "mill:markdown\|markdown/SKILL.md\|markdown skill" --include="*.md" --include="*.py" .` from the repo root that the only surviving hits are inside `_mill/`, which is task working state and not part of the shipped surface, and inside `SKILLS.md`, which card 4 regenerates.
- **Commit:** `refactor(skills): delete markdown skill, repoint references at prose`

### Card 4: Regenerate `SKILLS.md`

- **Context:**
  - `plugins/mill/scripts/millpy-skills-index.py`
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Regenerate the root `SKILLS.md` so its `mill` table no longer carries a `markdown` row, by running the scanner exactly as `plugins/mill/skills/mill-skills-index/SKILL.md` documents:

  ```
  PYTHONPATH= uv run --project plugins/mill python plugins/mill/scripts/millpy-skills-index.py
  ```

  Do not hand-edit `SKILLS.md` — the `SKILL.md` frontmatter is the source of truth and the index is a view of it.
  Confirm the regenerated file's diff is exactly the removal of the one `markdown` row and the corresponding change to the skill count on the generated header line, and that re-running the scanner a second time leaves the file byte-identical (this is what the batch's own `verify:` command asserts).
- **Commit:** `chore: regenerate SKILLS.md after markdown skill removal`

## Batch Tests

`verify:` re-runs the `SKILLS.md` scanner and asserts the regenerated file is byte-identical to what card 4 committed (`git diff --exit-code -- SKILLS.md`).
That is the only runnable surface this batch has: cards 1, 2, and 3's remaining edits are skill and docstring prose, which the task discussion establishes as untestable — a substring assertion on a style rule's wording breaks on any rewording and tests nothing real.

No `--only` test-file list is used here, so the `verify-unrelated-test-file` check does not apply.
Card 3's grep sweep is the manual gate for the deletion: no reference to `mill:markdown`, `markdown/SKILL.md`, or "the markdown skill" may survive outside `_mill/`.
