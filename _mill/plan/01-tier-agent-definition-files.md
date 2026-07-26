# Batch: tier-agent-definition-files

```yaml
task: "Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)"
batch: "tier-agent-definition-files"
number: 1
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-agents-defs.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Ship the six static per-effort-tier agent-definition files (`mill-reviewer-medium.md`,
`mill-reviewer-high.md`, `mill-reviewer-max.md`, `mill-implementer-medium.md`,
`mill-implementer-high.md`, `mill-implementer-max.md`) that a later batch's
`_agent_dispatch.resolve_subagent_type` will dispatch to by name, register them in
`plugin.json` so they are actually dispatchable (see Card 4 — `mill`'s plugin manifest
opts out of directory-based auto-discovery by declaring an explicit `agents` array, so
a file merely existing under `agents/` is not enough), and add the test coverage that
locks their frontmatter invariants and manifest registration in place. The next batch
(`subagent-type-effort-wiring`) is the one that starts computing subagent_type strings
pointing at these files, which is why it depends on this batch landing first: a real
Agent-tool dispatch must never resolve to a `subagent_type` with no matching,
registered agent definition.

Per the overview's Shared Decision "new agent-definition files are byte-identical to
their base except name and effort": every new file is a verbatim copy of its base
file's `description:` and body; only `name:` and an appended `effort:` frontmatter
line differ.

## Cards

### Card 1: Extend `test-agents-defs.py` with per-tier frontmatter checks

- **Context:**
  - `plugins/mill/agents/mill-reviewer.md`
  - `plugins/mill/agents/mill-implementer.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-agents-defs.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a module-level helper `_check_tier_agent_definition(agent_file: Path, base_file: Path, expected_effort: str) -> None` to `plugins/mill/unit_tests/test-agents-defs.py`, placed after the existing `_extract_frontmatter` function and before `test_reviewer_agent_definition`. It must:
  - Assert `agent_file.exists()`.
  - Parse both `agent_file` and `base_file` with the existing `_extract_frontmatter` helper; assert both parses are non-`None`.
  - Assert the tier file's `name` equals `agent_file.stem` (e.g. `mill-reviewer-high`).
  - Assert the tier file's `description` equals the base file's `description` exactly (same string, unchanged) — reads the base file's description dynamically rather than hardcoding it, so the check cannot drift from the base file's actual text.
  - Normalize and compare `tools` the same way `test_reviewer_agent_definition` already does (split on comma/whitespace, strip, set) — assert the tier file's tools set equals the base file's tools set exactly.
  - Assert the tier file's `effort` frontmatter key equals `expected_effort`.
  - Assert `"model" not in fm` for the tier file (same invariant `test_reviewer_agent_definition`/`test_implementer_agent_definition` already enforce on the base files).
  - `print(f"PASS _check_tier_agent_definition ({agent_file.name})")` on success (called from each of the six thin test functions below, so the helper itself does not need its own registration in `main()`'s `tests` list — only the six callers below are registered).

  Add six thin test functions, each calling the helper above with `HUB / "plugins" / "mill" / "agents" / "<file>"` as `agent_file`, the matching base file as `base_file`, and the matching tier string as `expected_effort`:
  - `test_reviewer_medium_agent_definition` -> `mill-reviewer-medium.md`, base `mill-reviewer.md`, `"medium"`
  - `test_reviewer_high_agent_definition` -> `mill-reviewer-high.md`, base `mill-reviewer.md`, `"high"`
  - `test_reviewer_max_agent_definition` -> `mill-reviewer-max.md`, base `mill-reviewer.md`, `"max"`
  - `test_implementer_medium_agent_definition` -> `mill-implementer-medium.md`, base `mill-implementer.md`, `"medium"`
  - `test_implementer_high_agent_definition` -> `mill-implementer-high.md`, base `mill-implementer.md`, `"high"`
  - `test_implementer_max_agent_definition` -> `mill-implementer-max.md`, base `mill-implementer.md`, `"max"`

  Register all six new functions in `main()`'s `tests` list, after the existing `test_implementer_agent_definition` entry, in the same order listed above.

  This card is written and run first (it will fail on missing files until Cards 2 and 3 land) — the TDD candidate named in `_mill/discussion.md`'s Testing section.
- **Commit:** `test(mill): add per-tier agent-definition frontmatter checks`

### Card 2: Create the three reviewer tier files

- **Context:**
  - `plugins/mill/agents/mill-reviewer.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/agents/mill-reviewer-medium.md`
  - `plugins/mill/agents/mill-reviewer-high.md`
  - `plugins/mill/agents/mill-reviewer-max.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create each file as a byte-for-byte copy of `plugins/mill/agents/mill-reviewer.md`'s current content, with exactly two changes per file:
  1. The frontmatter `name: mill-reviewer` line becomes `name: mill-reviewer-<tier>` (`mill-reviewer-medium`, `mill-reviewer-high`, `mill-reviewer-max` respectively).
  2. A new line `effort: <tier>` (`effort: medium`, `effort: high`, `effort: max` respectively) is appended immediately after the `tools: Read, Grep, Glob, Write` line, before the closing `---`.

  The `description:` line, the `tools:` line, and the entire body below the closing `---` (the `# mill-reviewer` heading and all prose, including its literal "mill-reviewer" self-references) are copied unchanged — do not rewrite the H1 heading or any prose to reference the new tier name. This matches the overview's Shared Decision "new agent-definition files are byte-identical to their base except name and effort."
- **Commit:** `feat(mill): add mill-reviewer-medium/high/max agent definitions`

### Card 3: Create the three implementer tier files

- **Context:**
  - `plugins/mill/agents/mill-implementer.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/agents/mill-implementer-medium.md`
  - `plugins/mill/agents/mill-implementer-high.md`
  - `plugins/mill/agents/mill-implementer-max.md`
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Create each file as a byte-for-byte copy of `plugins/mill/agents/mill-implementer.md`'s current content, with exactly two changes per file:
  1. The frontmatter `name: mill-implementer` line becomes `name: mill-implementer-<tier>` (`mill-implementer-medium`, `mill-implementer-high`, `mill-implementer-max` respectively).
  2. A new line `effort: <tier>` (`effort: medium`, `effort: high`, `effort: max` respectively) is appended immediately after the `tools: Read, Edit, Write, Bash, Grep, Glob, Skill` line, before the closing `---`.

  The `description:` line, the `tools:` line, and the entire body below the closing `---` (the `# mill-implementer` heading, all prose, and the "Test Integrity Guardrail" section) are copied unchanged. This matches the overview's Shared Decision "new agent-definition files are byte-identical to their base except name and effort."
- **Commit:** `feat(mill): add mill-implementer-medium/high/max agent definitions`

### Card 4: Register the six new agent files in `plugin.json`

- **Context:** none
- **Edits:**
  - `plugins/mill/.claude-plugin/plugin.json`
  - `plugins/mill/unit_tests/test-agents-defs.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `plugins/mill/.claude-plugin/plugin.json` currently declares:
  ```json
  "agents": [
    "./agents/mill-implementer.md",
    "./agents/mill-reviewer.md"
  ]
  ```
  Per Claude Code's plugin manifest reference, an explicit `agents` field *replaces*
  the default directory scan of `agents/` — files present in that directory but not
  listed here are never registered as dispatchable `subagent_type`s. Add the six new
  tier files, alphabetically sorted for readability:
  ```json
  "agents": [
    "./agents/mill-implementer.md",
    "./agents/mill-implementer-high.md",
    "./agents/mill-implementer-max.md",
    "./agents/mill-implementer-medium.md",
    "./agents/mill-reviewer.md",
    "./agents/mill-reviewer-high.md",
    "./agents/mill-reviewer-max.md",
    "./agents/mill-reviewer-medium.md"
  ]
  ```

  In `plugins/mill/unit_tests/test-agents-defs.py`, add a new test function
  `test_plugin_json_registers_all_agent_files`, placed after the six per-tier test
  functions Card 1 adds and before `main()`. It must:
  - Read and `json.load` `plugins/mill/.claude-plugin/plugin.json` (add `import json`
    at the top of the file if not already present).
  - Glob `plugins/mill/agents/*.md` for every agent-definition file actually on disk.
  - Assert the manifest's `agents` array, normalized to a set of `<name>.md` basenames
    (stripping the `./agents/` prefix), equals the set of `.md` filenames the glob
    found — exactly, not a subset either direction.
  - This guards against the exact class of gap this card fixes: a future agent file
    added to the directory without a matching `plugin.json` entry, or a stale entry
    left behind after a file is removed.

  Register the new function last in `main()`'s `tests` list, after the six per-tier
  functions added in Card 1.
- **Commit:** `fix(mill): register per-tier agent definitions in plugin.json`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-agents-defs.py` directly (single file, matches
the SKILL.md's documented single-test-file `verify:` pattern). It exercises every file
this batch touches: the two existing base-file tests, the six new per-tier tests added
in Card 1 (which in turn require Cards 2 and 3's created files to exist and carry
correct frontmatter), and Card 4's manifest-registration test (which requires Cards 2
and 3's files to exist on disk for its glob comparison, and Card 4's own `plugin.json`
edit to match). All four cards must land before `verify:` can pass.
