# Batch: skill-injection

```yaml
task: "Fix batch-name sanitization (colon/slash on Windows) and implementer skill loading"
batch: skill-injection
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-language-skills-directive.py test-review-common.py test-agents-defs.py
depends-on: [1]
```

## Batch Scope

This batch closes #483: spawned implementer/fixer sub-agents never load the language style skills. It adds a directive builder (`_agent_dispatch.language_skills_directive`) that language-detects a batch's touched files and emits a non-optional "load these skills" block, injects that block into both per-batch brief templates through a new `<LANGUAGE_SKILLS>` token (also fixing the briefs' `## Tools` sections, which omit `Skill`), and adds a generic backstop line to the implementer agent definition. Depends on batch 1 because both batches edit `_agent_dispatch.py` and `millpy-implement.py`; sequencing avoids overlapping writes. `_render.render` raises `KeyError` on any unresolved `<TOKEN>`, so the template token and its `values` entry are always added in the same card; the only renderers of these templates are `millpy-implement.py` and `millpy-fix.py`, both updated here.

## Cards

### Card 4: Add the language-skills directive builder

- **Context:**
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_review_common.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Deletes:** none
- **Requirements:** First, in `_review_common.py`, extend `parse_batch_refs` with an optional keyword param: `parse_batch_refs(batch_path: Path, fields: tuple[str, ...] = ("Context", "Edits", "Creates", "Deletes")) -> list[str]`. Inside the loop, after `m = _RE_REFS_HEADER.match(...)`, skip the header unless `m.group(1) in fields` (group 1 is the field name `Context|Edits|Creates|Deletes`). The default tuple preserves existing behavior exactly, so the existing `parse_batch_refs` callers (plan-review/code-review bulking) are unaffected; update the docstring to document the new param. Then add `language_skills_directive(batch_file: Path) -> str` to `_agent_dispatch.py`, importing `parse_batch_refs` from `_review_common` (confirmed no import cycle — neither `_review_common` nor `_reviewers` imports `_agent_dispatch`). The function: calls `parse_batch_refs(batch_file, fields=("Edits", "Creates"))` to get only the **touched** path strings (NOT `Context:` — read-only refs must not trigger a directive, per Shared Decision `targeted-skill-injection`); detects languages by file suffix using the map `{".go": ("Go", "golang"), ".py": ("Python", "python"), ".cs": ("C#", "csharp")}` (dedup, preserve first-seen order); builds a markdown block that begins with the heading `## Required skills` and ALWAYS names the `code-quality` skill and, for each detected language, additionally names `<prefix>-comments` and `<prefix>-testing` (e.g. Go → `golang-comments`, `golang-testing`). Wording must be non-optional, e.g. "Before editing any file, load and follow these skills (non-optional): ..." listing the backtick-wrapped skill names; when languages are detected, mention which (e.g. "This batch touches Go files."). When no recognized language is detected, the block still names `code-quality` only. Add the function to the module's `__all__` and docstring. Create `test-language-skills-directive.py` (follow the `sys.path.insert` + `test_*` + `print("PASS ...")` + `__main__` runner pattern of `test-agent-dispatch.py`); write temp batch files via `tempfile` with: only `.go` in `Edits:` (assert directive contains `golang-comments`, `golang-testing`, `code-quality`, and not `python-comments`); only `.py` in `Edits:` (assert python variants); mixed `.go`+`.py` in `Edits:`/`Creates:` (assert both language sets present and `code-quality` appears exactly once); only `.md`/`.yaml` in `Edits:` (assert `code-quality` present and no `-comments`/`-testing` substring); and a `.go` file in `Context:` only with a `.py` file in `Edits:` (assert the directive names python skills and NOT golang — proving `Context:` is excluded).
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
- **Requirements:** In `templates/implementer-brief.md`: (a) add a `<LANGUAGE_SKILLS>` token on its own line, on a blank line just before the `## Implementation discipline` heading (the token expands to the `## Required skills` block produced by `language_skills_directive`, so no surrounding heading is added in the template); (b) change the `## Tools` "Available:" line from `Available: Read, Edit, Write, Bash, Grep, Glob.` to `Available: Read, Edit, Write, Bash, Grep, Glob, Skill.`; (c) add `<LANGUAGE_SKILLS>` to the token list inside the leading HTML comment. In `millpy-implement.py`: add `"LANGUAGE_SKILLS": _agent_dispatch.language_skills_directive(batch_file)` to the tokens dict passed to `_render.render` (the dict containing `BATCH_NAME`/`BATCH_FILE`); `_agent_dispatch` and `batch_file` are already in scope. In `test-language-skills-directive.py`: add a test that renders `templates/implementer-brief.md` via `_render.render` with a sentinel `LANGUAGE_SKILLS` value (plus the other required tokens) and asserts the sentinel appears in the output AND the rendered `## Tools` "Available:" line contains `Skill`; register it in the `__main__` runner.
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
- **Requirements:** In `templates/fixer-batch-brief.md`: (a) add a `<LANGUAGE_SKILLS>` token on its own line, on a blank line just before the `## Fix discipline` heading (the token expands to the `## Required skills` block from `language_skills_directive`); (b) change the `## Tools` "Available:" line to append `, Skill` (matching Card 5); (c) add `<LANGUAGE_SKILLS>` to the leading HTML-comment token list. In `millpy-fix.py`: add `"LANGUAGE_SKILLS": _agent_dispatch.language_skills_directive(batch_file)` to the per-batch fixer tokens dict passed to `_render.render` (the dict containing `REVIEW_FILE`/`BATCH_FILE`, in the `args.scope != "holistic"` branch); `batch_file` is in scope at that point. Import `_agent_dispatch` in `millpy-fix.py` if not already imported. Do NOT touch the holistic-fixer branch (out of scope). In `test-language-skills-directive.py`: add a test that renders `templates/fixer-batch-brief.md` with a sentinel `LANGUAGE_SKILLS` value and asserts the sentinel appears AND the rendered `## Tools` "Available:" line contains `Skill`; register it in the `__main__` runner.
- **Commit:** `fix(fix): inject language-skills directive into fixer brief`

