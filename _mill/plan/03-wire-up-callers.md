# Batch: wire-up-callers

```yaml
task: Fix codeguide-update scope resolution on stacked branches and resolve_scope.py branch-name parsing
batch: wire-up-callers
number: 3
cards: 2
verify: null
depends-on: [1, 2]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Wires the two mill skills that call `resolve_scope.py`/`codeguide-update` into the fixes landed in batches 1 and 2: `git-commit`'s Step 2 now resolves the task's declared parent branch (via batch 2's `resolve_for_codeguide`) and passes it as `--parent` (batch 1's new flag) to `codeguide-update`; `mill-merge-in`'s Step 5 stops passing the malformed `git diff "$CHK"..HEAD` literal and passes the single token `"$CHK..HEAD"` instead, which batch 1's broadened dispatch now resolves correctly. Both cards are prose edits to `SKILL.md` files — there is no runnable test surface (`verify: null` at both batch and card level); correctness is established by plan/code review reading the prose against batch 1/2's actual function signatures.

## Cards

### Card 7: git-commit SKILL.md Step 2 — resolve and pass `--parent`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/codeguide/scripts/resolve_scope.py`
- **Edits:**
  - `plugins/mill/skills/git-commit/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In the `### 2. Codeguide sync (only if codeguide is initialized)` section, the existing flow is: run `resolve.py --json`, and if `found == false`, skip this step entirely. Insert the new parent-resolution prose AFTER that `found == false` skip check (i.e. only for the case where codeguide IS initialized and the step proceeds to invoke `@codeguide:codeguide-update`) — do not run mill path resolution for repos where codeguide isn't initialized, since it would be resolved and then discarded. The inserted prose instructs: (a) resolve `git_root` via `_paths.resolve_git_root()` and `hub_root` via `_paths.resolve_hub_path()`, then load config via `cfg = _config.load_config(hub_root, git_root)` (signature: `load_config(hub_root: Path, worktree_root: Path) -> dict` — pass `git_root` as the `worktree_root` argument), then resolve `status_path` via `_paths.resolve_task_path(hub_root, cfg['paths']['status_md'])` (the config-key pattern; do not hardcode a `_mill/status.md` literal); (b) invoke `_parent_branch.resolve_for_codeguide(status_path)` via the standard `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "..."` cache-form invocation, printing the result (or an empty string / marker if `None`) so the calling shell/assistant can read it. Wrap step (a)'s three resolution calls (`resolve_git_root`, `resolve_hub_path`, `resolve_task_path`) so that ANY failure (not just a missing `parent:` row — `resolve_for_codeguide` only swallows `ParentBranchError`; `_paths.resolve_git_root()`/`resolve_hub_path()` can themselves raise/halt outside a mill worktree, e.g. `SystemExit` when cwd isn't in a git repo the function recognizes) is treated as "no parent hint available" and falls through to the no-arg invocation below — explicitly state this guard so a non-mill or non-hub cwd degrades cleanly instead of aborting the commit.
  - Update the existing "Otherwise invoke `@codeguide:codeguide-update`" sentence: when the parent-hint step above returned a non-empty branch name, invoke `@codeguide:codeguide-update` with `--parent <branch>` as its argument; when it returned empty/`None`/errored (no mill worktree, no recorded parent, or any of step (a)'s resolutions failed), invoke `@codeguide:codeguide-update` with no arguments exactly as today. State explicitly that this degrade-to-no-arg path must never error or prompt — `git-commit` is a general-purpose skill used outside mill task worktrees too (e.g. `--onmain` commits directly to the hub).
  - Do not change the Inline mode / Sibling mode bullets below this step, or any of the `## Rules` section — this card only touches the Step 2 codeguide-sync invocation prose.
- **Commit:** `docs(mill): git-commit Step 2 passes --parent to codeguide-update on mill task branches`

### Card 8: mill-merge-in SKILL.md Step 5 — fix malformed scope argument

- **Context:**
  - `plugins/codeguide/scripts/resolve_scope.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `### 5. Codeguide update`, change the bullet "Pass argument `git diff "$CHK"..HEAD`" to "Pass argument `"$CHK..HEAD"`" (the single token `$CHK` followed by the literal suffix `..HEAD`, with no `git diff` prefix). Update the surrounding sentence if needed so it reads correctly as "so the update sees everything the merge introduced, including your conflict resolutions" — the intent is unchanged, only the literal argument string is corrected.
  - Do not change anything else in Step 5 (the `_codeguide/Overview.md` existence check, the Skill-tool invocation form, or the absent-Overview.md skip-silently note) or any other step in the file.
- **Commit:** `fix(mill): mill-merge-in Step 5 passes a valid single-token scope argument to codeguide-update`

## Batch Tests

Both cards are `SKILL.md` prose edits with no runnable code — `verify: null` at the batch level, matching the plan-batch template's guidance to state why when a batch has no test command. Correctness is verified by plan review (checking the new prose is consistent with batch 1's actual `--parent` CLI contract and batch 2's actual `resolve_for_codeguide` signature) and, per the discussion's Testing section, an integration-level check is recommended as a follow-up but is out of scope for this batch's automated verify.
