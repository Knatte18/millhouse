# Batch: pr-fallback-edits

```yaml
task: '22 — par-A — mill-merge: auto-switch to PR path on branch-protection rejection'
batch: pr-fallback-edits
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Three prose/config edits that together implement the branch-protection fallback for mill-merge. Card 1 inserts the fallback block into the SKILL.md's Step 5 direct path. Cards 2 and 3 add an identical commented-out `git:` block to the wiki-config.yaml template (for new wikis) and the live millhouse wiki/config.yaml respectively. No new files are created; no Python code is written. Verify is null because the only changed surface is documentation and commented-out configuration.

## Cards

### Card 1: Add branch-protection fallback to mill-merge Step 5

- **Reads:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Requirements:** In `plugins/mill/skills/mill-merge/SKILL.md`, locate Step 5's **Direct path** block (the subsection under `### 5. PR path or direct squash?` that begins "**Direct path** (everything else):"). Immediately after the `git -C <parent-path> push` command and before the existing **Idempotency check** paragraph, insert the following **On push failure — branch-protection fallback:** block verbatim:

  ---

  **On push failure — branch-protection fallback:**

  Capture the combined stdout+stderr of the `git push` command. If the exit code is non-zero:

  1. Check the captured output for any of these substrings: `Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006`. If none match → fail the step and trigger the Step 1–5 rollback (do not attempt the fallback).

  2. If a match is found — branch-protection rejection — undo the local squash commit on the parent:

     ```bash
     git -C <parent-path> reset --hard origin/<parent_branch>
     ```

  3. Check whether a PR already exists for the child branch (handles re-runs after partial failure):

     ```bash
     gh pr list --head "$CHILD_BRANCH" --state open --json number,url --jq '.[0]'
     ```

     If a PR exists, capture its `url` field and skip to sub-step 5 (push child branch).

  4. If no open PR exists, create one. Use `<parent_branch>` (not `<base-branch>`) as the `--base` target — in the fallback the two values may differ (e.g., parent is `develop`, base is `main`):

     ```bash
     gh pr create \
         --base "<parent_branch>" \
         --head "$CHILD_BRANCH" \
         --title "<task: field from status.md>" \
         --body "Auto-created: direct push was rejected by branch protection.

     <task_description field from status.md>"
     ```

     Capture the PR URL printed by `gh pr create`.

  5. Push the child branch so the PR has the cleanup commit:

     ```bash
     git push origin "$CHILD_BRANCH"
     ```

  6. Append the `pr-pending` phase and commit+push `status.md` on the task branch:

     ```python
     _status.append_phase(status_path, "pr-pending", _timestamp.now_utc_iso())
     ```

     ```bash
     git add status.md && git commit -m "chore: pr-pending after branch-protection fallback" && git push
     ```

  7. Report to the user:

     ```
     Direct push rejected by branch protection — switched to PR path. PR: <url>. Consider setting `git.require-pr-to-base: true` in wiki/config.yaml.
     ```

  8. Skip to Step 11 (Release lock). Do not run Steps 6 (archive tag), 7 (Home.md flip), 8 (worktree/branch removal), or 9 (portal removal). Re-run `/mill-merge` after the PR lands to complete teardown.

  ---

  The **Idempotency check** paragraph that follows the direct-path `git push` block (`if git merge --squash prints "Already up to date" …`) must remain in place, unchanged, immediately after the fallback block. The fallback only fires on non-zero exit; the idempotency check covers the success/no-op paths.
- **Commit:** `feat(mill-merge): add branch-protection fallback in Step 5 direct path`

### Card 2: Add git block to wiki-config.yaml template

- **Reads:**
  - `plugins/mill/templates/wiki-config.yaml`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Requirements:** In `plugins/mill/templates/wiki-config.yaml`, locate the `spawn:` section header comment and the `paths:` section header comment. Insert the following block between the end of the `spawn:` section and the start of the `# ---------------------------------------------------------------------------` comment line that begins the `paths:` section:

  ```yaml
  # ---------------------------------------------------------------------------
  # Git integration
  # ---------------------------------------------------------------------------
  # Uncomment if your remote enforces PRs to the base branch (branch protection).
  # git:
  #   require-pr-to-base: true   # create a PR instead of pushing directly
  #   base-branch: main          # branch to target; defaults to main if absent

  ```

  One blank line should follow the block before the `paths:` section separator. The block must be fully commented out — no active YAML keys.
- **Commit:** `docs(templates): add commented git block to wiki-config.yaml template`

### Card 3: Add git block to live wiki/config.yaml

- **Reads:**
  - `c:/Code/millhouse/wiki/config.yaml`
  - `discussion.md`
- **Modifies:**
  - `c:/Code/millhouse/wiki/config.yaml`
- **Creates:** none
- **Requirements:** Resolve the wiki path at runtime via `_paths.resolve_wiki_path(git_root)` (where `git_root` is the task worktree root). The resolved path should be `c:/Code/millhouse/wiki`. Edit `config.yaml` in the wiki: insert the identical `git:` block described in Card 2 in the same position — between the end of the `spawn:` section and the start of the `paths:` section separator. After editing, commit and push the file via `_wiki.write_commit_push`:

  ```python
  import sys
  sys.path.insert(0, 'plugins/mill/scripts')
  from pathlib import Path
  import _wiki, _paths
  git_root = _paths.resolve_git_root()
  wiki_path = _paths.resolve_wiki_path(git_root)
  _wiki.write_commit_push(wiki_path, ['config.yaml'], 'chore: add commented git block to wiki/config.yaml')
  ```

  Run this as a `python -c "..."` one-liner from the task worktree root. Do not leave the wiki in a dirty (uncommitted) state.
- **Commit:** `chore(wiki): add commented git block to wiki/config.yaml` *(this commit is made by `_wiki.write_commit_push`, not by the task branch's git history)*

## Batch Tests

`verify: null` — all changes are documentation/configuration edits with no runnable test surface. Verify by inspection after each card:

- Card 1: read back Step 5 of `SKILL.md` and confirm: fallback block is present after the `git push` line, detection strings are complete, `--base` uses `<parent_branch>`, PR-existence guard is present, skip target is Step 11, idempotency check is untouched.
- Card 2: read back `plugins/mill/templates/wiki-config.yaml` and confirm the `git:` block appears between `spawn:` and `paths:`, both fields are commented out.
- Card 3: read back `c:/Code/millhouse/wiki/config.yaml` and confirm the same block in the same position; run `git -C c:/Code/millhouse/wiki log -1` to confirm a commit was made.
