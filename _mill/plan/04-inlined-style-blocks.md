# Batch: inlined-style-blocks

```yaml
task: 'Fix prose skill: staleness rule and missing loads'
batch: inlined-style-blocks
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py
depends-on: [1]
```

## Batch Scope

This batch reaches the eight dispatch sites whose agents write prose but cannot load a skill.
The five reviewer prompt templates are rendered for agents whose tool grant is `Read, Grep, Glob, Write`, and can also be rendered as a raw prompt string through an LLM-provider wrapper with no skill machinery at all;
the three briefs here list no `Skill` in their `## Tools` section.
A load directive at any of these sites would be an instruction the agent has no tool to execute, so the rules are inlined instead.

Both cards insert the identical block, byte for byte.
It is given here once and copied verbatim at all eight sites:

```
## Writing style

State the point first — no preamble, and no restating a point before making it.
Cut empty intensifiers ("actually", "really", "simply", "just", "completely"): remove the word, and if the sentence still means the same thing it was padding.
Say each thing once; do not restate it in a summary or a closing recap.
Do not narrate what is already visible in the quoted code or the surrounding context.
Don't pin a perishable specific — a tally, a list of the current callers of a symbol, or a name cited descriptively rather than as a stable identifier: name the source, not the snapshot.
Apply a per-sentence cut test: would the reader act differently if this sentence were missing? If not, cut it.
For any multi-line prose written into a file, use semantic line breaks — one sentence per line, never fixed-column hard-wrap, plain newlines only (never a trailing double-space or backslash).
```

The block compresses one rule from each of `prose`'s five content sections, including the staleness rule batch 1 card 1 adds — five of the eight sites write review findings and commit messages, which is exactly the prose a tally or a list of current callers goes stale in.

The block contains no angle-bracket `<UPPERCASE>` token, and must not acquire one: `_render.render` raises `KeyError` on any unresolved token, which would break every prompt render in production.
It also does not restate the per-finding review format ("severity-label plus three or four short bullets, a few hundred tokens"), which each reviewer template already specifies — these rules serve that requirement rather than redefining it.

This batch depends on batch 1 because the block is a compressed restatement of `prose`'s rules, including the cut test batch 1 adds;
if batch 1's wording moves, this block moves with it.

## Cards

### Card 9: Inline the writing-style block in the five reviewer templates

- **Context:**
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/unit_tests/test-review-templates.py`
- **Edits:**
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-discussion.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Insert the `## Writing style` block quoted in this batch's `## Batch Scope` into each of the five reviewer prompt templates, byte-identical at all five sites.

  Place it immediately after the `<TOOL_RULE>` token line in each file, separated by one blank line on each side.
  In `plugins/mill/templates/review-code-batch.md` and `plugins/mill/templates/review-code-holistic.md` that puts it ahead of `## Prior non-blocking items`;
  in `plugins/mill/templates/review-plan-batch.md` and `plugins/mill/templates/review-plan-holistic.md` ahead of `## Constraints`;
  in `plugins/mill/templates/review-discussion.md` ahead of the `---` rule that precedes `## Task`.

  Do not add a load directive naming any skill to these templates.
  The reviewer agent definitions grant `Read, Grep, Glob, Write` and no `Skill` tool, so a load instruction would be unexecutable, and the bulk dispatch shape has no skill machinery at all.
  Do not change any existing heading, token, or sentence in the five files;
  the block is an insertion only.

  After inserting, confirm with `grep -c "Apply a per-sentence cut test"` that each of the five files carries the block exactly once.
- **Commit:** `docs(templates): inline writing-style rules in the five reviewer prompts`

### Card 10: Inline the writing-style block in the three skill-less briefs

- **Context:**
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:**
  - `plugins/mill/templates/fixer-holistic-brief.md`
  - `plugins/mill/templates/merge-in-conflict-brief.md`
  - `plugins/mill/templates/merge-in-verify-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Insert the same `## Writing style` block quoted in this batch's `## Batch Scope` into the three agent briefs whose `## Tools` section grants no `Skill` tool, byte-identical to the five reviewer-template copies from card 9.

  Place it immediately after the `## Tools` section in each of `plugins/mill/templates/fixer-holistic-brief.md`, `plugins/mill/templates/merge-in-conflict-brief.md`, and `plugins/mill/templates/merge-in-verify-brief.md`, separated by one blank line on each side, so it sits beside the tool grant that motivates its form.

  All three agents produce prose — commit messages, conflict resolutions, verification summaries — which is why they are in scope.
  Do not add `Skill` to any of the three `## Tools` lists;
  widening a deliberately narrow tool grant is outside this task.
  `plugins/mill/templates/fixer-holistic-brief.md` already instructs loading `mill-receiving-review` despite omitting `Skill` from its own list;
  leave that line alone, since the inlined block sidesteps it and resolving the inconsistency is a separate concern.
  `plugins/mill/templates/implementer-brief.md` is listed above for reference only — it grants `Skill` and receives the rules through `<LANGUAGE_SKILLS>` instead, and must not be edited.

  After inserting, confirm with `grep -c "Apply a per-sentence cut test"` that each of the three files carries the block exactly once, and that the block's text is identical to the five copies card 9 wrote.
- **Commit:** `docs(templates): inline writing-style rules in the skill-less agent briefs`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-review-templates.py` directly, by path rather than through `run-all.py --only`.
That test renders each of the five reviewer templates through `_review_common.render_prompt` with the exact token set its backend supplies, which is the one failure this batch can realistically cause: an accidental `<UPPERCASE>` token in the inserted block would raise `KeyError` at render time in production, and this is the only test that would catch it.
It also re-asserts that the deleted tool-prohibition header stays deleted and the kept `MILL_REVIEW_BEGIN`/`MILL_REVIEW_END` wrapper stays present, so an insertion at the wrong offset is caught too.

The direct-invocation form is used instead of `--only` on purpose;
see the overview's `single-test-file-verify-form-for-batch-4` Shared Decision.

The three briefs in card 10 have no equivalent render guard — the merge-in tests mock `_render.render` and `plugins/mill/unit_tests/test-millpy-fix.py` asserts only on substrings of the raw `fixer-holistic-brief.md` text.
The card's `grep -c` confirmation is the gate there, backed by the same no-angle-bracket-token rule.
The style block's own wording is deliberately not asserted anywhere: a substring check on it would break on any rewording and test nothing real.
