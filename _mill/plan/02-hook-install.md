# Batch: hook-install

```yaml
task: "plan validator and wiki-guard hook false positives"
batch: "hook-install"
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-claude-settings.py
depends-on: [1]
```

## Batch Scope

Delivers the settings-file side of the wiki-guard fix: an idempotent reconcile that installs the new hook and retires the legacy inline one, wired into mill-setup Phase 4.8.
Depends on batch 1 only for the hook CLI script name.
Batch-local decision: the hook command template, staleness handling, and replace-in-place rules are fixed in discussion.md and repeated in the card requirements below.

## Cards

### Card 4: reconcile_wiki_guard_hook helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_claude_settings.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add to this module, following the `reconcile_destructive_denylist` pattern (load settings or start from an empty dict, mutate, write with `json.dumps(data, indent=2)` only when something changed, return the dict), and extend the module docstring's Public API and constants sections accordingly:
  - Constant `WIKI_GUARD_SCRIPT_NAME = "millpy-wiki-guard.py"`.
  - `build_wiki_guard_command(plugin_root: Path) -> str`: return exactly `PYTHONPATH="<plugin_root>/scripts" "$MILL_PYTHON" "<plugin_root>/scripts/millpy-wiki-guard.py"` where `<plugin_root>` is `plugin_root.as_posix()`.
  - `reconcile_wiki_guard_hook(settings_path: Path, hook_command: str) -> dict` operating on `data["hooks"]["PreToolUse"]`, a list of entries shaped `{"matcher": ..., "hooks": [{"type": "command", "command": ...}]}`:
    1. Among entries whose `matcher` is exactly `"Bash"`, find hook objects whose `command` contains `millpy-wiki-guard.py` (an older or current installed path) or contains both `daemon-owned` and the literal text `\.wiki\b` (the legacy inline grep hook).
    2. If exactly one such hook object already has `command == hook_command` and no other matching hook object exists, make no change.
    3. Otherwise replace the FIRST matching hook object in place with `{"type": "command", "command": hook_command}` and remove every other matching hook object. Only matching hook objects are touched: other hook objects in the same entry's `hooks` list are preserved, and an entry is dropped only when its `hooks` list becomes empty.
    4. When no matching hook object exists, append a new entry `{"matcher": "Bash", "hooks": [{"type": "command", "command": hook_command}]}` to `PreToolUse` (creating `hooks` and `PreToolUse` as needed).
    Never modify any other key, entry, or matcher (the Read/Edit/Write/Grep/Glob matcher entry, other event types, `permissions`, `env`).
- **Commit:** `feat(claude-settings): reconcile wiki-guard PreToolUse hook`

### Card 5: reconcile_wiki_guard_hook tests

- **Context:**
  - `plugins/mill/scripts/_claude_settings.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-claude-settings.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add test functions in the existing file's style (tempdir settings file, plain asserts, a `print("PASS ...")` line) and register each in `main()`'s `tests` list; extend the module docstring's coverage list. Cover: absent settings file gets one Bash entry with the command; the legacy inline hook entry (a Bash entry whose command mentions daemon-owned and the legacy grep pattern) is replaced in place, not duplicated, and the Read/Edit/Write/Grep/Glob matcher entry survives untouched; an entry containing an older versioned script path is replaced with the new command, not duplicated; a second identical call is a no-op that skips the write (file bytes unchanged); a Bash entry that shares its `hooks` list with an unrelated hook keeps the unrelated hook while the matching one is replaced; an entry whose only hook was the legacy one is not left empty; unrelated keys (`permissions`, `env`, other hook events) survive unchanged; `build_wiki_guard_command` output for a sample `Path` equals the exact template string.
- **Commit:** `test(claude-settings): cover wiki-guard hook reconcile`

### Card 6: mill-setup Phase 4.8 wiring

- **Context:**
  - `plugins/mill/scripts/_claude_settings.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In Phase 4.8 ("Write `MILL_PYTHON` to `~/.claude/settings.json`"): (a) in the descriptive paragraphs, add a short paragraph stating the phase also installs the wiki-guard PreToolUse Bash hook via `_claude_settings.reconcile_wiki_guard_hook`, replacing the legacy inline grep hook, that the hook command embeds the versioned plugin cache path and therefore fails open until this phase is re-run after a plugin cache refresh, and that like the allowlist and denylist it takes effect immediately without a restart; (b) in the inline python script, after the `reconcile_destructive_denylist` call and its print, add `_claude_settings.reconcile_wiki_guard_hook(settings_path, _claude_settings.build_wiki_guard_command(plugin_root))` followed by `print('Wiki-guard hook reconciled')` (the script already binds `plugin_root`); (c) extend the "Log the result" sentence to include the hook-reconciliation outcome and the final emitted sentence to add `Wiki-guard hook reconciled in ~/.claude/settings.json -- takes effect immediately, no restart needed.`. Keep every existing line otherwise unchanged. Follow the SKILL's existing prose conventions (one sentence per line, ASCII arrows and dashes in emitted strings).
- **Commit:** `docs(mill-setup): install wiki-guard hook in Phase 4.8`

## Batch Tests

`verify:` runs `test-claude-settings.py` only, the file card 5 extends and the only test that imports `_claude_settings`; the SKILL edit has no runnable surface beyond that helper.
