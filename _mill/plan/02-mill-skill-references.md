# Batch: mill-skill-references

```yaml
task: Migrate mill's generic skills to the shared scribe plugin
batch: mill-skill-references
number: 2
cards: 9
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-load-directive-convention.py test-language-skills-directive.py test-agents-defs.py test-mill-go-variants.py test-skills-index.py test-inplace.py test-skill-helper-drift.py test-guards.py
depends-on: [1]
```

## Batch Scope

Replaces mill's six generic skills with `scribe:*` plus one new mill layer, `mill:conventions`, and rewrites every reference to them.
One batch because the forbidden-name guard in the rewritten `test-load-directive-convention.py` (card 3) only passes once every reference, the deletions and the regenerated `SKILLS.md` have all landed;
splitting it would leave an intermediate batch whose verify cannot pass.
Card 3 writes the test first (TDD): it fails against the tree until cards 4-11 land.
Batch 3 consumes the new canonical load phrase only through the same test, which it re-runs after editing `CLAUDE.md`.
Batch-local decision: every rewrite is a targeted text replacement at the named line;
none of these cards restructures a skill beyond the sentence being changed.

## Cards

### Card 3: Rewrite the load-directive convention test for scribe

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-load-directive-convention.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Rewrite the module to guard the new convention, keeping its structure (module docstring listing covered cases, `check_text`, test functions printing `PASS <name>`, `main()` runner) and `HUB`/`_LOAD_VERB_RE` unchanged.
  - Replace `_CONVERSATION_RE`, `_PROSE_RE`, `_CANONICAL_RE` with:
    `_CONVERSATION_RE = re.compile(r"scribe:conversation")`,
    `_CONVENTIONS_RE = re.compile(r"mill:conventions")`,
    `_TWO_SKILL_RE` matching "[Ll]oad `scribe:prose`[,] then `scribe:conversation`" (`\s*,?\s*then\s+` between the two backticked names),
    `_THREE_SKILL_RE` matching "[Ll]oad `scribe:prose`, then `scribe:conversation`, then `mill:conventions`" (`\s*,\s*then\s+` between each pair),
    and `_FORBIDDEN_RE` matching any of `mill:(prose|conversation|code-quality|code-comments|testing|handoff)` followed by a word boundary, `plugins/mill/skills/(prose|conversation|code-quality|code-comments|testing|handoff)/`, or `plugins/(python|csharp|golang)/`.
  - `check_text(text) -> str | None`:
    a line naming `scribe:conversation` with a load verb makes the file require `_TWO_SKILL_RE` somewhere in its text;
    a line naming `mill:conventions` with a load verb makes the file require `_THREE_SKILL_RE`.
    Return a reason naming the first offending line, as today; a file with neither kind of line passes.
    Update the docstring's step list to match and drop the reference to the old plan's Shared Decision name.
  - New `check_forbidden(text) -> str | None`: return a reason naming the first line matching `_FORBIDDEN_RE`, else `None`.
  - `_shipped_files()`: also glob `.claude/skills/**/SKILL.md`; drop the docstring clause excluding `.claude/skills/`.
  - New `_forbidden_scan_files()`: every `*.md` under `plugins/` and `.claude/skills/`, every `*.py` under `plugins/mill/scripts/`, every `*.md` under `doc/`, plus `SKILLS.md` and `CLAUDE.md` at `HUB` (mentioned, not read: the test globs these at run time).
    Skip any path whose parts include `_mill`, `.venv`, `node_modules` or `.scratch`, and skip this test file itself (`Path(__file__).resolve()`).
  - Test functions (replace the old five in-memory cases; keep one tree-walk per rule):
    three-skill directive passes;
    two-skill directive passes;
    a `scribe:conversation` load directive with no `scribe:prose` fails;
    `scribe:conversation` loaded before `scribe:prose` fails;
    a `mill:conventions` load directive in a file that has only the two-skill phrase fails;
    a referential mention with no load verb ("per `scribe:conversation`'s numbered-options rule") passes;
    the canonical directive followed by a later referential mention passes;
    `check_forbidden` flags each of the six `mill:<name>` forms, one path under `plugins/mill/skills/prose/` and one under `plugins/python/`;
    `check_forbidden` passes text naming `mill:conventions`, `scribe:prose` and `mill:workflow`;
    tree-walk of `_shipped_files()` through `check_text`;
    tree-walk of `_forbidden_scan_files()` through `check_forbidden`, reporting every offending file.
  - Register every test function in `main()`'s list.
    The in-memory fixtures may spell the forbidden names literally, since this file excludes itself from the scan.
  - The two tree-walk tests fail until cards 4-11 land; that is expected mid-batch.
