# Batch: subagent-definitions

```yaml
task: "Replace subprocess LLM dispatch with the Claude Code Agent tool"
batch: subagent-definitions
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agents-defs.py
depends-on: []
```

## Batch Scope

Ships the two plugin-provided sub-agent type definitions the SKILLs reference by
`subagent_type` in agent mode: `mill-reviewer` (hard read-only) and
`mill-implementer` (full worker tools), plus the plugin-manifest wiring so they
resolve wherever the mill plugin is installed (including external consumer
repos). A config-level test enforces the read-only tool set, which is the
constraint that makes the reviewer safe. No Python behavior depends on this
batch at runtime; the SKILLs (batches 5-6) name these types.

## Cards

### Card 6: Author the two sub-agent definition files

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/agents/mill-reviewer.md`
  - `plugins/mill/agents/mill-implementer.md`
- **Deletes:** none
- **Requirements:** Each file is a Claude Code sub-agent definition: YAML
  frontmatter followed by a system-prompt body. `mill-reviewer.md` frontmatter:
  `name: mill-reviewer`, a one-line `description`, and `tools: Read, Grep, Glob`
  (read-only allow-list -- MUST NOT include Edit, Write, Bash, or NotebookEdit;
  this is the faithful port of `_llm_claude`'s
  `--disallowedTools Edit,Write,Bash,NotebookEdit` at line ~138). Its body states
  it is a read-only reviewer that must not modify files or run commands and that
  its sole output is its final message. `mill-implementer.md` frontmatter:
  `name: mill-implementer`, a one-line `description`, and
  `tools: Read, Edit, Write, Bash, Grep, Glob, Skill` (matching
  `run_implementer`'s allow-list at `_llm_claude.py:508`). Do NOT set a `model:`
  field in either (the per-call `model` override supplies the tier). Bodies are
  short -- the per-dispatch brief carries the actual task instructions.
- **Commit:** `feat(agents): add mill-reviewer and mill-implementer subagents`

### Card 7: Declare plugin-provided agents in the manifest

- **Context:**
  - `plugins/mill/agents/mill-reviewer.md`
  - `plugins/mill/agents/mill-implementer.md`
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/.claude-plugin/plugin.json`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Make the two agent definitions discoverable as plugin-provided
  sub-agent types. First determine the convention the installed Claude Code
  plugin loader uses: skills are auto-discovered from `plugins/mill/skills/<name>/`
  with no manifest field, so the analogous `plugins/mill/agents/<name>.md`
  directory is the expected auto-discovery location. If auto-discovery from an
  `agents/` directory is supported, no `plugin.json` change is required beyond
  confirming the directory name -- in that case leave `plugin.json` unchanged and
  record the finding in the commit message. If the loader instead requires an
  explicit manifest field, add it (e.g. `"agents": "agents/"`) to `plugin.json`,
  preserving the existing keys (`name`, `description`, `version`, `license`,
  `author`) and valid JSON. Do not invent a field that the loader does not read.
- **Commit:** `feat(agents): make mill subagents plugin-discoverable`

### Card 8: Test the sub-agent tool-set constraints

- **Context:**
  - `plugins/mill/agents/mill-reviewer.md`
  - `plugins/mill/agents/mill-implementer.md`
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-agents-defs.py`
- **Deletes:** none
- **Requirements:** New `test-agents-defs.py` parses the YAML frontmatter of both
  agent files (reuse the project's existing frontmatter-parsing approach; both
  files exist at `plugins/mill/agents/`). Assert: `mill-reviewer`'s `tools` list,
  normalized, equals exactly `{Read, Grep, Glob}` and contains NONE of
  `{Edit, Write, Bash, NotebookEdit}`; `mill-implementer`'s `tools` includes
  `{Read, Edit, Write, Bash, Grep, Glob, Skill}`; both have a `name` matching the
  filename stem and a non-empty `description`; neither sets a `model:` field. Use
  the repo path-resolution pattern to locate the agents dir (no hard-coded
  absolute paths).
- **Commit:** `test(agents): enforce reviewer read-only tool set`

## Batch Tests

`verify:` runs the new `test-agents-defs.py`, which statically validates the two
agent-definition files' frontmatter -- the security-critical assertion being
that `mill-reviewer` grants no mutating tools. Pure file-parsing test; no git,
LLM, or plugin-loader runtime needed.
