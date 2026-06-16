---
name: mill-finalize
description: Orchestrate end-of-task finalization. Decides PR-vs-direct via config, dispatches to /git-pr (PR mode) or /mill-merge (direct mode). Invoked by mill-go Handoff Step 5 or run manually after mill-go completes.
---

# mill-finalize

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are the end-of-task finalization orchestrator. Your job is to choose the correct merge path and execute it. PR mode creates a pull request for human review before squash-merge; direct mode delegates immediately to /mill-merge. You never create a PR if the config says direct is fine, and you never squash directly if the config requires a PR.

## Entry

1. Resolve `git_root` via `_paths.resolve_git_root()`, `wiki_path` via `_paths.resolve_wiki_path(git_root)`.
2. Load config: `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`.
   `signature: _config.load_config(hub_root: Path, worktree_root: Path) -> dict` — deep-merges `<hub_root>/mill-config.yaml` with `<worktree_root>/.millhouse/config.local.yaml`.
2.5. **Path Setup.** `cfg` was loaded in step 2. Derive:
   - `worktree_root = _paths.resolve_hub_path()` (the hub root; used to anchor `_mill/` paths in nested layouts)
   - `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`
   - `task_dir = status_path.parent`

   Use these variables for all subsequent path references.
3. Resolve task data: `active_data = _marker.task_data(git_root, wiki_path, cfg)`. On `MarkerError` → halt: "This worktree has no registered task branch — mill-finalize needs a tracked branch. Run mill-claim to register it, or merge manually."
4. `slug = active_data['slug']`.
5. `status_path` is set in Path Setup (step 2.5). Call `data = _status.read_status(status_path)`. Verify `data["phase"] == "done"`. If not: halt "status.md phase is `<value>`; mill-finalize expects `done`. Run mill-go first to bring the task to done."
   `signature: _status.read_status(status_path: Path) -> dict` — returns flat dict with keys `phase`, `task`, `current_batch`, `last_timeline_entry`, `blocked_reason`. Access phase via `data["phase"]` (not `data["yaml"]["phase"]` — that is `read_full`'s shape).

## Dispatch

Read these config keys from the deep-merged config (`cfg`):

- `require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))` — default false.
- `base_branch = cfg.get("git", {}).get("base_branch", "main")` — default "main".
- `parent_branch = _parent_branch.resolve(status_path, interactive=False)` — reads `parent:` from status.md. On `ParentBranchError` → halt with the error message.

**PR mode** activates when `require_pr is True`.

- **PR mode:** proceed to PR Steps.
- **Direct mode** (everything else): invoke `/mill-merge`. Execution ends — mill-merge owns its own steps and teardown.

## PR Steps

### Step 1: mill-merge-in

Invoke the `mill-merge-in` skill (no arguments — it reads the parent branch from status.md). If it reports failure → halt; do not proceed.

### Step 2: Update status to pr-pending

```python
_status.append_phase(status_path, "pr-pending", _timestamp.now_utc_iso())
```

```bash
git add <status_path>
git commit -m "mill-finalize: pr-pending for <slug>"
```

### Step 3: Cleanup commit (issue #268)

Clean up the task state directory. On stacked branches (where base branch
tracks `task_dir`), restore it from the base; otherwise remove it. This
prevents PR diffs from being polluted with unrelated deletions on
stacked-branch PRs.

Call `_finalize_cleanup.base_tracks_task_dir(git_root, parent_branch, task_dir)`.
If True (base tracks task_dir):

```bash
git -C <worktree> checkout <parent_branch> -- <task_dir>
git commit -m "chore: pre-merge cleanup"
```

If False (base does not track task_dir):

```bash
git -C <worktree> rm -r <task_dir>
git commit -m "chore: pre-merge cleanup"
```

Idempotency: On the restore path, if checkout fails (rare; base has no
`<task_dir>`), skip the commit. On the rm path, if `<task_dir>` is already
absent (re-run after partial failure), `git rm -r <task_dir>` prints "did
not match any files" — treat as a no-op. If the working tree has nothing to
commit, skip the commit. In both cases `task_dir` is either absent (rm path)
or restored to base's version (restore path).

### Step 4: Push task branch

```bash
CHILD_BRANCH=$(git branch --show-current)
git push origin "$CHILD_BRANCH"
```

### Step 5: Create PR

Invoke `/git-pr <parent_branch>` with environment variable `MILL_FINALIZE_PR_CLEANUP=1`:

```bash
MILL_FINALIZE_PR_CLEANUP=1 /git-pr <parent_branch>
```

The skill generates title and body from commit history. Cleanup has already run
in Step 3 (task_dir is either absent on the rm path or restored-to-base on the
restore path), and `MILL_FINALIZE_PR_CLEANUP=1` tells git-pr's guard to skip
its task-branch halt so PR creation proceeds in both cases. If `/git-pr` fails
→ halt and surface the error; do not roll back status.md or the cleanup commit
(push already happened; operator can create the PR manually via GitHub UI or
`gh pr create`).

### Step 6: Home.md → [pr-pending]

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
from pathlib import Path; import _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
_client.set_phase(wiki_path, '<slug>', 'pr-pending')
"
```

### Step 7: Halt

Report to the user:

> "PR created for `<slug>`. Home.md updated to [pr-pending]. Run `/mill-merge` after the PR merges on GitHub to complete teardown (archive tag, [done] flip, worktree cleanup)."

## Board discipline

- `status_path` writes are committed on the task branch via `git add` + `git commit`. Never written to the wiki.
- Wiki mutations go through `_client` calls (`set_phase`, `upsert_task`, `merge_tasks`); the daemon serializes all writes and pushes automatically. For multi-step atomic operations use `_client.merge_tasks`.
- No `cd` to wiki or parent worktree. All parent-branch git operations use `git -C <parent-path>` if ever needed.
- `${CLAUDE_PLUGIN_ROOT}` for all intra-plugin path references.
