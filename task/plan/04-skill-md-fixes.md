# Batch: skill-md-fixes

```yaml
task: '28 (A) — review-plan robustness'
batch: skill-md-fixes
number: 4
cards: 3
verify: null
depends-on: [3]
```

## Batch Scope

Apply three text changes to `plugins/mill/skills/mill-plan/SKILL.md`:
1. Bug A: wrap all three autonomous `millpy-review-plan.py` invocations (step 1.5 re-run, step 2, step 4.5) in the `millpy-bg.py` wrapper with the poll-log pattern.
2. Bug D: extend step 4.5's trigger from all-ERROR to any-ERROR.
3. Bug E: update the wiki-config-mutation fix-table row to reference `--skip-check wiki-config-mutation`.

No code changes; `verify: null`. Depends on batch 3 so that `--skip-check wiki-config-mutation` is a real CLI flag when SKILL.md references it.

## Cards

### Card 11: Bug A — wrap all three autonomous CLI invocations in millpy-bg

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `SKILL.md`, replace all three autonomous bare `uv run ... millpy-review-plan.py` invocations with the `millpy-bg` wrapper + poll pattern. The three locations are:

  **Location 1 — Step 1.5** re-run after validator-fix commit:
  Find the sentence `"re-runs \`uv run --project "c:/Code/millhouse/wts/millhouse/plugins/mill" "c:/Code/millhouse/wts/millhouse/plugins/mill/scripts/millpy-review-plan.py"\` (still no round consumed — the validator gate is pre-LLM)."` Replace the inline backtick CLI snippet with the millpy-bg invocation and poll instruction, adapting the sentence to read: "re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed). Poll `cat <log-path>` until `[mill-bg] EXIT`, then extract the JSON line from the log."

  **Location 2 — Step 2** subprocess invocation:
  Replace the ```bash block:
  ```bash
  uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-plan.py"
  ```
  with:
  ```bash
  uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
      --slug plan-review-r<N> -- \
      uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-plan.py"
  ```
  After the block, add: "This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then read the log and extract the JSON summary line (the last non-empty, non-sentinel line)."

  **Location 3 — Step 4.5** retry invocation:
  Replace the ```bash block:
  ```bash
  uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-plan.py"
  ```
  with:
  ```bash
  uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-bg.py" \
      --slug plan-review-retry-r<N> -- \
      uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-review-plan.py"
  ```
  Add the same poll instruction as location 2.

  **Step 6** manual invocation example is NOT an autonomous subprocess call — leave it bare. Do not modify it.
- **Commit:** `fix(mill-plan): wrap autonomous millpy-review-plan.py invocations in millpy-bg (#185)`

### Card 12: Bug D — extend step 4.5 trigger from all-ERROR to any-ERROR

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `SKILL.md` step 4.5, make two wording changes:
  1. Find `"every entry's \`verdict\` is \`"ERROR"\`"` and change to `"at least one entry's \`verdict\` is \`"ERROR"\`"`. The full condition currently reads: `"has a non-empty \`reviews[]\` array AND every entry's \`verdict\` is \`"ERROR"\`"` → change to `"has a non-empty \`reviews[]\` array AND at least one entry's \`verdict\` is \`"ERROR"\`"`.
  2. Find `"On the **second** consecutive ERROR-only round"` and change to `"On the **second** consecutive run that still contains any \`"ERROR"\` entry"`.
  The halt message `BLOCKED: review ERROR-only round {N}` and the `Closes #84` comment are unchanged.
- **Commit:** `fix(mill-plan): extend step 4.5 to trigger on any-ERROR entry (#186)`

### Card 13: Bug E — update wiki-config-mutation fix-table row in SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `SKILL.md`, in the validator fix-table (step 1.5), find the `wiki-config-mutation` row and update two occurrences of `--skip-validate` to `--skip-check wiki-config-mutation`:
  1. `"re-run the CLI with \`--skip-validate\`"` → `"re-run the CLI with \`--skip-check wiki-config-mutation\`"`.
  2. In the co-occurrence sentence `"then re-run with \`--skip-validate\`"` → `"then re-run with \`--skip-check wiki-config-mutation\`"`.

  The `--skip-validate` occurrence in step 1.5's header text `"If \`pipeline.skip_validate: true\` ever appears in config...pass \`--skip-validate\` to the CLI"` is the pipeline-level override and must NOT be changed.
- **Commit:** `fix(mill-plan): update wiki-config-mutation row to use --skip-check (#188)`

## Batch Tests

`verify: null` — SKILL.md changes are text-only with no runnable test surface. Manual verification: read the three modified sections in SKILL.md and confirm (a) every autonomous CLI invocation uses millpy-bg with a poll instruction, (b) step 4.5 trigger says "at least one entry", (c) wiki-config-mutation row says `--skip-check wiki-config-mutation` in both fix descriptions.
