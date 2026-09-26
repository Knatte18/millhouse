# Batch: skill-text

```yaml
task: 'Post-merge teardown: keep PR notes, remove checkpoint branches'
batch: 'skill-text'
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-guards.py
depends-on: [1]
```

## Batch Scope

Prose edits to four SKILL.md files: `mill-merge-in` deletes its checkpoint on success, `mill-merge` drops its stale checkpoint references, `mill-finalize` stashes the PR notes and passes them to `git-pr`, and `git-pr` accepts and appends them.
Depends on batch 1 for the `stash_pr_notes` helper.

## Cards

### Card 4: mill-merge-in deletes its checkpoint on success

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `mill-merge-in/SKILL.md`, insert a new step between "### 5. Commit dispatch briefs" and "### 6. Report", titled "### 5b. Delete checkpoint" (not 5.5, which the step 5 prose already uses for a historical reference), that runs, on the success path only, a bash block recomputing the name (`CHK="mill-checkpoint-$(git rev-parse --abbrev-ref HEAD | tr '/' '-')"`, since each fenced block is a separate tool call) followed by `git branch -D "$CHK" || echo "[mill-merge-in] note: could not delete $CHK (non-fatal)"`.
  State that a failure to delete never fails the skill and that the checkpoint is kept only on the Rollback path.
  In "### 6. Report": remove the `Checkpoint: <CHK> (delete manually ...)` line from the report template, reword the sentence that says to append the substituted-parent line "after the `Checkpoint:` line" to say "after the `Verify:` line", and replace the closing paragraph "Leave the checkpoint branch in place on success. ..." with one sentence saying the checkpoint is deleted on success (step 5b) and preserved only when the skill halts on a conflict or failed verify.
  Leave the "## Rollback" section and the "Do **not** delete the checkpoint" line unchanged.
  Keep the existing `git add _mill/briefs/` block in step 5 byte-identical.
- **Commit:** `fix(mill-merge-in): delete checkpoint branch after successful merge and verify`

### Card 5: mill-merge drops stale checkpoint references

- **Context:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `mill-merge/SKILL.md` Step 2, remove the two-line instruction "Capture the checkpoint branch name it prints; you may need it on rollback." since merge-in no longer prints a checkpoint name and rollback already targets `origin/<parent_branch>`.
  In the rollback paragraph, drop the line "Preserve the checkpoint branch." (moot once merge-in succeeded).
  Leave the "Why `origin/<parent_branch>`, not the checkpoint" note as is.
  No other behavior change.
- **Commit:** `docs(mill-merge): drop stale checkpoint-name references`

### Card 6: mill-finalize stashes pr-notes before cleanup

- **Context:**
  - `plugins/mill/scripts/_finalize_cleanup.py`
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `mill-finalize/SKILL.md` Step 3, add a paragraph before the "Citation scan" paragraph titled "Stash PR notes (non-blocking)".
  It runs, via `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "..."`, `_finalize_cleanup.stash_pr_notes(<worktree>, <task_dir>, '<slug>')` and binds `pr_notes_path = <worktree>/.scratch/pr-notes-<slug>.md` when it returns True (else `None`); a failure of this call only prints a warning and never halts Step 3.
  Explain that the scratch file survives the `git rm -r` and restore-from-base branches because `.scratch/` is gitignored.
  In Step 5, change the invocation to `/git-pr <parent_branch> --skip-task-branch-guard` plus ` --pr-notes <pr_notes_path>` only when `pr_notes_path` is bound, and note that git-pr appends the notes to the PR body and removes the scratch file after the PR is created.
- **Commit:** `fix(mill-finalize): carry pr-notes into the PR body`

### Card 7: git-pr accepts --pr-notes

- **Context:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/git-pr/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `git-pr/SKILL.md` Usage block add `/git-pr develop --pr-notes <path>` with a one-line description (optional reviewer notes file, appended to the PR body).
  In Step 2 item 1 (Argument), extend the strip rule: strip `--skip-task-branch-guard` and also `--pr-notes` together with its following value from `$ARGUMENTS` before taking the first remaining non-flag token as the base branch, so the path is never read as the base branch.
  In Step 9 "Generate body", add: when `--pr-notes <path>` was given and the file exists, append its contents verbatim to the generated body under a `## Reviewer notes` heading.
  After Step 10 or Step 10.5 succeeds (PR created or REST-created), delete the notes file; on failure leave it in place for a retry.
  Without the flag, behavior is unchanged.
- **Commit:** `feat(git-pr): append --pr-notes file to the PR body`

## Batch Tests

`verify:` runs `test-brief-commit.py` (locks the `git add _mill/briefs/` pattern in `mill-merge-in/SKILL.md`) and `test-guards.py` (references skill text including `mill-finalize/SKILL.md`), the two existing tests that lock text in the edited skills; the edits themselves are prose and otherwise verified by review.
