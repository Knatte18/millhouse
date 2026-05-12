# Batch: mill-merge refactor

```yaml
task: '40 (B) — mill-finalize: lift PR decision out of mill-merge'
batch: mill-merge refactor
number: 2
cards: 2
verify: null
depends-on: [1]
```

## Batch Scope

Refactor `plugins/mill/skills/mill-merge/SKILL.md` to strip PR-creation logic (moved to mill-finalize) and update the phase gate to handle the post-cleanup case (where task/status.md is absent). Also rename the two config keys in mill-merge's Entry section to the new snake_case names. The file is a single SKILL.md; both cards operate on it, sequentially. Depends on batch 1 so the implementer can read mill-finalize/SKILL.md to confirm the division of responsibility is consistent.

## Cards

### Card 2: mill-merge frontmatter description + config key rename

- **Context:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Edit `plugins/mill/skills/mill-merge/SKILL.md`. Three mechanical changes:

  1. **Frontmatter `description:` field (line 3 of file).**
     Current value:
     ```
     description: Finalize a completed task. Cleanup commit on task branch, squash-merge to parent, archive tag, Home.md flip. Worktree, branch, portal, and legacy wiki cleanup are handled by /mill-cleanup. PR-path honoured via git.require-pr-to-base. Runs from the child worktree.
     ```
     Replace with:
     ```
     description: Squash-merge a completed task branch to its parent, create archive tag, flip Home.md [done]. Direct merge only — PR dispatch lives in mill-finalize. Worktree, branch, portal, and legacy wiki cleanup handled by /mill-cleanup. Runs from the child worktree.
     ```

  2. **Entry Step 1 "Config keys to read" sub-list.**
     Current text (two bullets):
     ```
     - `git.require-pr-to-base` (bool, default false) — when true AND parent-branch equals base-branch, the skill creates a PR instead of merging directly.
     - `git.base-branch` (string) — the repo's canonical base (usually `main`). Falls back to `main` if absent.
     ```
     Replace with:
     ```
     - `git.require_pr_to_base` (bool, default false) — read for the branch-protection fallback message only; PR dispatch itself is handled by mill-finalize.
     - `git.base_branch` (string) — the repo's canonical base (usually `main`). Falls back to `main` if absent. Used in the branch-protection fallback to set the PR `--base` target correctly.
     ```

  3. **Step 5 condition comment and the direct-path branch-protection fallback message.**
     In the "PR path or direct squash?" section, Step 5, find the branch-protection fallback message (sub-step 8):
     ```
     Direct push rejected by branch protection — switched to PR path. PR: <url>. Consider setting `git.require-pr-to-base: true` in wiki/config.yaml.
     ```
     Replace with:
     ```
     Direct push rejected by branch protection — switched to PR path. PR: <url>. Consider setting `git.require_pr_to_base: true` in wiki/config.yaml.
     ```

- **Commit:** `refactor(mill-merge): rename config keys to snake_case, update description`

### Card 3: mill-merge Phase Gate update + Step 5 PR-path removal

- **Context:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  Edit `plugins/mill/skills/mill-merge/SKILL.md`. Two substantial changes:

  **Change A — Phase Gate (Entry Step 6).**

  Current Entry Step 6 text:
  ```
  6. **Phase gate — also the re-entry point for PR-path recovery.** Read `git_root/task/status.md`'s `phase:`.

     | phase | action |
     | --- | --- |
     | `done` | fresh merge — continue to Step 1 |
     | `pr-pending` | see *PR-path re-entry* below |
     | `complete` / missing / other | halt with "status.md phase is <value>; mill-merge expects `done`. If the task is not finished, run mill-go first." |
  ```

  Replace with:
  ```
  6. **Phase gate — also the re-entry point for PR-path recovery.**

     **Try `task/status.md` first.** If `status_path.exists()`, read `phase:` from it and apply the table below. If `task/status.md` is absent (the PR-path cleanup commit already removed `task/`), read `Home.md` instead: call `_wiki.sync_pull(wiki_path, slug=slug)`, read `(wiki_path / "Home.md").read_text(encoding="utf-8")`, parse with `tasks = _tasks_md.parse(home_text)`, find `task = next((t for t in tasks if t.slug == slug), None)`. If `task.phase == "pr-pending"` → treat as `pr-pending` below. Otherwise → halt with "task/status.md absent and Home.md does not show pr-pending for `<slug>`; cannot determine merge state."

     | phase | action |
     | --- | --- |
     | `done` | fresh merge — continue to Step 1 |
     | `pr-pending` | see *PR-path re-entry* below |
     | `complete` / missing / other | halt with "status.md phase is `<value>`; mill-merge expects `done`. If the task is not finished, run mill-go first." |
  ```

  **Change B — Step 5 PR-path removal.**

  The current Step 5 heading is `### 5. PR path or direct squash?` and contains two branches: a PR path block and a direct path block. Remove the PR-path branch entirely and rename the step.

  Current Step 5 opening:
  ```
  ### 5. PR path or direct squash?

  Both PR-creation paths flip Home.md to `[pr-pending]` before halting at Step 8 so the coordination state is visible.

  - **PR path** — activate when `git.require-pr-to-base: true` AND `parent-branch == base-branch`:

    ```bash
    gh pr create --base "<base-branch>" --head "$CHILD_BRANCH" \
        --title "<task: field from status.md>" \
        --body "<one-line summary from status.md>"
    ```

    ```python
    with _wiki.wiki_lock(<WIKI_PATH>, slug):
        home_text = (wiki_path / "Home.md").read_text(encoding="utf-8")
        new_text = _tasks_md.set_phase(home_text, slug, "pr-pending")
        (wiki_path / "Home.md").write_text(new_text, encoding="utf-8")
        _wiki.write_commit_push(<WIKI_PATH>, ["Home.md"], f"task: pr-pending {slug}", slug=slug)
    ```

    Update `task/status.md` via `_status.append_phase(status_path, "pr-pending", _timestamp.now_utc_iso())` and push the task branch so the PR has the cleanup commit. Skip to Step 8 (Release lock) — no further cleanup. Re-run `/mill-merge` after the PR lands to continue from the PR-path re-entry.

  - **Direct path** (everything else):
  ```

  Replace the entire PR-path block and the step heading with:
  ```
  ### 5. Direct squash

  PR dispatch lives in mill-finalize. This step is direct path only.

  - **Direct path:**
  ```

  (Keep everything that currently follows `- **Direct path** (everything else):` through the end of Step 5's direct path content, including the branch-protection fallback sub-steps and the idempotency check. Remove only the PR-path block and the introductory "Both PR-creation paths..." sentence.)

- **Commit:** `refactor(mill-merge): remove PR-creation path, update phase gate for absent status.md`

## Batch Tests

No runnable test surface — SKILL.md edits only. Correctness verified by the plan reviewer reading the edited file against discussion.md decisions.
