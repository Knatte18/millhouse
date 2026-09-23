# Batch: claude-settings-denylist

```yaml
task: 'mill-setup/wiki/docs/build-env: misc small bugs, round 3'
batch: claude-settings-denylist
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-settings.py
depends-on: []
```

## Batch Scope

Fixes GitHub issue #1127: `mill-setup` Phase 4.8 reconciles `permissions.allow` (via
`_claude_settings.merge_permission_allowlist`) but not `permissions.deny`. A common operator
`Bash(rm -rf:*)` deny rule is target-blind — it blocks `rm -rf` against a throwaway scratch dir
exactly as hard as `rm -rf ~`. This batch adds a sibling reconciliation function,
`reconcile_destructive_denylist`, to `_claude_settings.py`, wires it into Phase 4.8 next to the
existing allowlist merge, and adds test coverage to the existing test file, per `discussion.md`'s
`1127-denylist-shape` Decision. No external interface for another batch — self-contained.

## Cards

### Card 3: Add and wire `reconcile_destructive_denylist` for `permissions.deny`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_claude_settings.py`
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/unit_tests/test-claude-settings.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  **In `_claude_settings.py`:** add two new module-level constants and one new function, placed
  after the existing `MILL_SUBAGENT_TOOLS` constant and before `merge_permission_allowlist`:

  ```python
  RETIRED_DENY = ["Bash(rm -rf:*)", "Bash(rm -rf *)"]

  DESTRUCTIVE_DENY = [
      "Bash(rm -rf /)", "Bash(rm -rf /*)",
      "Bash(rm -rf ~)", "Bash(rm -rf ~/)", "Bash(rm -rf $HOME)",
      "Bash(rm -rf /home)", "Bash(rm -rf /Users)", "Bash(rm -rf /root)",
      "Bash(rm -rf /etc:*)", "Bash(rm -rf /usr:*)", "Bash(rm -rf /var:*)",
      "Bash(rm -rf /boot:*)", "Bash(rm -rf /opt:*)", "Bash(rm -rf /bin:*)",
      "Bash(rm -rf /lib:*)",
  ]
  ```

  `RETIRED_DENY` are the target-blind rules being retired. `DESTRUCTIVE_DENY` splits into two
  shapes: user-root entries (`/`, `~`, `~/`, `$HOME`, `/home`, `/Users`, `/root`) are exact-match
  only, so anything *below* those roots stays deletable; system-tree entries (`/etc`, `/usr`,
  `/var`, `/boot`, `/opt`, `/bin`, `/lib`) are prefix-matched with `:*`, since nothing under those
  roots is ever legitimately deleted recursively.

  Add `reconcile_destructive_denylist(settings_path: Path) -> dict`, mirroring
  `merge_permission_allowlist`'s exact shape and docstring conventions (module docstring, `Args:`/
  `Returns:` sections, idempotent read/change/write-only-if-changed pattern): read
  `settings_path` (or start from `{}` if it does not exist), read/create `data["permissions"]["deny"]`
  (via `data.setdefault("permissions", {}).setdefault("deny", [])`), remove every entry that is in
  `RETIRED_DENY` from that list, then append every entry from `DESTRUCTIVE_DENY` not already present
  (preserving existing order and every other pre-existing `deny` entry, exactly as
  `merge_permission_allowlist` preserves unrelated `allow` entries), set `changed = True` if either
  the removal or the addition actually altered the list, write the file back only when `changed`
  (via `json.dumps(data, indent=2)`, matching `merge_permission_allowlist`'s own write call), and
  return the resulting `data` dict. Never touch `permissions.allow`,
  `permissions.additionalDirectories`, or any other top-level key (`env`, `model`, `hooks`, etc.) —
  same non-interference guarantee `merge_permission_allowlist` already documents for `permissions.deny`.
  Update the module docstring's "Public API" section to list the new function alongside
  `merge_permission_allowlist`.

  **In `mill-setup/SKILL.md`'s `### Phase 4.8` section:** in the fenced bash block, immediately
  after the line `_claude_settings.merge_permission_allowlist(settings_path, _claude_settings.MILL_SUBAGENT_TOOLS)`
  and its following `print(f'Permission allowlist merged: {_claude_settings.MILL_SUBAGENT_TOOLS}')`
  line, add two new lines before the closing `"` of the heredoc:
  ```
  _claude_settings.reconcile_destructive_denylist(settings_path)
  print('Destructive denylist reconciled')
  ```
  In the prose immediately above the fenced block, after the existing sentence "This phase also
  merges the mill subagent's tool surface (`_claude_settings.MILL_SUBAGENT_TOOLS`) into
  `permissions.allow` in the same file, so a background `mill-implementer`/`mill-reviewer` dispatch
  doesn't stall on an interactive tool-permission prompt that nothing can answer (#631).", add a new
  sentence: "It also reconciles `permissions.deny`: `_claude_settings.reconcile_destructive_denylist`
  retires target-blind `rm -rf` deny rules (`RETIRED_DENY`) and replaces them with a scoped set of
  catastrophic-target rules (`DESTRUCTIVE_DENY`) — see `_claude_settings.py`." Extend the "Log the
  result" sentence below the fenced block to also name the denylist-reconciliation outcome, and
  extend the `emit` message string to append, after the existing allowlist sentence:
  " Destructive denylist reconciled in ~/.claude/settings.json -- takes effect immediately, no
  restart needed." Do not change the `MILL_PYTHON`-related lines or any other phase in this file.

  **In `test-claude-settings.py`:** add four new test functions in a new `# reconcile_destructive_denylist`
  section (mirroring the file's existing `# merge_permission_allowlist` section heading style), using
  the same `tempfile.TemporaryDirectory()` / in-memory fixture conventions as the existing tests —
  no real git or LLM:
  - `test_reconcile_retires_target_blind_rm_rf`: seed a settings file whose `permissions.deny`
    contains `"Bash(rm -rf:*)"` plus one unrelated entry (e.g. `"Bash(git push --force:*)"`); call
    `reconcile_destructive_denylist`; assert `"Bash(rm -rf:*)"` is gone from the result's
    `permissions.deny` and the unrelated entry survives.
  - `test_reconcile_adds_destructive_deny_entries`: call `reconcile_destructive_denylist` against an
    absent settings file; assert every entry in `_claude_settings.DESTRUCTIVE_DENY` is present in the
    resulting `permissions.deny`, with no duplicates.
  - `test_reconcile_preserves_unrelated_deny_and_other_keys`: seed a settings file with an unrelated
    `permissions.deny` entry, a `permissions.allow` list, an `additionalDirectories` list, and an
    `env` block (mirroring `test_preserves_existing_permissions_block`'s fixture shape); call
    `reconcile_destructive_denylist`; assert the unrelated `deny` entry, the `allow` list, the
    `additionalDirectories` list, and the `env` block are all byte-identical to their pre-call
    values.
  - `test_reconcile_idempotent_second_call_skips_write`: call `reconcile_destructive_denylist` twice
    in a row against the same path (mirroring `test_idempotent_second_call_skips_write`'s
    mtime/text-comparison shape); assert the second call's result matches the first's, the file's
    mtime is unchanged, and the file's text is unchanged after the second call.

  Add all four new test functions to the `tests` list inside `main()`, after the existing
  `test_idempotent_second_call_skips_write` entry and before
  `test_mill_subagent_tools_matches_agent_frontmatter`.
- **Commit:** `feat(claude-settings): reconcile target-blind rm -rf deny rules in mill-setup Phase 4.8`

## Batch Tests

`verify:` runs the full `test-claude-settings.py` file (all eight tests: four pre-existing plus the
four new ones this card adds) — this is the correct scope since the file already covers the sibling
function `merge_permission_allowlist` this card sits next to, and the file is small and fast; no
`--only` narrowing is needed for a single-file suite.
