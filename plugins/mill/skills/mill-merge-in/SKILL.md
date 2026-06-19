---
name: mill-merge-in
description: Sync the parent branch into the current branch. Checkpoint + conflict policy + verify + codeguide-update. Safe to call standalone or as mill-merge's first step.
---

# mill-merge-in

Merge the parent branch into the current branch. Creates a rollback checkpoint first, resolves conflicts conservatively, replays the same batch verifies mill-go ran during implementation, and runs codeguide-update when applicable. This skill does not acquire the merge lock — only the calling `mill-merge` (or the user running it standalone) touches state outside the current branch.

## Entry

1. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".
2. Resolve the parent branch. **Source of truth is `_mill/status.md`'s `parent:` row** — call `_parent_branch.resolve(status_path, interactive=True)` where `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`. Config does not carry a parent-branch override (YAGNI as of v2.0). If `mill-merge-in` is being called from `mill-merge`'s auto-merge path, pass `interactive=False` and propagate the raised `ParentBranchError`.
3. Optional positional argument: `<branch>` from the user's invocation overrides both status.md and the prompt. This is for ad-hoc syncing from some other branch than the task's declared parent.

## Steps

### 1. No-op check

```bash
git log HEAD..<parent-branch> --oneline
```

If output is empty → report "Nothing to merge — already up to date." and exit 0 immediately. No checkpoint, no verify, no codeguide-update. This is the fast-path contract that lets `mill-merge` call this skill cheaply as a first step.

### 2. Create checkpoint

```bash
CHK="mill-checkpoint-$(git rev-parse --abbrev-ref HEAD | tr '/' '-')"
git branch "$CHK"
```

Record the checkpoint branch name. On any failure after this point, roll back via `git reset --hard "$CHK"` and **preserve** the checkpoint branch (do not delete on failure — the user may need to investigate).

### 3. Merge parent into current

```bash
git merge <parent-branch>
```

**On conflicts** — iterate `git diff --name-only --diff-filter=U`:

| File category | Policy |
|---|---|
| Whitespace- / formatting-only differences | Accept current branch version. |
| Package lock files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Cargo.lock`) | Accept current branch version, then regenerate via the project's install command (`npm install`, `yarn`, `pnpm install`, `poetry lock --no-update`, `cargo build`, etc.). Commit the regenerated file. |
| Build artefacts (dist/, build/, *.min.*) | Accept current branch version. |
| Real code conflicts | Enumerate unresolved files via `git diff --name-only --diff-filter=U`. **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`. If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-merge-in-subagent.py` and `<args> = --mode conflicts --files <file1> <file2> ...`. On `{"status":"success"}`: run `git -c core.editor=true merge --continue` to create the merge commit. `-c core.editor=true` scopes the editor suppression to this one command -- no env-var leak into subsequent operations. On `{"status":"stuck"}`: roll back → `git reset --hard "$CHK"` — preserve checkpoint, report to caller. If `subprocess` or `psmux`: use the subprocess/psmux branch — `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --mode conflicts --files <file1> <file2> ...` — same success/stuck handling as agent mode. |

On `{"status":"stuck"}` from the sub-agent → roll back to checkpoint (`git reset --hard "$CHK"`), preserve the checkpoint, report to the caller.

### 4. Verify

Replay exactly the tests that ran during implementation. Call `_plan_dag.iter_batch_verifies(plan_dir)` where `plan_dir = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/plan/")`. That yields `(batch_name, verify_cmd)` pairs in DAG order, skipping batches with `verify: null`.

Before the loop, load config and read the allowlist: call `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`, then read `skip_list = (cfg.get("verify") or {}).get("skip_known_broken") or []`. `skip_list` is the empty list when the key is absent (the default for all existing hubs). Initialise counters `ran = 0` and `skipped = 0`.

