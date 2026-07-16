# Batch: permission-allowlist

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: permission-allowlist
number: 4
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-settings.py
depends-on: []
```

## Batch Scope

This batch closes #631: a background `mill-implementer`/`mill-reviewer` subagent blocked on an interactive tool-permission prompt is indistinguishable from a genuinely running one via `TaskOutput`. Per discussion.md's decision, the fix is a bare-tool-name permission allowlist merged into the operator's global `~/.claude/settings.json` (not this repo's own `.claude/settings.json`, which is never present when mill-go orchestrates an external repo). This batch touches only a new helper module and `mill-setup`'s SKILL.md — no file overlap with Batches 1–3, so it has no dependency.

## Cards

### Card 18: `_claude_settings.py` — permission-allowlist merge helper

- **Context:**
  - `plugins/mill/scripts/_vscode.py`
  - `plugins/mill/agents/mill-implementer.md`
  - `plugins/mill/agents/mill-reviewer.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_claude_settings.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/scripts/_claude_settings.py` with a module docstring (mirroring `_vscode.py`'s style) and a public function `merge_permission_allowlist(settings_path: Path, tool_names: list[str]) -> dict`. Behavior: read `settings_path` as JSON if it exists (`json.loads(settings_path.read_text(encoding="utf-8"))`), else start from `{}`. Get or create `data.setdefault("permissions", {})`, then `permissions.setdefault("allow", [])`. For each name in `tool_names`, append it to `allow` only if not already present (preserve existing order, append new entries at the end, no duplicates) — do not touch `permissions["deny"]`, `permissions["additionalDirectories"]`, or any other top-level key (`env`, `model`, `hooks`, etc.) if present. Write the updated `data` back to `settings_path` via `settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")` only if the `allow` list actually changed (idempotent no-op write-skip when every name was already present, mirroring Phase 4.8's existing `if env_block.get('MILL_PYTHON') == mill_python: print('already correct')` early-exit pattern). Return the final `data` dict. Define a module-level constant `MILL_SUBAGENT_TOOLS = ["Bash", "Read", "Edit", "Write", "Grep", "Glob", "Skill"]` — the alphabetically-sorted union of `mill-implementer.md`'s (`Read, Edit, Write, Bash, Grep, Glob, Skill`) and `mill-reviewer.md`'s (`Read, Grep, Glob, Write`) `tools:` frontmatter — as the single source of truth Phase 4.8 (Card 19) imports and passes as `tool_names`, so the allowlist and the two agent definitions cannot silently drift apart.
- **Commit:** `feat(claude-settings): add permission-allowlist merge helper (#631)`

### Card 19: `mill-setup` Phase 4.8 merges the mill subagent tool allowlist

- **Context:**
  - `plugins/mill/scripts/_claude_settings.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-setup/SKILL.md`'s "### Phase 4.8 — Write `MILL_PYTHON` to `~/.claude/settings.json`" section (lines 347-371), extend the inline `-c "..."` Python block (lines 352-368) to also call the new helper: after the existing `import json, os` / `from pathlib import Path` imports, add `import sys; sys.path.insert(0, os.environ['CLAUDE_PLUGIN_ROOT'] + '/scripts'); import _claude_settings`. After the existing `env_block` MILL_PYTHON-setting logic (which currently ends with either the "already correct" print or the `settings_path.write_text(...)` + "set" print), add a call to `_claude_settings.merge_permission_allowlist(settings_path, _claude_settings.MILL_SUBAGENT_TOOLS)` and print its own result line (e.g. `f"Permission allowlist merged: {_claude_settings.MILL_SUBAGENT_TOOLS}"` — the helper's own internal idempotent no-op check means this is safe to call unconditionally on every mill-setup run, matching the existing MILL_PYTHON write's idempotency). Update the section's prose (the paragraph before the code block) to mention that this phase also merges the mill subagent's tool surface into `permissions.allow` so background agent-mode dispatches don't stall on interactive approval prompts, and note that unlike the `MILL_PYTHON` env write it does not require a session restart to take effect (permission allowlist entries apply to new tool calls, not to already-active session state). Update the "Log the result" instruction (line 371) to also report the permission-allowlist merge outcome alongside the existing `MILL_PYTHON set...` message.
- **Commit:** `feat(mill-setup): merge mill subagent permission allowlist in Phase 4.8 (#631)`

## Batch Tests

`verify:` runs a new `test-claude-settings.py` (new file, following this repo's existing in-memory/tempfile fixture convention per `CLAUDE.md`) covering `merge_permission_allowlist`: (a) starting from a settings file that does not exist yet creates it with `permissions.allow` containing exactly `MILL_SUBAGENT_TOOLS`; (b) a pre-existing custom `permissions.allow`/`deny`/`additionalDirectories` block (mirroring the shape this operator's real `~/.claude/settings.json` already has: bare tool names in `allow`, specific git-command patterns in `deny`) survives the merge with the new tool names appended and no existing entries removed, duplicated, or reordered; (c) calling the function twice in a row (idempotency) produces the same `allow` list both times and the second call's write is skipped entirely (assert via a mtime/no-op check or by asserting the returned dict content is identical, per whatever mechanism this test file's fixture pattern supports); (d) `MILL_SUBAGENT_TOOLS`'s content is asserted directly against `mill-implementer.md`'s and `mill-reviewer.md`'s current `tools:` frontmatter (parsed from those files) rather than hardcoded twice, so the two can never silently drift.
