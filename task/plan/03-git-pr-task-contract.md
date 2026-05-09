# Batch: git-pr-task-contract

```yaml
task: 36 (A) — Bug-fix batch 3
batch: git-pr-task-contract
number: 3
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Insert a new task-branch detection step into `plugins/mill/skills/git-pr/SKILL.md` so that running `/git-pr` from a worktree containing `task/status.md` halts before any push or PR-creation work, redirecting the user to `/mill-merge`. This is a single one-card batch because the only change is one inserted section in one markdown file; there is no Python surface to test, and the new detection is independent of #206's cleanliness-gate work (no shared files, no shared concepts). `verify: null` because there is no runnable command — the change is pure SKILL.md prose, validated at code review.

## Cards

### Card 10: insert task-branch detection step in git-pr SKILL.md

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/git-pr/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Insert a new section `### 1.5 Detect task branch` immediately after the existing `### 1. Validate branch` section (currently ending around line 32) and before `### 2. Determine base branch` (currently starting around line 34). Section body, exactly:

  ```markdown
  ### 1.5 Detect task branch

  Check whether the current worktree contains `task/status.md`:

  ```bash
  GIT_ROOT=$(git rev-parse --show-toplevel)
  if [ -f "$GIT_ROOT/task/status.md" ]; then
      # halt with the redirect message below
      :
  fi
  ```

  If `task/status.md` exists at the worktree root, halt with the following message and return without running any subsequent step:

  > This is a mill task branch — `task/` files would land in the PR. Use `/mill-merge` to handle the cleanup commit, archive tag, and Home.md flip in one shot. For mid-task collaborator review, push the branch directly with `git push` and open a draft PR via the GitHub UI.

  If the file does not exist, proceed to step 2.
  ```

  Use the literal heading `### 1.5 Detect task branch` (the half-step preserves existing numbering of subsequent sections). Do not renumber any other section. Do not modify any other section of the file. The redirect message must match the wording above verbatim, including the surrounding `>` blockquote markers.

  Match the existing file's prose style: bash code-fences for shell snippets, blockquotes for user-facing messages, "If X / proceed to step N" phrasing for branching (mirroring sections 1, 3, 7 of the same SKILL.md).

- **Commit:** `docs(git-pr): refuse + redirect on task branches`

## Batch Tests

`verify: null` — the change is pure SKILL.md prose. There is no automated test surface for skill instructions; correctness is verified at code review by the reviewer reading the inserted section against this card's requirements and confirming the redirect message wording matches verbatim. Runtime behavior (the actual halt-on-task-branch) is exercised by manual integration testing per discussion.md's Testing section, which is out of scope for the per-batch `verify:` and is the engineer's responsibility post-merge.
