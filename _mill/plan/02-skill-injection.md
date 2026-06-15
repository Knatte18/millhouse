# Batch: skill-injection

```yaml
task: "Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading"
batch: skill-injection
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-language-skills-directive.py test-agents-defs.py
depends-on: [1]
```

## Batch Scope

This batch closes #483: spawned implementer/fixer sub-agents never load the language style skills. It adds a directive builder (`_agent_dispatch.language_skills_directive`) that language-detects a batch's touched files and emits a non-optional "load these skills" block, injects that block into both per-batch brief templates through a new `<LANGUAGE_SKILLS>` token (also fixing the briefs' `## Tools` sections, which omit `Skill`), and adds a generic backstop line to the implementer agent definition. Depends on batch 1 because both batches edit `_agent_dispatch.py` and `millpy-implement.py`; sequencing avoids overlapping writes. `_render.render` raises `KeyError` on any unresolved `<TOKEN>`, so the template token and its `values` entry are always added in the same card; the only renderers of these templates are `millpy-implement.py` and `millpy-fix.py`, both updated here.

## Cards

### Card 4: Add the language-skills directive builder

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Deletes:** none
- **Requirements:** Add `language_skills_directive(batch_file: Path) -> str` to `_agent_dispatch.py`, importing `parse_batch_refs` from `_review_common` (confirmed no import cycle — neither `_review_common` nor `_reviewers` imports `_agent_dispatch`). The function: calls `parse_batch_refs(batch_file)` to get the touched path strings; detects languages by file suffix using the map `{".go": ("Go", "golang"), ".py": ("Python", "python"), ".cs": ("C#", "csharp")}` (dedup, preserve first-seen order); builds a markdown directive that ALWAYS names the `code-quality` skill and, for each detected language, additionally names `<prefix>-comments` and `<prefix>-testing` (e.g. Go → `golang-comments`, `golang-testing`). Wording must be non-optional, e.g. a `## Required skills` block reading "Before editing any file, load and follow these skills (non-optional): ..." listing the backtick-wrapped skill names; when languages are detected, mention which (e.g. "This batch touches Go files."). When no recognized language is detected, the block still names `code-quality` only. Add the function to the module's `__all__` and docstring. Create `test-language-skills-directive.py` (follow the `sys.path.insert` + `test_*` + `print("PASS ...")` + `__main__` runner pattern of `test-agent-dispatch.py`); write temp batch files via `tempfile` referencing only `.go` (assert directive contains `golang-comments`, `golang-testing`, `code-quality`, and not `python-comments`), only `.py` (assert python variants), mixed `.go`+`.py` (assert both language sets present and `code-quality` appears exactly once), and only `.md`/`.yaml` files (assert `code-quality` present and no `-comments`/`-testing` substring).
- **Commit:** `feat(agent-dispatch): add language_skills_directive builder`

### Card 5: Inject the directive into the implementer brief

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `templates/implementer-brief.md`: (a) add a `<LANGUAGE_SKILLS>` token on its own line in an early section placed just before `## Implementation discipline`; (b) change the `## Tools` "Available:" line from `Available: Read, Edit, Write, Bash, Grep, Glob.` to `Available: Read, Edit, Write, Bash, Grep, Glob, Skill.`; (c) add `<LANGUAGE_SKILLS>` to the token list inside the leading HTML comment. In `millpy-implement.py`: add `"LANGUAGE_SKILLS": _agent_dispatch.language_skills_directive(batch_file)` to the tokens dict passed to `_render.render` (the dict containing `BATCH_NAME`/`BATCH_FILE`); `_agent_dispatch` and `batch_file` are already in scope. In `test-language-skills-directive.py`: add a test that renders `templates/implementer-brief.md` via `_render.render` with a sentinel `LANGUAGE_SKILLS` value (plus the other required tokens) and asserts the sentinel appears in the output AND the rendered `## Tools` "Available:" line contains `Skill`; register it in the `__main__` runner.
- **Commit:** `fix(implement): inject language-skills directive into implementer brief`

### Card 6: Inject the directive into the fixer brief

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_render.py`
- **Edits:**
  - `plugins/mill/templates/fixer-batch-brief.md`
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `templates/fixer-batch-brief.md`: (a) add a `<LANGUAGE_SKILLS>` token on its own line in an early section placed just before `## Fix discipline`; (b) change the `## Tools` "Available:" line to append `, Skill` (matching Card 5); (c) add `<LANGUAGE_SKILLS>` to the leading HTML-comment token list. In `millpy-fix.py`: add `"LANGUAGE_SKILLS": _agent_dispatch.language_skills_directive(batch_file)` to the per-batch fixer tokens dict passed to `_render.render` (the dict containing `REVIEW_FILE`/`BATCH_FILE`, in the `args.scope != "holistic"` branch); `batch_file` is in scope at that point. Import `_agent_dispatch` in `millpy-fix.py` if not already imported. Do NOT touch the holistic-fixer branch (out of scope). In `test-language-skills-directive.py`: add a test that renders `templates/fixer-batch-brief.md` with a sentinel `LANGUAGE_SKILLS` value and asserts the sentinel appears AND the rendered `## Tools` "Available:" line contains `Skill`; register it in the `__main__` runner.
- **Commit:** `fix(fix): inject language-skills directive into fixer brief`

### Card 7: Add language-skill backstop to the implementer agent definition

- **Context:**
  - `plugins/mill/unit_tests/test-agents-defs.py`
- **Edits:**
  - `plugins/mill/agents/mill-implementer.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `agents/mill-implementer.md`, after the closing paragraph ("The per-batch brief provides all instructions..."), add one backstop line instructing the agent to detect the implementation language from the files it edits and load the matching `{lang}-*` skills (e.g. `golang-comments`, `python-comments`, `csharp-comments`) plus `code-quality` before editing, in addition to any skills the brief names. Keep the existing YAML frontmatter (`name`, `description`, `tools: Read, Edit, Write, Bash, Grep, Glob, Skill`) unchanged so `test-agents-defs.py` still validates.
- **Commit:** `docs(agents): add language-skill backstop to mill-implementer`

## Batch Tests

`verify:` runs `test-language-skills-directive.py` (builder-logic table from Card 4: Go/Python/C#/mixed/no-language detection; plus the Card 5/6 render assertions that the `<LANGUAGE_SKILLS>` directive renders into BOTH the implementer and fixer briefs and that each brief's `## Tools` line names `Skill` — this is the guard against the silent-no-op case where a token is added to only one template) and `test-agents-defs.py` (validates the edited `mill-implementer.md` agent definition still parses with valid frontmatter). Scope matches this batch's `Edits:`/`Creates:`.