For each `(name, cmd)`:
- Plugin-root substitution: compute `local_plugin_root = str(git_root / "plugins" / "mill")`; if `(git_root / "plugins" / "mill").is_dir()`, rewrite `cmd = cmd.replace("${PLUGIN_ROOT}", local_plugin_root)`. If `plugins/mill` does not exist in the current git root (non-millhouse repos), this is a no-op.
- Allowlist pre-check: iterate `skip_list`; on the first entry `p` where `p in cmd` is true, print `[verify] skipped {p} (allowlisted as known-broken)` to stdout (where `{p}` is the literal matched entry), increment `skipped`, and `continue` to the next `(name, cmd)` pair without running the command and without invoking the verify-fix sub-agent. If no entry in `skip_list` matches, fall through to the next bullet.
- Run the command from the worktree root. On success: increment `ran` and continue to the next pair.
- On failure → **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`. If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go/SKILL.md`) with `<cli> = millpy-merge-in-subagent.py` and `<args> = --mode verify-fix --cmd "<cmd>" --checkpoint "$CHK"`. Special handling: when the prepare stage reports `dispatch_needed: false` in its JSON output (verify already passed), skip the Agent tool invocation and finalize call, and use the embedded success envelope directly. On `{"status":"success"}`: increment `ran`, continue to next batch verify. On `{"status":"stuck"}`: roll back → `git reset --hard "$CHK"` — preserve checkpoint, escalate to the caller. If `subprocess` or `psmux`: use the subprocess/psmux branch — `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --mode verify-fix --cmd "<cmd>" --checkpoint "$CHK"` — same success/stuck handling as agent mode.

If `iter_batch_verifies` returns `[]` (no plan, or every batch had null verify) → skip verify entirely. This covers tasks that were entirely docs or config.

### 5. Codeguide update

If `_codeguide/Overview.md` exists anywhere in the repo, invoke the `codeguide-update` skill scoped to the checkpoint diff:

- Use the Skill tool with name `codeguide:codeguide-update` (namespace matches `plugins/codeguide/settings.json`).
- Pass argument `git diff "$CHK"..HEAD` so the update sees everything the merge introduced, including your conflict resolutions.

If `_codeguide/Overview.md` is absent → skip silently. This is the documented convention in `plugins/mill/skills/git-commit/SKILL.md` step 2 and we follow it here for symmetry.

### 5.5. Commit dispatch briefs

If any dispatch briefs exist and have changes (both the `merge/conflicts` brief written in step 3 and the `merge/verify-fix` brief written in step 4 after the `git merge --continue`), stage and commit them. Use a guarded `git status --porcelain` check to avoid an empty commit:

```bash
if [ -d <worktree>/_mill/briefs ] && [ -n "$(git -C <worktree> status --porcelain -- _mill/briefs)" ]; then
  git -C <worktree> add _mill/briefs/ && git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"
fi
```

This step runs on the success path only: any failure in steps 2-5 triggers the Rollback (`git reset --hard "$CHK"`) before reaching this point, so the brief commit is intentionally outside rollback scope and captures successful state. Clean merges (no conflicts, no verify failures) skip steps 3 and 4 entirely, so this step gracefully handles the case where no briefs were written (the `git status --porcelain` guard returns empty).

### 6. Report

```
Merged <parent-branch> into <current-branch>. <N> commits integrated.
Verify: <ran> batch tests ran.
Checkpoint: <CHK> (delete manually once you are confident the merge is stable).
```

Emit `Verify: <ran> batch tests ran.` when `skipped == 0`; emit `Verify: <ran> batch tests ran, <skipped> skipped (allowlisted as known-broken).` when `skipped >= 1`.

Leave the checkpoint branch in place on success. The user decides when to delete it — typically after mill-merge's squash lands on parent without follow-up fixes.

## Rollback

If any step between 2 and 5 fails:

```bash
git reset --hard "$CHK"
```

Do **not** delete the checkpoint. Surface the failure to the caller. If called from `mill-merge`, the caller releases its merge lock and aborts; if standalone, the user investigates.

## No-op guarantee

When step 1 returns empty, this skill touches nothing: no checkpoint, no verify, no codeguide-update, no output side effects. `mill-merge` depends on this — it calls `mill-merge-in` first every time, expecting a cheap exit when there is nothing to sync.
