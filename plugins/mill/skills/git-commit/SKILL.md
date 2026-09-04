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

### 2. Codeguide sync (only if codeguide is initialized)

Run `PYTHONPATH="${CODEGUIDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CODEGUIDE_PLUGIN_ROOT}/scripts/resolve.py" --json` from the repo root.
Parse the JSON object `{mode, cg_root, sibling_anchor, found}`.
If `found == false`, skip this step entirely (codeguide is not initialised for this repo).

Otherwise, before invoking `@codeguide:codeguide-update`, try to resolve a parent-branch hint so stacked task branches scope the update against their actual parent instead of the repo's default branch:

1. Resolve `git_root = _paths.resolve_git_root()` and `hub_root = _paths.resolve_hub_path()`, then load config via `cfg = _config.load_config(hub_root, git_root)` (signature: `load_config(hub_root: Path, worktree_root: Path) -> dict` — pass `git_root` as the `worktree_root` argument), then resolve `status_path = _paths.resolve_task_path(hub_root, cfg['paths']['status_md'])` (the config-key pattern;
   never hardcode a `_mill/status.md` literal).
2. Call `_parent_branch.resolve_for_codeguide(status_path)` and print its result (empty line when it returns `None`), using the standard cache-form invocation:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import _paths, _config, _parent_branch
   try:
       git_root = _paths.resolve_git_root()
       hub_root = _paths.resolve_hub_path()
       cfg = _config.load_config(hub_root, git_root)
       status_path = _paths.resolve_task_path(hub_root, cfg['paths']['status_md'])
       result = _parent_branch.resolve_for_codeguide(status_path)
   except (Exception, SystemExit):
       result = None
   print(result or '')
   "
   ```

   **Guard:** the `try`/`except (Exception, SystemExit)` above must wrap all three resolution calls (`resolve_git_root`, `resolve_hub_path`, `resolve_task_path`), not just the `_parent_branch` call — `resolve_for_codeguide` only swallows `ParentBranchError` (a missing `parent:` row), while `_paths.resolve_git_root()` / `resolve_hub_path()` can themselves raise or halt outside a mill worktree (e.g. `SystemExit` when cwd isn't inside a git repo the helper recognizes).
   Any failure in any of the three must be treated as "no parent hint available" and fall through to the no-arg invocation below — this guard must degrade cleanly rather than abort the commit.

When the parent-hint step above printed a non-empty branch name, invoke `@codeguide:codeguide-update` with `--parent <branch>` as its argument.
When it printed an empty line (no mill worktree, no recorded `parent:` row, or any of step 1's resolutions failed), invoke `@codeguide:codeguide-update` with no arguments exactly as today — this degrade-to-no-arg path must never error or prompt, since `git-commit` is a general-purpose skill used outside mill task worktrees too (e.g. `--onmain` commits directly to the hub).
Either way, the `codeguide-update` skill re-resolves per file and handles inline / sibling itself.

- **Inline mode** → doc files live inside this repo. `codeguide-update`'s helper (`codeguide_commit.py --mode inline`) stages them;
  this skill commits them alongside source changes as part of step 3.
- **Sibling mode** → doc files live in the sibling repo and are committed there by `codeguide_commit.py --mode sibling` as its own commit.
  **Do not** try to stage sibling-rooted paths in this commit — the sibling has its own history.

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
