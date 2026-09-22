# Plan: Fix prose skill: staleness rule and missing loads

```yaml
task: 'Fix prose skill: staleness rule and missing loads'
slug: prose-skill-gaps
approved: false
discussion_sha: 14f67eb1af2035d8145d5df14c2bd38ded775b96
started: '20260922-090637'
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: prose-rules-and-markdown-retire
    file: 01-prose-rules-and-markdown-retire.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/scripts/millpy-skills-index.py && git diff --exit-code -- SKILLS.md
  - number: 2
    name: dispatch-directive
    file: 02-dispatch-directive.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-language-skills-directive.py
  - number: 3
    name: load-directive-sites-and-test
    file: 03-load-directive-sites-and-test.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-load-directive-convention.py
  - number: 4
    name: inlined-style-blocks
    file: 04-inlined-style-blocks.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-templates.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: inlined-style-block-is-byte-identical

- **Decision:** The `## Writing style` block added to the five reviewer prompt templates and the three skill-less agent briefs is byte-identical at all eight sites.
  Its exact text is given once, in batch 4's `## Batch Scope`, and both of that batch's cards copy it verbatim rather than paraphrasing per site.
- **Rationale:** Eight hand-adapted variants would drift, and a future sweep for the block would have to guess at eight spellings.
  One literal string means `grep -c` finds every site and a reword is a single find-and-replace.
  The block also must contain no `<UPPERCASE>` angle-bracket token: `_render.render` raises `KeyError` on any unresolved `<TOKEN>`, so an accidental one would break every prompt render in production.
- **Applies to:** inlined-style-blocks

### Decision: load-directive-versus-inlined-block

- **Decision:** One rule picks the form at every dispatch site — a load directive naming `mill:prose` where the agent's brief grants the `Skill` tool, an inlined `## Writing style` block where it does not.
  Under that rule `implementer-brief.md` and `fixer-batch-brief.md` inherit the skill via `language_skills_directive()` (batch 2);
  `fixer-holistic-brief.md`, `merge-in-conflict-brief.md`, `merge-in-verify-brief.md`, and the five reviewer templates get the inlined block (batch 4).
- **Rationale:** A load directive aimed at an agent with no `Skill` tool is an instruction it has no way to execute.
  Deriving both forms from one rule means a future brief's treatment follows from its own `## Tools` list rather than a case-by-case judgement.
  No agent definition under `plugins/mill/agents/` and no brief's `## Tools` list is widened by this plan.
- **Applies to:** all batches

### Decision: convention-test-anchors-on-canonical-wording

- **Decision:** The order half of the load-directive convention test is implemented as "the file must contain at least one line matching the canonical pattern `load \`mill:prose\`, then \`mill:conversation\``", not as a positional comparison applied to every matched line.
- **Rationale:** Each of the four sites that already have the directive right follows it with an explanatory sentence that itself contains a load verb and names `mill:conversation` **before** `mill:prose` (e.g. mill-start's "`mill:conversation` builds on `mill:prose`, so load it first").
  A per-line positional comparison would fail all four currently-correct files.
  A whole-file first-occurrence comparison is worse: `mill-start/SKILL.md` mentions `mill:conversation` referentially at line 25, long before its own line-81 directive.
  Anchoring on the canonical wording satisfies both halves of the requirement — a directive that names `mill:conversation` first and `mill:prose` afterwards produces no canonical line and fails — at the accepted cost, recorded in the task discussion, that the convention's wording is now encoded in a pattern.
- **Applies to:** load-directive-sites-and-test

### Decision: no-done-gate

- **Decision:** `pipeline.done_gate` stays `null`;
  this plan does not edit `mill-config.yaml`.
- **Rationale:** Both candidate repo-wide gates are already red on the worktree tip, before any change from this plan.
  `uvx ruff check .` from the repo root reports 2009 errors (exit 0, but a non-empty finding set — pre-existing lint debt).
  The full unit suite reports `FAIL -- 2 of 114 in 62.6s: ['test-mill-go-base-agent-only.py', 'test-millpy-validate-plan.py']`;
  the first fails on a banned-literal regression guard over `mill-go-base/SKILL.md`, the second on a test double whose signature has drifted from `_plan_validate.run`.
  Neither is in this task's scope.
  Enabling either gate would make every batch in this plan depend on unrelated debt being fixed first, and setting the key would additionally trigger the `wiki-config-mutation` validator check for no gain.
- **Applies to:** all batches

### Decision: single-test-file-verify-form-for-batch-4

- **Decision:** Batch 4 invokes `plugins/mill/unit_tests/test-review-templates.py` directly rather than through `run-all.py --only`.
- **Rationale:** `test-review-templates.py` is the real regression guard for batch 4 — it renders each of the five reviewer templates with the exact token set its backend supplies, which is precisely what an accidentally introduced `<TOKEN>` in the inlined block would break.
  Batch 4 does not edit that test file, so the `verify-unrelated-test-file` check would flag it as a stray `--only` token byte-identical to `main`;
  that check cannot see the template-to-test relationship, and suppressing it by editing the test would mean asserting on the style block's wording, which the task discussion rules out.
  Direct single-file invocation is the form `mill-plan/SKILL.md`'s "Verify command scope" section already sanctions, and the check only inspects `--only` lists.
- **Applies to:** inlined-style-blocks

### Decision: tdd-cards-leave-the-tree-red-between-commits

- **Decision:** In batch 2 the test card lands before the implementation card, and in batch 3 the site fix lands before the test card.
  Batch 2's tree is therefore red between its two commits by design.
- **Rationale:** The task discussion names both as TDD candidates.
  `verify:` runs at batch boundaries, not per card, so an intra-batch red tree is invisible to the gate and the batch is green at its boundary either way.
  Batch 3 is ordered the other way round because its test walks the real shipped tree: landing the test first would make it fail on `handoff/SKILL.md` for a reason the very next card removes, with no diagnostic value.
- **Applies to:** dispatch-directive, load-directive-sites-and-test

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `SKILLS.md`
- `plugins/mill/scripts/_agent_dispatch.py`
- `plugins/mill/scripts/millpy-skills-index.py`
- `plugins/mill/scripts/tools/mdreflow/mdreflow.py`
- `plugins/mill/skills/code-comments/SKILL.md`
- `plugins/mill/skills/handoff/SKILL.md`
- `plugins/mill/skills/mill-go2/SKILL.md`
- `plugins/mill/skills/prose/SKILL.md`
- `plugins/mill/templates/fixer-holistic-brief.md`
- `plugins/mill/templates/merge-in-conflict-brief.md`
- `plugins/mill/templates/merge-in-verify-brief.md`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-language-skills-directive.py`
- `plugins/mill/unit_tests/test-load-directive-convention.py`