### Card 7: Add language-skill backstop to the implementer agent definition

- **Context:**
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Edits:**
  - `plugins/mill/agents/mill-implementer.md`
  - `plugins/mill/unit_tests/test-agents-defs.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `agents/mill-implementer.md`, after the closing paragraph ("The per-batch brief provides all instructions..."), add one backstop line instructing the agent to detect the implementation language from the files it edits and load the matching `{lang}-*` skills (e.g. `golang-comments`, `python-comments`, `csharp-comments`) plus `code-quality` before editing, in addition to any skills the brief names. Keep the existing YAML frontmatter (`name`, `description`, `tools: Read, Edit, Write, Bash, Grep, Glob, Skill`) unchanged so `test-agents-defs.py` still validates. Then, because `test-agents-defs.py` currently defines `test_reviewer_agent_definition` and `test_implementer_agent_definition` but has NO `if __name__ == "__main__"` runner — meaning `run-all.py` (which executes each file via `subprocess.run([sys.executable, test])`) imports it and exits 0 without running a single assertion — add a `__main__` runner block to `test-agents-defs.py` that calls both test functions (mirror the runner in `test-agent-dispatch.py`). This makes the batch `verify:` actually exercise the agent-definition check.
- **Commit:** `docs(agents): add language-skill backstop to mill-implementer`

## Batch Tests

`verify:` runs three files: `test-language-skills-directive.py` (builder-logic table from Card 4: Go/Python/C#/mixed/no-language detection, plus the `Context:`-excluded case; plus the Card 5/6 render assertions that the `<LANGUAGE_SKILLS>` directive renders into BOTH the implementer and fixer briefs and that each brief's `## Tools` line names `Skill` — the guard against the silent-no-op case where a token is added to only one template); `test-review-common.py` (regression guard for the `parse_batch_refs` `fields=` refactor in Card 4 — the default-behavior path must stay green); and `test-agents-defs.py` (validates the edited `mill-implementer.md` agent definition — note Card 7 adds the missing `__main__` runner so this file actually executes its assertions under `run-all.py`). Scope matches this batch's `Edits:`/`Creates:`.
