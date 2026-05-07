# Batch: skill-and-config

```yaml
task: '29 (A) — mill-merge-in: delegate konflikter og verify-feil til sub-agent'
batch: skill-and-config
number: 2
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

Updates the two non-code files that govern how the SKILL and existing hubs use the new CLI: `mill-merge-in/SKILL.md` (Steps 3 and 4 delegate to the CLI instead of doing inline resolution) and `plugins/mill/templates/wiki-config.yaml` (documents the new `merge.verify_fix_rounds` config key with its default). This batch can run in parallel with Batch 3 (unit-tests) since they touch disjoint files. No verify command: SKILL.md is documentation and the wiki-config template is a non-executable YAML file; correctness is verified by code review.

Batch-local decision: `wiki/config.yaml` (the deployed wiki config for this hub) is NOT edited in this batch. The new key has a code-level default of `3` in the CLI (`cfg.get("merge", {}).get("verify_fix_rounds", 3)`), so existing hubs work correctly without the key being present in their `wiki/config.yaml`. The template update in `plugins/mill/templates/wiki-config.yaml` documents the key for new hub setups.

## Cards

### Card 4: Add merge.verify_fix_rounds to wiki-config template

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a new `merge:` section to `plugins/mill/templates/wiki-config.yaml` after the `groom:` section (at the end of the file). The section must include a comment header `# ---------------------------------------------------------------------------`, a `# mill-merge-in` label line, `# ---------------------------------------------------------------------------`, a comment explaining that `verify_fix_rounds` controls how many self-fix attempts the verify-fix sub-agent makes before reporting stuck, and then `merge:` followed by `  verify_fix_rounds: 3`. Commit message must document why editing only the template (not `wiki/config.yaml`) is safe: the CLI has a fallback default of 3, so no existing hub is broken. The new key `merge.verify_fix_rounds` does not exist in any current script or skill file (confirmed via grep: zero hits for `verify_fix_rounds` in `plugins/mill/scripts/` and `plugins/mill/skills/` before this card ships), so no currently-running task reads it yet.
- **Commit:** `feat(config): document merge.verify_fix_rounds in wiki-config template`

### Card 5: Update mill-merge-in/SKILL.md Steps 3 and 4

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `plugins/mill/skills/mill-merge-in/SKILL.md` Step 3 and Step 4 as follows.
  **Step 3 — conflict table:** Replace the `Real code conflicts` row body (the cell that currently says "Attempt resolution based on understanding both sides...") with: "Enumerate unresolved files via `git diff --name-only --diff-filter=U`. Call: `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --mode conflicts --files <file1> <file2> ...` On `{"status":"success"}`: run `git merge --continue` to create the merge commit. On `{"status":"stuck"}`: roll back → `git reset --hard "$CHK"` — preserve checkpoint, report to caller." Also replace the line after the table that says "If any real-code conflict is unresolvable → roll back to checkpoint, preserve the checkpoint, report the conflicting files to the caller." with: "On `{"status":"stuck"}` from the sub-agent → roll back to checkpoint (`git reset --hard "$CHK"`), preserve the checkpoint, report to the caller."
  **Step 4 — verify loop:** Replace the per-batch failure handling ("On failure → diagnose and fix. Max 3 attempts per batch. On exhaustion → roll back to checkpoint, preserve the checkpoint, escalate to the caller.") with: "On failure → call: `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --mode verify-fix --cmd "<cmd>" --checkpoint "$CHK"` On `{"status":"success"}`: continue to next batch verify. On `{"status":"stuck"}`: roll back → `git reset --hard "$CHK"` — preserve checkpoint, escalate to the caller." The pre-existing rollback behavior (roll back to checkpoint on stuck) is preserved; this card only changes HOW the resolution/fix is attempted.
- **Commit:** `feat(skill): delegate conflict resolution and verify-fix to sub-agent in mill-merge-in`

## Batch Tests

`verify: null` — SKILL.md is a Markdown documentation file; `wiki-config.yaml` is a YAML template. Neither has a runnable test surface. Correctness is verified through code review of the diff.
