---
name: mill-merge
description: Squash-merge a completed task branch to its parent, create archive tag, flip Home.md [done]. Direct merge only — PR dispatch lives in mill-finalize. Worktree, branch, portal, and legacy wiki cleanup handled by /mill-cleanup. Runs from the child worktree.
---

# mill-merge

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are an integration engineer. Your job is to merge a completed task branch back to its parent safely. You never force-merge, never pass a defect downstream, and never lose work. Always run from the child worktree — never from the parent.

**Cross-worktree invariants (same as v1, load-bearing):**

- mill-merge runs from the child worktree.
- `cd <parent-worktree>` is forbidden — it corrupts the shell cwd for the rest of the session.
- All parent-branch git operations go through `git -C <parent-path>`.

## Entry

1. **Step 1 — Resolve mode + load config.**
   Resolve `git_root` via `_paths.resolve_git_root()`, `wiki_path` via `_paths.resolve_wiki_path(git_root)`, and `container_path` via `_paths.resolve_container_path(git_root)`. Load the deep-merged config: `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`. Try to call `active_data = _marker.task_data(git_root, wiki_path, cfg)`. On `_marker.MarkerError` (detached HEAD, prefix mismatch, slug absent from Home.md), halt immediately with: *"This worktree has no registered task branch — `mill-merge` needs `status.md` to know the parent branch. Run `mill-claim` to convert this worktree to a tracked task, or merge manually."* On success: extract `slug = active_data['slug']` and call `mode_inplace = _inplace.is_inplace(slug, git_root, cfg)`. Set `mode = 'inplace'` if `mode_inplace` else `mode = 'worktree'`.

   Stale-worktree edge: if `active_data` is not None AND the corresponding `<worktrees-dir>/<slug>/` directory exists AND the branch matches, call `_inplace.prompt_stale_worktree(slug, worktree_path)` and override `mode` based on the user's choice (`"inplace"` → `mode = 'inplace'`; `"worktree"` → `mode = 'worktree'`; `"abort"` → halt).

   If `mode == 'worktree'` AND `git worktree list --porcelain` shows the cwd is the main worktree:

   - When `active_data` is not None → halt with: "mill-merge from the main worktree requires in-place mode (no separate worktree exists for the active slug). The active marker says `<slug>` is on branch `<branch>`; mill-merge cannot proceed."

   Config keys to read:
   - `git.require_pr_to_base` (bool, default false) — read for the branch-protection fallback message only; PR dispatch itself is handled by mill-finalize.
   - `git.base_branch` (string) — the repo's canonical base (usually `main`). Falls back to `main` if absent. Used in the branch-protection fallback to set the PR `--base` target correctly.

   **In-place mode bypass:** when `mode == 'inplace'`, the existing Steps 1 (acquire merge lock on parent) and 2 (invoke `mill-merge-in`) are SKIPPED. There is no separate parent worktree to lock; the merge is purely local. Continue from Step 3 (capture child branch) onward, but treat "child" and "parent" as branches in the same working tree (cwd is the hub). For the squash merge in Step 4 (Direct path), omit the `-C <parent-path>` flag — the merge runs against the current working tree directly.

1.5. **Path Setup.** `cfg` was loaded in step 1; `container_path` and `slug` are in scope from Step 1. Derive:
   ```python
   worktree_root = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)
   status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
   task_dir = status_path.parent
   ```
   No in-place vs worktree mode branch is needed: `resolve_active_worktree` checks in-place mode first (returns `git_root` when `_inplace.is_inplace` is true) and `resolve_active_hub` covers both modes, so the single call is correct whether `mode == 'inplace'` or `'worktree'`. Use these variables for all subsequent path references.

