# Batch: mill-go, config template, and SKILLS index

```yaml
task: '40 (B) — mill-finalize: lift PR decision out of mill-merge'
batch: mill-go, config template, and SKILLS index
number: 3
cards: 3
verify: null
depends-on: [1, 2]
```

## Batch Scope

Three independent edits that all depend on batches 1 and 2 being complete: (a) update mill-go's Handoff Step 5 to call `/mill-finalize` instead of `/mill-merge`, (b) rename the two config keys in the `wiki-config.yaml` template, (c) regenerate `SKILLS.md` from the updated SKILL.md frontmatter. The SKILLS.md regen must run after batches 1 and 2 so the new mill-finalize entry and updated mill-merge description are both captured.

Cards 4 and 5 can be committed separately; card 6's commit should follow after the regen.

## Cards

### Card 4: Mill-go Handoff Step 5 update

- **Context:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Edit `plugins/mill/skills/mill-go/SKILL.md`. Two changes, both in the Handoff section:

  **Change A — Handoff Step 5.**

  Find the current Step 5 text (exact match):
  ```
  5. If `pipeline.auto_merge: true` → invoke `/mill-merge`. Otherwise tell the user: "Task complete. Run `/mill-merge` to merge the task branch back to parent." mill-merge may halt on `pr-pending` in PR mode (`git.require-pr-to-base: true`) — that is a skill-level halt and is expected; treat it as completion of step 5 and continue to step 6.
  ```

  Replace with:
  ```
  5. If `pipeline.auto_merge: true` → invoke `/mill-finalize`. Otherwise tell the user: "Task complete. Run `/mill-finalize` to finalize the task (creates a PR or squashes directly, depending on config)." mill-finalize may halt on `pr-pending` in PR mode — that is expected; treat it as completion of step 5 and continue to step 6.
  ```

  **Change B — Handoff Step 6** (remove the mill-merge-specific "mill-merge itself does not self-report" clause).

  Find in the current Step 6 text (the sentence to remove):
  ```
  mill-merge itself does not self-report — only the orchestrator (mill-go) does.
  ```

  Delete that sentence from Step 6. The sentence is true of mill-finalize too, but it belongs in a mill-go principle statement, not as an implementation detail in the step text. (The rest of Step 6 is unchanged.)

  Also find and remove or update the Handoff config-key reference in Step 19 (the config keys read at the top of the Handoff section):
  ```
  - `pipeline.auto_merge` — whether to invoke mill-merge after success.
  ```
  Replace with:
  ```
  - `pipeline.auto_merge` — whether to invoke mill-finalize after success.
  ```

- **Commit:** `refactor(mill-go): handoff delegates to mill-finalize instead of mill-merge`

### Card 5: wiki-config.yaml template config key rename

- **Context:**
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Edit `plugins/mill/templates/wiki-config.yaml`. Find the commented-out Git integration example block:
  ```
  # git:
  #   require-pr-to-base: true   # create a PR instead of pushing directly
  #   base-branch: main          # branch to target; defaults to main if absent
  ```

  Replace with:
  ```
  # git:
  #   require_pr_to_base: true   # create a PR instead of pushing directly; dispatch lives in mill-finalize
  #   base_branch: main          # branch to target; defaults to main if absent
  ```

  No other changes to this file.

- **Commit:** `refactor(config): rename git config keys to snake_case in wiki-config template`

### Card 6: Regenerate SKILLS.md

- **Context:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `SKILLS.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Run the skills-index script to regenerate `SKILLS.md` from all SKILL.md frontmatter:

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-skills-index.py"
  ```

  If `CLAUDE_PLUGIN_ROOT` is empty (observed on Windows in some shells), fall back to the source-tree path since this is running inside the millhouse repo:

  ```bash
  PYTHONPATH="plugins/mill/scripts" uv run --project "plugins/mill" "plugins/mill/scripts/millpy-skills-index.py"
  ```

  Verify the stdout summary mentions mill-finalize as a newly written entry and mill-merge with an updated description. The script output includes the list of written file paths.

  After regeneration, confirm `SKILLS.md` contains:
  - A new row for `mill-finalize` linking to `plugins/mill/skills/mill-finalize/SKILL.md` with the description from that file's frontmatter.
  - An updated row for `mill-merge` with the new description from its frontmatter (no longer mentions "PR-path honoured via git.require-pr-to-base").

- **Commit:** `chore: regenerate SKILLS.md (add mill-finalize, update mill-merge description)`

## Batch Tests

No runnable test surface — SKILL.md edits and a doc regeneration. SKILLS.md correctness is self-verifying (the regen script either writes the expected rows or it does not).
