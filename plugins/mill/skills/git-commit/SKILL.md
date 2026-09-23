---
name: git-commit
description: "Commit and push (no rebase)"
argument-hint: "[--onmain] [message]"
---

Commit and push.
No rebase.

## Pre-commit steps

Run these before staging.
Both are conditional — skip if the condition isn't met.

### 1. Lint (language-specific)

Detect the project language (see `@mill:workflow` Language Detection) and run the lint/format step from the matching `{lang}-build` skill on **changed files only**, never the whole solution/project.
Skip if no source files changed or no language detected.
This step inherits the delegated `{lang}-build` skill's tool-availability checks: if a required formatter/linter (e.g. `goimports`) is not installed, follow that skill's documented halt-with-actionable-message behavior (e.g. golang-build's Tool Installation section, which reports "install with: ..." and stops) rather than silently skipping the lint/format step.

## Rules

- Use @mill:git-workflow skill for full commit rules.
- **If on `main`/`master` and `--onmain` is not in the argument:** refuse to commit.
  Suggest a branch name based on staged changes or recent context (e.g. `feature/revise-git-workflow`), prompt the user to confirm or provide an alternative name, then stop.
  Do not create the branch.
- **If on `main`/`master` and `--onmain` is in the argument:** proceed normally.
- Stage files individually: `git add file1 file2` — never `git add .` or `git add -A`.
- **Verify the stage before committing.** After staging, run `git diff
  --quiet -- <the same paths just staged>`. A non-zero exit means the
  working tree still has changes beyond what was staged for those paths --
  the add/edit race this step exists to catch (a `git mv`/edit not yet
  reflected in the index at stage time). On a non-zero exit, re-run `git add`
  for those exact paths once and re-check; if the second check is still
  non-zero, halt and report the mismatch instead of committing.
- Commit with title + bullet-point format (title summarizes the task, bullets explain key decisions).
- Push to remote.
  Set upstream if needed: `git push --set-upstream origin <branch>`.
- Never force-push.
  Never use `--no-verify`.