2. Slug already resolved in Step 1; reuse `active_data['slug']` — no second read needed.
3. *(Config already loaded in Step 1.)*
4. Resolve parent branch via `_parent_branch.resolve(status_path, interactive=<True unless called non-interactively>)`. `status_path` is resolved via `_paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (set in Path Setup step 1.5) and `task_dir = status_path.parent` — state lives in `task_dir` on the task branch, not in the wiki.
5. **Phase gate — also the re-entry point for PR-path recovery.**

   **Try `_mill/status.md` first.** If `status_path.exists()`, read `phase:` from it and apply the table below. If `status_path` is absent: call `task = _client.get_task(wiki_path, slug)` (where `from wiki import _client`). Guard: `if task is None: halt("_mill/status.md absent and slug '<slug>' not found in wiki; cannot determine merge state.")`. If `task["status"] == "pr-pending"` → treat as `pr-pending` below. Otherwise → halt with "_mill/status.md absent and wiki does not show pr-pending for '<slug>'; cannot determine merge state."

   | phase | action |
   | --- | --- |
   | `done` | see *PR-state gate* below |
   | `pr-pending` | see *PR-state gate* below |
   | `complete` / missing / other | halt with "status.md phase is `<value>`; mill-merge expects `done`. If the task is not finished, run mill-go first." |

   When `phase: done`, cache the task fields from `_mill/status.md` now, while status.md still exists and before the Teardown Steps run:
   - `cached_task = _status.read_full(status_path)["yaml"].get("task", slug)` — the task title used in Step 5's squash commit message and Step 6's PR title.
   - `cached_task_description = _status.read_full(status_path)["yaml"].get("task_description", cached_task)` — the task description used in Step 6's PR body.

   Use `cached_task` and `cached_task_description` in all subsequent references to "task: field from status.md" and "task_description field from status.md". Step 4's `git rm -r _mill/` deletes status.md before Step 5 runs; reading from a cached variable avoids the read-after-delete failure.

### PR-state gate

This gate runs for both `done` and `pr-pending` phases, immediately after Step 5's phase check. It must execute before any squash or teardown work begins.

**Capture child branch** (note: this is captured here, earlier than the existing Step 3 capture, because the gate needs it before any parent-side operations; Step 3's capture remains for the squash flow):

```bash
CHILD_BRANCH=$(git branch --show-current)
```

**Resolve PR state** (cwd = child git root, never wiki):

```bash
PR_STATE_JSON=$(PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json
import _pr_state, _paths
r = _pr_state.resolve_pr_state('$CHILD_BRANCH', _paths.resolve_git_root())
print(json.dumps(r))
")
```

Parse the JSON `state` and `number` fields from `PR_STATE_JSON`.

**Route on `state`** (helper returns lowercase values):

- **`merged`** -- cleanup-only teardown: run Step 4 (cleanup commit, so the archive tag reflects a clean tip), then Step 5.5 (cache-helper preflight -- guards Step 6's `_archive_tag` import against a stale plugin cache `ModuleNotFoundError`), then Step 6 (archive tag), Step 7 (Home.md `[done]`), Step 8 (release lock -- no-op if never acquired), Step 9 (notify/report). Skip Steps 1, 2, and 5.

  Note: the local parent branch is intentionally NOT fast-forwarded here; it resyncs on the next parent-side fetch/pull. Do not add a parent ff-sync step (discussion Decisions/merged-remote-cleanup-only, Local-parent staleness).

- **`open`** -- halt and report, never auto-close:

  > "PR #<number> is still open -- close or merge it on GitHub, then re-run `/mill-merge`."

- **`closed`** -- proceed with the normal local squash exactly as the `done` fresh-merge flow (continue to Step 1).

  **Commit-message source:** the `closed` route can be reached from a `pr-pending` re-entry where `_mill/status.md` is typically absent (mill-finalize already `git rm -r`'d `task_dir`), so `cached_task` and `cached_task_description` may be undefined. Establish them before continuing to Step 1:

  - If `status_path.exists()`: read them exactly as the `done` branch caching block does (`_status.read_full(status_path)["yaml"].get("task", slug)` / `.get("task_description", cached_task)`).
  - Otherwise: `task = _client.get_task(wiki_path, slug)` -> `cached_task = task["title"]`, `cached_task_description = task.get("title")` (title is the available field; there is no separate description field in the wiki task). This fallback feeds Step 5's squash commit message.

  **Caution -- branch-protection interaction:** in a branch-protected repo the Step 5 push may be rejected, triggering the existing Step 5 branch-protection fallback that auto-creates a NEW PR -- which contradicts the operator's deliberate close-without-merge. The fallback itself stays as-is, but be aware that `closed` -> local-squash is not guaranteed terminal (discussion Decisions/closed-no-merge-proceeds, Branch-protection interaction).

- **`none`** -- silent fallback to phase-based behavior (no new output):
  - If `phase: done`: continue to Step 1 (today's direct squash).
  - If `phase: pr-pending`: keep today's halt -- "status.md says pr-pending but no PR on this branch; inspect manually."

## Steps

### 1. Acquire merge lock on parent

Resolve the parent worktree path from `git worktree list --porcelain` (the entry whose branch matches the parent branch). Write `<parent-path>/.scratch/merge.lock` with three lines: `pid`, `timestamp` (ISO-8601 UTC Z), `branch` (the child branch about to merge).

If the lock already exists:
- Re-read it. If timestamp is older than 5 min → stale → overwrite.
- Otherwise wait up to 5 min polling every 10 s for the lock to clear. After 5 min → halt with the holder info so the user can intervene.

### 2. Invoke mill-merge-in

Call the `mill-merge-in` skill (no arguments — it picks up the parent from status.md the same way). If it reports failure → release the merge lock and halt. Capture the checkpoint branch name it prints; you may need it on rollback.

### 3. Capture child branch

```bash
CHILD_BRANCH=$(git branch --show-current)
```

Do this before switching to `git -C <parent-path>` calls — once you are operating on the parent, `git branch --show-current` there will report the parent's branch, not yours.

## Teardown sequence

Steps 4–7 implement the canonical merge sequence; worktree, portal, and wiki active-dir teardown is handled by `/mill-cleanup`. Each step is independent; a failed step is reported with its name so the user can re-run from that step (Step 4's squash idempotency handles the common re-entry case).

> **Recovery note:** After teardown completes, the cleanup commit is permanently visible via `git log archive/<slug>`. Operators can inspect (or restore) the task-branch state at any point via `git checkout archive/<slug>`.

### 4. Cleanup commit

On the task branch (current cwd), remove the state directory that belongs to the task lifecycle, not to production code:

```bash
git -C <worktree> rm -r <task_dir>
git commit -m "chore: pre-merge cleanup"
```

**Why:** squashing a branch that already has cleanup as its tip means the squash commit on the parent never includes transient task metadata. The cleanup commit is itself preserved under the archive tag created in Step 6.

**Idempotency:** if `<task_dir>` is already absent (re-run after partial failure), `git rm -r` will warn "did not match any files" — treat as a no-op. If the resulting working tree has nothing to commit, skip the commit.

### 5. Direct squash

PR dispatch lives in mill-finalize. This step is direct path only.

- **Direct path:**

  ```bash
  git -C <parent-path> merge --squash "$CHILD_BRANCH"
  git -C <parent-path> reset -q HEAD -- <task_dir>
  git -C <parent-path> checkout -- <task_dir>
  git -C <parent-path> commit -m "<cached_task>"
  git -C <parent-path> push
  ```

  Note: `<task_dir>` may be passed as either an absolute path (when `_paths.resolve_task_path` derives it from `worktree_root`) or a repo-relative path. `git reset` and `git checkout` accept both forms within the repo root.

  **Why:** The child cleanup commit deletes `task_dir`, so a parent that independently tracks `task_dir/_mill/status.md` at the same relative path would otherwise have its file deleted by the squash diff (the #497 bug-2 corruption). The restore step unstages and restores the parent's own `task_dir` from its pre-squash HEAD, ensuring the squash only stages the intended production files. This is a clean no-op when the parent tracks nothing at `task_dir`.

  After the restore, re-inspect the staged changes via `git -C <parent-path> diff --cached --stat` and proceed to commit only the intended production files.

  **On push failure — branch-protection fallback:**

  Capture the combined stdout+stderr of the `git push` command. If the exit code is non-zero:

  1. Check the captured output for any of these substrings: `Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006`. If none match → fail the step and trigger the Step 1–5 rollback (do not attempt the fallback).

  2. If a match is found — branch-protection rejection — undo the local squash commit on the parent:

     ```bash
     git -C <parent-path> reset --hard origin/<parent_branch>
     ```

  3. Check whether a PR already exists for the child branch (handles re-runs after partial failure):

     ```bash
     gh pr list --head "$CHILD_BRANCH" --state open --json number,url --jq '.[0]'
     ```

     If a PR exists, capture its `url` field and skip to sub-step 5 (push child branch).

  4. If no open PR exists, create one. Use `<parent_branch>` (not `<base-branch>`) as the `--base` target — in the fallback the two values may differ (e.g., parent is `develop`, base is `main`):

     ```bash
     gh pr create \
         --base "<parent_branch>" \
         --head "$CHILD_BRANCH" \
         --title "<cached_task>" \
         --body "Auto-created: direct push was rejected by branch protection.

     <cached_task_description>"
     ```

     Capture the PR URL printed by `gh pr create`.

  5. Push the child branch so the PR has the cleanup commit:

     ```bash
     git push origin "$CHILD_BRANCH"
     ```

  6. Append the `pr-pending` phase and commit+push `<status_path>` on the task branch:

     ```python
     _status.append_phase(status_path, "pr-pending", _timestamp.now_utc_iso())
     ```

     ```bash
     git add <status_path> && git commit -m "chore: pr-pending after branch-protection fallback" && git push
     ```

  7. Flip Home.md to `[pr-pending]`:

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     from pathlib import Path; import _paths
     from wiki import _client
     wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
     _client.set_phase(wiki_path, '<slug>', 'pr-pending')
     "
     ```

  8. Report to the user:

     ```
     Direct push rejected by branch protection — switched to PR path. PR: <url>. Consider setting `git.require_pr_to_base: true` in mill-config.yaml.
     ```

  9. Skip to Step 8 (Release lock). Do not run Steps 6 (archive tag) or 7 (Home.md flip). Re-run `/mill-merge` after the PR lands to complete teardown.

  **Idempotency check:** if `git merge --squash` prints "Already up to date" or `git commit` prints "nothing to commit" → skip `push` and proceed to Step 6.

### 5.5. Preflight check for cache helpers

Before attempting Step 6's archive-tag import, verify that the plugin cache is complete. Run:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
from pathlib import Path
import _preflight
exit(_preflight.check_helpers(['_archive_tag']))
"
```

If the check returns non-zero (helper missing), the error message to stderr names the missing module(s) and instructs the operator to refresh the plugin cache. The operator must reinstall/update the cache and re-run `/mill-merge`.

**Rationale:** a stale plugin cache (missing `_archive_tag.py`) would otherwise crash at Step 6 with a cryptic `ModuleNotFoundError`. Catching it early provides an actionable message.

### 6. Archive tag

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
from pathlib import Path
import _paths
import _archive_tag
worktree = _paths.resolve_git_root()
result = _archive_tag.create_or_resolve(worktree, '<slug>', '$CHILD_BRANCH')
print(f'[mill-merge] archive-tag action: {result[\"action\"]} -- tag: {result[\"tag\"]}')
if result['moved_aside_to']:
    print(f'[mill-merge] prior tag preserved as {result[\"moved_aside_to\"]}')
"
```

Idempotently tags the cleanup-commit tip of the task branch. The helper handles the three conflict cases — same-SHA no-op, ancestor force-update, divergent move-aside — so re-running `/mill-merge` after a partial teardown never fails at this step. See `_archive_tag.py` for the resolution logic.

### 7. Home.md — mark [done]

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
from pathlib import Path; import _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
_client.set_phase(wiki_path, '<slug>', 'done')
"
```

**Failure handling after the squash landed on parent:** do NOT roll back the merge. Report the error, release all locks, tell the user "Merge landed on <parent> but <step> failed: <err>. Re-run `/mill-merge` to retry — Step 5's idempotency check will skip the squash." This is the non-destructive boundary: once the parent has the squash, it stays.

### 8. Release merge lock

Delete `<parent-path>/.scratch/merge.lock`. Run this in a `finally:` equivalent so the lock is released on every exit path.

**In-place mode:** no merge lock was acquired (Entry Steps 1 and 2 were skipped). Skip lock release.

### 9. Notify + report

`_notify.notify("mill-merge.done", f"task {slug} merged into {parent_branch}", slug=slug, parent=parent_branch)`.

Report to the user:

> "Merge complete for `<slug>`. Worktree intact — run `/mill-cleanup --apply` to remove worktree, branch, portal, and legacy wiki active-dir. Archive tag `archive/<slug>` created. Home.md updated to `[done]`."

**Verify after teardown:** confirm `git tag -l archive/<slug>` returns the tag, and `Home.md` shows `[done]` for `<slug>`.

**No self-report from this skill.** Reflection is the orchestrator's job — `mill-go` fires `/mill-self-report --auto` at its Handoff (step 6) when `pipeline.auto_report: true`. mill-merge is too narrow in scope to host its own reflection pass; if it is invoked from a separate thread (i.e. not chained from mill-go's auto_merge path), the user can run `/mill-self-report` manually if reflection is wanted.

## PR-path re-entry

PR-path re-entry for both `done` and `pr-pending` phases is now handled by the `### PR-state gate` in `## Entry`. All merged/open/closed/none routing is defined there.

## Rollback (Steps 1–5 only)

Any failure between lock acquisition (Step 1) and the squash landing on parent (Step 5) rolls back via the checkpoint `mill-merge-in` created:

```bash
git -C <parent-path> reset --hard mill-checkpoint-<name>
```

Release the merge lock. Preserve the checkpoint branch. Report the failure with the step name.

**Cleanup-commit rollback (Step 4):** if the cleanup commit fails mid-way (e.g. `git rm` succeeded but `git commit` failed), reset the task branch:

```bash
git reset --hard HEAD
```

Post-Step-5 failures (archive tag, Home.md, sidebar) are **not** rolled back — the merge on parent is production state and un-doing it would waste the squash that the PR or direct merge already committed to origin.

## Board discipline

- Wiki mutations go through `_client` calls (`set_phase`, `upsert_task`, `merge_tasks`); the daemon serializes all writes and pushes automatically. For multi-step atomic operations use `_client.merge_tasks`.
- Task state (status file, discussion file, plan dir, reviews dir) lives in the task directory (`_mill/` for current worktrees, `task/` for legacy) on the task branch — never in the wiki. The cleanup commit removes the entire `task_dir` directory from the branch tip before squash.
- Phase transitions via `_status.append_phase`; hand-editing `_mill/status.md` is banned.
- Merge-lock file lives at `<parent-path>/.scratch/merge.lock`. Never placed anywhere else — other skills expect it there.
