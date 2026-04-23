---
name: git-commit
description: "Commit and push (no rebase)"
argument-hint: "[--onmain] [message]"
---

Commit and push. No rebase.

## Pre-commit steps

Run these before staging. Both are conditional — skip if the condition isn't met.

### 1. Lint (language-specific)

Detect the project language (see `@mill:workflow` Language Detection) and run the lint step from the matching `{lang}-build` skill on changed files. Skip if no source files changed or no language detected.

### 2. Codeguide sync (only if codeguide is initialized)

Run `@codeguide:codeguide-update` whenever codeguide is initialized for this repo — either **inline** (`_codeguide/Overview.md` exists under the repo) or **sibling** (a separate `<container>/<repo>.codeguide/` or `<container>/codeguide/` repo exists). `codeguide-update` resolves the mode itself via `resolve.py` and handles both.

- **Inline mode** → doc files live inside this repo. `codeguide-update`'s helper (`codeguide_commit.py --mode inline`) stages them; this skill commits them alongside source changes as part of step 3.
- **Sibling mode** → doc files live in the sibling repo and are committed there by `codeguide_commit.py --mode sibling` as its own commit. **Do not** try to stage sibling-rooted paths in this commit — the sibling has its own history.

## Rules

- Use @mill:git-workflow skill for full commit rules.
- **If on `main`/`master` and `--onmain` is not in the argument:** refuse to commit. Suggest a branch name based on staged changes or recent context (e.g. `feature/revise-git-workflow`), prompt the user to confirm or provide an alternative name, then stop. Do not create the branch.
- **If on `main`/`master` and `--onmain` is in the argument:** proceed normally.
- Stage files individually: `git add file1 file2` — never `git add .` or `git add -A`.
- Commit with title + bullet-point format (title summarizes the task, bullets explain key decisions).
- Push to remote. Set upstream if needed: `git push --set-upstream origin <branch>`.
- Never force-push. Never use `--no-verify`.