- **Commit:** `test(mill): guard the scribe load order and forbid the retired mill skill names`

### Card 4: Create the mill:conventions skill

- **Context:**
  - `plugins/mill/skills/conversation/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/conversation/SKILL.md`
  - `/home/knatte/Code/scribe/plugins/scribe/skills/prose/SKILL.md`
  - `CLAUDE.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/skills/conventions/SKILL.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Frontmatter (`---` block, the SKILL.md exception): `name: conventions`;
  `description: Mill-specific operating rules — new-thread prompts, task-state and scratch locations, sed reach into dispatched agents, worktree isolation. Builds on scribe:prose and scribe:conversation.`
  Body, semantic line breaks throughout, restating nothing `scribe:prose` or `scribe:conversation` already say:
  - `# Mill Conventions` heading, then an opening that says this skill holds the rules specific to working in a mill repo and that it builds on `scribe:prose` and `scribe:conversation`, stated with the exact phrase "Load `scribe:prose`, then `scribe:conversation` before this skill".
    Do not write the literal `mill:conventions` together with a load verb anywhere in this file.
  - `## Prompts for new threads`: verbatim from the same section of `plugins/mill/skills/conversation/SKILL.md`.
  - `## Task-state and scratch locations`, rewritten per CLAUDE.md:
    per-task working state (`status.md`, `discussion.md`, `plan/`, `reviews/`, `briefs/`) lives in `_mill/` on the task branch;
    the wiki holds only `Home.md` and daemon-rendered files;
    scripts resolve the wiki through `_paths.resolve_wiki_path`, never the `.wiki` junction.
    Then the scratch rule as a stated override of scribe: in a mill worktree `.scratch/` means the worktree root's `.scratch/`, because mill's scripts, fixtures and new-thread prompts resolve it from the worktree root — this intentionally narrows `scribe:conversation`'s "`.scratch/` under the current working directory" for mill sessions.
    Keep the plugin-managed scratch note (shared `.scratch/`; subdirectories such as `test-review-<type>-<id>/`, `plans/`, `briefs/` created as needed and cleaned up at will) and that `.scratch/` is gitignored via `**/.scratch/`.
    Drop the "never write to /tmp" rule (scribe states it).
  - `## sed in generated prompts`: only the addition — the no-`sed` rule also binds every prompt, brief or script a mill orchestrator generates for a dispatched implementer, reviewer or fixer.
    Do not restate the rule itself.
  - `## Worktree isolation`: verbatim from mill's `conversation`, including the MAY/MAY NOT bullets, the `mill-merge`/`mill-cleanup` exemption and the 2026-04-13 **Why:** paragraph.
  - `## Skill authors`: only the retroactive clause, scoped to mill skills — when you touch an existing mill skill whose operator prompts are prose, convert them to `scribe:conversation`'s numbered-list form.
- **Commit:** `feat(mill): add mill:conventions, the mill layer over scribe`

### Card 5: Delete mill's generic skills

- **Context:**
  - `plugins/mill/skills/conventions/SKILL.md`
- **Edits:** none
- **Creates:** none
- **Deletes:**
  - `plugins/mill/skills/prose/SKILL.md`
  - `plugins/mill/skills/conversation/SKILL.md`
  - `plugins/mill/skills/code-quality/SKILL.md`
  - `plugins/mill/skills/code-comments/SKILL.md`
  - `plugins/mill/skills/testing/SKILL.md`
  - `plugins/mill/skills/handoff/SKILL.md`
