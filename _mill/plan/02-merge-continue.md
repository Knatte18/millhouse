# Batch: merge-continue

```yaml
task: "mill-merge / fixer teardown recovery"
batch: merge-continue
number: 2
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Documents the non-interactive form of `git merge --continue` in `mill-merge-in/SKILL.md` Step 3 (#357). Today's documented command opens the editor on default-config git and hangs forever in non-interactive shells. This batch is a single-line SKILL.md edit changing the documented command to `git -c core.editor=true merge --continue`. No Python surface; no test surface; `verify: null`.

External interface: none.

## Cards

### Card 4: Update `mill-merge-in/SKILL.md` Step 3 with non-interactive merge --continue

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `skills/mill-merge-in/SKILL.md`, edit the "Real code conflicts" row of the conflict-resolution table inside `### 3. Merge parent into current`. The current text contains the phrase: ``On `{"status":"success"}`: run `git merge --continue` to create the merge commit.`` Replace the literal command `git merge --continue` with `git -c core.editor=true merge --continue`. The replacement is a single literal-string change inside the existing row; do not restructure the table, do not change the success/stuck branching, do not modify any other table row, and do not modify the `git merge <parent-branch>` line under "Merge parent into current" itself (the no-conflict path is already non-interactive on success). Also append a one-sentence note immediately after the replaced phrase: "`-c core.editor=true` scopes the editor suppression to this one command — no env-var leak into subsequent operations." Do NOT add a separate section explaining this; the in-row note is sufficient.
- **Commit:** `docs(mill-merge-in): make Step 3 git merge --continue non-interactive`

## Batch Tests

No runnable surface (`verify: null`). The SKILL.md edit is interpreted by the Builder thread at mill-merge-in runtime; correctness is verified by integration in the next mill-merge-in invocation that hits a real conflict. There is no automated test for this batch.
