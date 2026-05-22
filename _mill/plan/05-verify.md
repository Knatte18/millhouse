# Batch: verify

```yaml
task: Set MILL_PYTHON via mill-setup, use in all skill invocations
batch: verify
number: 5
cards: 1
verify: null
depends-on: [1, 2, 3, 4]
```

## Batch Scope

Runs a grep verification over `plugins/mill/skills/` to confirm the full venv path `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` appears ONLY in `mill-setup/SKILL.md`. Also confirms the two CLAUDE.md files no longer contain the path as the primary reference (the user CLAUDE.md exception note intentionally retains it but as a secondary reference under the bootstrapper exception). This batch has no Edits or Creates — it is a pure verification step that runs after all implementation batches complete.

## Cards

### Card 11: Run grep verification over plugins/mill/skills/

- **Context:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Run the following grep from the worktree root:

  ```bash
  grep -r '\.venv/Scripts/python\.exe' plugins/mill/skills/ --include="SKILL.md" -l
  ```

  **Expected output:** exactly one line: `plugins/mill/skills/mill-setup/SKILL.md`. If any other file appears, the replacement in that file was incomplete. For each unexpected hit, re-run the `replace_all` Edit for that file and re-run the grep.

  Also run the count check for mill-setup to confirm Batch 1 added occurrences but nothing was unexpectedly removed:

  ```bash
  grep -c '\.venv/Scripts/python\.exe' plugins/mill/skills/mill-setup/SKILL.md
  ```

  **Expected output:** `20`. Batch 1 adds 2 new occurrences to mill-setup: one in the Phase 4.8 Bash command block (Card 1) and one in the Phase 8 verification bullet (Card 2). The pre-task baseline was 18; 18 + 2 = 20. If the count is less than 20, a Batch 1 edit was not applied. If more than 20, an unintended addition slipped in.

  Finally, confirm the CLAUDE.md canonical form was updated:

  ```bash
  grep 'MILL_PYTHON' CLAUDE.md
  ```

  **Expected output:** at least one line containing `$MILL_PYTHON` in the `## Script invocation` section.

- **Commit:** `chore(verify): confirm MILL_PYTHON replacement complete`

## Batch Tests

This batch IS the test. `verify: null` in frontmatter because the verification is the card itself, not an external test suite command. On success, all implementation batches have been validated and the task is ready for finalization.