- **Moves:** none
- **Requirements:**
  `git rm -r` the six skill directories (`prose`, `conversation`, `code-quality`, `code-comments`, `testing`, `handoff` under `plugins/mill/skills/`), then confirm none of the six directories remains on disk.
  `scribe:handoff` now serves `/handoff`; no caller references `mill:handoff` by qualified name.
- **Commit:** `chore(mill): delete generic skills now served by scribe`

### Card 6: Point the orchestrator Step-0 loads at scribe and mill:conventions

- **Context:**
  - `plugins/mill/skills/conventions/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
  - `.claude/skills/mill-pool/SKILL.md`
  - `doc/turn-reduction-audit.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Step-0 directive at each site becomes the bold heading "**Step 0: Load `scribe:prose`, then `scribe:conversation`, then `mill:conventions`.**" (mill-go-base keeps its "Step 0b" label).
  The follow-on sentence at each site becomes "Load all three skills via the Skill tool, unconditionally, immediately — before any other Entry step or phase; `scribe:conversation` builds on `scribe:prose`, and `mill:conventions` builds on both, so load them in that order." keeping each site's own timing clause (mill-go-base: "immediately after Step 0 and before any other Entry step or phase"; mill-pool: "before any other Entry step").
  - `mill-start/SKILL.md`: Entry Step 0 (the three lines at ~88-90), with the numbered-options sentence naming `scribe:conversation`;
    line ~25 becomes "per the `scribe:conversation` rule "the recommended option, if any, is option 1"" (scribe's actual wording);
    line ~407 `mill:conversation` -> `scribe:conversation`.
  - `mill-plan/SKILL.md`: Entry Step 0 (~16-18), with the defensive-load sentence naming `scribe:conversation`'s numbered-options convention and `scribe:prose`'s writing rules;
    line ~262 "`csharp-build` defines no lint command" -> "`scribe:csharp-build` defines no lint command".
  - `mill-go-base/SKILL.md`: Step 0b (~48-50), same defensive-load sentence rewrite.
  - `.claude/skills/mill-pool/SKILL.md`: Step 0 (~29-30);
    line ~85 "(see its CLAUDE.md and the mill:conversation skill, which mill-start loads itself as its own first step; ...)" -> "(see its CLAUDE.md and the `mill:conventions` skill, which mill-start loads itself as its own first step; ...)";
    line ~104 "per the mill:conversation numbered-options convention" -> "per the `scribe:conversation` numbered-options convention".
  - `doc/turn-reduction-audit.md`: the three Step-0 entries (~65, ~228, ~477) "load `mill:prose`/`mill:conversation`" -> "load `scribe:prose`/`scribe:conversation`/`mill:conventions`"; leave their line-number citations as they are.
  - After editing, `grep -nE "mill:(prose|conversation|code-quality|code-comments|testing|handoff)"` over the five files returns nothing.
- **Commit:** `refactor(mill): load scribe:prose, scribe:conversation, mill:conventions at orchestrator Step 0`

### Card 7: Qualify skill references across the remaining mill skills and templates

- **Context:**
  - `plugins/mill/skills/conventions/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-self-report/SKILL.md`
  - `plugins/mill/skills/ask-thread/SKILL.md`
  - `plugins/mill/skills/git-commit/SKILL.md`
  - `plugins/mill/skills/git-pr/SKILL.md`
  - `plugins/mill/skills/workflow/SKILL.md`
  - `plugins/mill/skills/mill-go2/SKILL.md`
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `mill-setup` ~259, `mill-merge` ~55, `mill-self-report` ~75, `ask-thread` ~48: `mill:conversation` -> `scribe:conversation`, rest of each sentence unchanged.
  - `mill-setup` `## Preconditions`: add a last bullet: "`scribe@scribe` is installed and enabled — mill declares it as a dependency and fails to load without it; if the `scribe` marketplace is not yet added on this machine, run `/plugin marketplace add Knatte18/scribe` and `/plugin install scribe@scribe` before installing mill".
  - `git-commit` ~19: "the delegated `{lang}-build` skill" -> "the delegated `scribe:{lang}-build` skill", and "(e.g. golang-build's Tool Installation section" -> "(e.g. `scribe:golang-build`'s Tool Installation section".
  - `workflow` Skill Invocation Table: `@mill:code-quality` -> `@scribe:code-quality`;
    `@mill:testing` (+ language-specific `{lang}-testing`) -> `@scribe:testing` (+ language-specific `scribe:{lang}-testing`);
    the language-specific row's `@{lang}:{lang}-*` -> `@scribe:{lang}-*`;
    `@mill:prose` -> `@scribe:prose`;
    `@mill:conversation` -> `@scribe:conversation`;
    append the row "| For mill-specific operating rules (new-thread prompts, `_mill/` state, worktree isolation) | `@mill:conventions` |".
    Language Detection table: `@python:python-build`, `python-comments`, `python-testing` -> `@scribe:python-build`, `scribe:python-comments`, `scribe:python-testing`, and the C# and Go rows likewise.
  - `mill-go2` ~16 (`## Driver preamble`): `mill:code-quality` -> `scribe:code-quality`, `mill:prose` -> `scribe:prose`, and each language trio `python:python-*`, `csharp:csharp-*`, `golang:golang-*` -> `scribe:python-*`, `scribe:csharp-*`, `scribe:golang-*`.
    Keep the line starting "Before Step 0" (`test-mill-go-variants.py` asserts it).
  - `review-output.schema.md` ~68: "per `prose`'s Markdown section" -> "per `scribe:prose`'s Markdown section".
  - After editing, `grep -nE "mill:(prose|conversation|code-quality|code-comments|testing|handoff)|(^|[^_[:alnum:]])(python|csharp|golang):(python|csharp|golang)-"` over the eight files returns nothing.
- **Commit:** `refactor(mill): qualify generic and language skill references as scribe:*`

### Card 8: Qualify the language skills the implementer agents load

- **Context:**
  - `plugins/mill/unit_tests/test-agents-defs.py`
  - `plugins/mill/.claude-plugin/plugin.json`
- **Edits:**
  - `plugins/mill/agents/mill-implementer.md`
  - `plugins/mill/agents/mill-implementer-low.md`
  - `plugins/mill/agents/mill-implementer-medium.md`
  - `plugins/mill/agents/mill-implementer-high.md`
  - `plugins/mill/agents/mill-implementer-max.md`
  - `plugins/mill/agents/mill-implementer-xhigh.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Apply the identical edit to all six bodies (`test_implementer_agents_background_verify_guidance` requires the bodies after the frontmatter to stay byte-identical):
  - "for Go files load `golang-comments` and `golang-testing`;" -> "for Go files load `scribe:golang-comments` and `scribe:golang-testing`;", and the Python and C# lines likewise (`scribe:python-comments`, `scribe:python-testing`, `scribe:csharp-comments`, `scribe:csharp-testing`).
  - "Always load `code-quality` when making edits." -> "Always load `scribe:code-quality` when making edits."
  - "- **Skill**: Invoke mill skills" -> "- **Skill**: Invoke mill and scribe skills".
  Frontmatter stays unchanged.
- **Commit:** `refactor(mill): implementer agents load scribe-qualified language skills`

### Card 9: Emit scribe-qualified names from language_skills_directive

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - `_agent_dispatch.language_skills_directive`: base list `skills = ["`scribe:prose`", "`scribe:code-quality`"]`; per detected language append `` f"`scribe:{prefix}-comments`" `` and `` f"`scribe:{prefix}-testing`" ``.
    `LANG_MAP` prefixes stay `golang`/`python`/`csharp`.
    Docstring: "names the matching ``scribe:{lang}-comments`` and ``scribe:{lang}-testing`` skills plus ``scribe:prose`` and ``scribe:code-quality`` for all batches."
    Module docstring (~51): "naming the required language skills plus prose and code-quality" -> "naming the required scribe language skills plus scribe:prose and scribe:code-quality".
  - `test-language-skills-directive.py`: qualify every expected name, positive and negative (a negative check on "`python-comments`" would pass vacuously once the output reads "`scribe:python-comments`"), including the `directive.count(...)` checks and the rendered-template check "python-comments" -> "scribe:python-comments".
    Update the module docstring's Covers list the same way.
    Scenarios stay as they are (Go-only, Python-only, C#-only, mixed, no-language, Context excluded, render, Move-only).
- **Commit:** `refactor(mill): language_skills_directive names scribe-qualified skills`

### Card 10: Update script docstrings that cite the retired skills

- **Context:**
  - `plugins/mill/unit_tests/test-inplace.py`
- **Edits:**
  - `plugins/mill/scripts/_inplace.py`
  - `plugins/mill/scripts/tools/mdreflow/mdreflow.py`
  - `plugins/mill/scripts/tools/pydocreflow/pydocreflow.py`
  - `plugins/mill/scripts/millpy-skills-index.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Docstring-only edits; no code change.
  - `_inplace.py` ~70: "per ``mill:conversation`` conventions" -> "per ``scribe:conversation`` conventions".
  - `mdreflow.py` module docstring: line 1 "the mill:prose skill's semantic-line-break rule" -> "the scribe:prose skill's semantic-line-break rule";
    the "per plugins/mill/skills/prose/SKILL.md's "Line breaks" section" clause (~4-5) -> "per the `scribe:prose` skill's Line breaks section", with no path.
  - `pydocreflow.py` module docstring ~4-5: "per the python-comments skill's "Line-wrap style" section (plugins/python/skills/python-comments/SKILL.md)" -> "per the `scribe:python-comments` skill's line-wrap rule", with no path.
  - `millpy-skills-index.py` ~63: "allowed by the `prose` skill's Markdown section" -> "allowed by the `scribe:prose` skill's Markdown section".
  - Re-flow only the lines you change; keep the docstrings' existing wrap style.
- **Commit:** `docs(mill): point script docstrings at scribe skills`

### Card 11: Regenerate SKILLS.md and sweep for leftover references

- **Context:**
  - `plugins/mill/skills/mill-skills-index/SKILL.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Regenerate from this worktree's scanner, from the worktree root: `PYTHONPATH=plugins/mill/scripts uv run --project plugins/mill python plugins/mill/scripts/millpy-skills-index.py`.
    Confirm the diff drops the `golang`, `csharp`, `python` plugin sections and the six deleted mill skills, and adds `conventions`.
  - Repo-wide sweeps, excluding `_mill/`, `.git/`, `.scratch/` and any `.venv`/`node_modules`:
    `grep -rnE "mill:(prose|conversation|code-quality|code-comments|testing|handoff)"` and `grep -rnE "(^|[^_[:alnum:]])(python|csharp|golang):(python|csharp|golang)-"` return nothing outside `plugins/mill/unit_tests/test-load-directive-convention.py`;
    `grep -rnE '`(prose|conversation|code-quality|code-comments|testing|handoff)`' plugins/mill .claude/skills doc` — review each hit: a bare skill-name reference to one of the deleted skills is a defect to report (cards 6-10 should have covered them all), while ordinary words and scribe-qualified names are fine.
    Fix nothing outside this card's `Edits:`; report any stray hit with its file and line instead.
  - Run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-load-directive-convention.py` and confirm every test passes.
- **Commit:** `chore: regenerate SKILLS.md for the scribe migration`

## Batch Tests

`verify:` runs the tests whose subject this batch changes:
`test-load-directive-convention.py` (card 3's rewritten guard: load order over every shipped SKILL.md/template and the forbidden-name scan over every shipped file, including `SKILLS.md`),
`test-language-skills-directive.py` (card 9),
`test-agents-defs.py` (card 8's byte-identical implementer bodies),
`test-mill-go-variants.py` (card 7's `mill-go2` preamble),
`test-skills-index.py` (card 11's scanner, confirming it does not depend on the removed plugin directories),
`test-inplace.py` (card 10's `_inplace.py` docstring edit),
`test-skill-helper-drift.py` and `test-guards.py` (both scan shipped SKILL.md files, so they cover card 4's new `conventions` skill and the edited skills).
