---
name: mill-merge
description: Finalize a completed task. Sync parent, squash-merge back, flip Home.md to [done], delete the active task dir, remove junctions, drop the worktree + branch. PR-path honoured via git.require-pr-to-base. Runs from the child worktree.
---

# mill-merge

You are an integration engineer. Your job is to merge a completed task branch back to its parent safely. You never force-merge, never pass a defect downstream, and never lose work. Always run from the child worktree — never from the parent.

**Cross-worktree invariants (same as v1, load-bearing):**

- mill-merge runs from the child worktree.
- `cd <parent-worktree>` is forbidden — it corrupts the shell cwd for the rest of the session.
- All parent-branch git operations go through `git -C <parent-path>`.

## Entry

1. **Step 1 — Resolve mode + load config.**
   Resolve `git_root` via `_paths.resolve_git_root()` and `wiki_path` via `_paths.resolve_wiki_path(git_root)`. Load the deep-merged config: read `<wiki_path>/config.yaml` and overlay `<git_root>/.millhouse/config.local.yaml` if present (same deep-merge pattern used elsewhere). Try to call `active_data = _active.read_all(Path('.millhouse'))`. On `_active.ActiveError` (no marker / malformed), set `active_data = None` and `mode = 'worktree'` (legacy behaviour). On success: extract `slug = active_data['slug']` and call `mode_inplace = _inplace.is_inplace(active_data, git_root, cfg)`. Set `mode = 'inplace'` if `mode_inplace` else `mode = 'worktree'`.

   Stale-worktree edge: if `active_data` is not None AND the corresponding `<worktrees-dir>/<slug>/` directory exists AND the branch matches, call `_inplace.prompt_stale_worktree(slug, worktree_path)` and override `mode` based on the user's choice (`"inplace"` → `mode = 'inplace'`; `"worktree"` → `mode = 'worktree'`; `"abort"` → halt).

   If `mode == 'worktree'` AND `git worktree list --porcelain` shows the cwd is the main worktree:

   - When `active_data` is not None → halt with: "mill-merge from the main worktree requires in-place mode (no separate worktree exists for the active slug). The active marker says `<slug>` is on branch `<branch>`; mill-merge cannot proceed."
   - When `active_data is None` → halt with: "No active in-place task found and cwd is the main worktree; mill-merge must run from a task worktree."

   Config keys to read:
   - `git.require-pr-to-base` (bool, default false) — when true AND parent-branch equals base-branch, the skill creates a PR instead of merging directly.
   - `git.base-branch` (string) — the repo's canonical base (usually `main`). Falls back to `main` if absent.

   **In-place mode bypass:** when `mode == 'inplace'`, the existing Steps 1 (acquire merge lock on parent) and 2 (invoke `mill-merge-in`) are SKIPPED. There is no separate parent worktree to lock; the merge is purely local. Continue from Step 3 (capture child branch) onward, but treat "child" and "parent" as branches in the same working tree (cwd is the hub). For the squash merge in Step 4 (Direct path), omit the `-C <parent-path>` flag — the merge runs against the current working tree directly.

2. `_wiki.sync_pull(<WIKI_PATH>)`.
3. Read slug via `_active.read_slug(Path(".millhouse"))` (already resolved in Step 1; reuse `active_data` — no second read needed).
4. *(Config already loaded in Step 1.)*
5. Resolve parent branch via `_parent_branch.resolve(status_path, interactive=<True unless called non-interactively>)`.
6. **Phase gate — also the re-entry point for PR-path recovery.** Read `status.md`'s `phase:`.

   | phase | action |
   | --- | --- |
   | `done` | fresh merge — continue to Step 1 |
   | `pr-pending` | see *PR-path re-entry* below |
   | `complete` / missing / other | halt with "status.md phase is <value>; mill-merge expects `done`. If the task is not finished, run mill-go first." |

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

### 4. PR path or direct squash?

- **PR path** — activate when `git.require-pr-to-base: true` AND `parent-branch == base-branch`:

  ```bash
  gh pr create --base "<base-branch>" --head "$CHILD_BRANCH" \
      --title "<task: field from status.md>" \
      --body "<one-line summary from status.md + link to active/<slug>/>"
  ```

  Update `status.md`: `_status.append_phase(status_path, "pr-pending", _timestamp.now_utc_iso())`. Commit+push via `_wiki.write_commit_push`. Skip to Step 10 (Release lock) — no Home.md flip, no cleanup. The user (or a later `/mill-merge` re-run after the PR lands) continues from the PR-path re-entry below.

- **Direct path** (everything else):

  ```bash
  git -C <parent-path> merge --squash "$CHILD_BRANCH"
  git -C <parent-path> commit -m "<task: field from status.md>"
  git -C <parent-path> push
  ```

  **Idempotency check:** if `git merge --squash` prints "Already up to date" or `git commit` prints "nothing to commit" → skip `push` and proceed to Step 5. This lets the user re-run mill-merge after a Step-5-or-later failure without re-merging.

### 5. Home.md — mark [done]

This step and the next happen under the wiki shared lock so no other task writes Home.md mid-flip.

1. `_wiki.acquire_lock(<WIKI_PATH>, slug, timeout_seconds=30)`.
2. Read `<WIKI_PATH>/Home.md`. Use `_tasks_md.set_phase(text, slug, "done")` to rewrite the single line. Write the result.
3. Commit+push via `_wiki.write_commit_push(<WIKI_PATH>, ["Home.md"], f"task: complete and merge {slug}")`.
4. Keep the lock — Step 6 also holds it.

**Failure handling after the direct squash landed on parent:** do NOT roll back the merge. Report the error, release both locks, tell the user "Merge landed on <parent> but <step> failed: <err>. Re-run `/mill-merge` to retry — Step 4's idempotency check will skip the merge." This is v1's non-destructive boundary: once production has the squash, it stays.

### 6. Delete `<WIKI_PATH>/active/<slug>/`

While still holding the wiki lock:

1. `shutil.rmtree(wiki_path / "active" / slug)`.
2. Commit+push via `_wiki.write_commit_push(<WIKI_PATH>, [f"active/{slug}/"], f"task: complete and merge {slug}")`. The commit records the deletion.
3. Release the wiki lock now — the remaining steps don't touch shared wiki state.

### 7. Regenerate sidebar

`_sidebar.regenerate(<WIKI_PATH>)` (re-acquires its own wiki lock internally). Pushes a `_Sidebar.md` update.

### 8. Remove junctions owned by this worktree

For every entry in `_wiki.read_junctions(<WIKI_PATH>)`, compute the junction path relative to the worktree root (e.g. `.millhouse/wiki`, `.active/`), and call `_junction.remove(junction_path)` on each. Tolerate already-gone.

**In-place mode:** also remove the `.active` junction at `git_root / ".active"` via `_junction.remove(git_root / ".active")`. This junction is hub-root-level for in-place tasks (per `wiki/config.yaml`'s `junctions:` block).

### 9. Release merge lock

Delete `<parent-path>/.scratch/merge.lock`. Run this in a `finally:` equivalent so the lock is released on every exit path.

**In-place mode:** no merge lock was acquired (Steps 1 and 2 were skipped). Skip this step.

### 10. Drop the worktree + branch

**Worktree mode:**
```bash
git -C <parent-path> worktree remove --force <self-worktree-path>
git -C <parent-path> branch -d "$CHILD_BRANCH"
```

If `worktree remove` fails with "is not empty" or "is in use" on Windows: surface a hint — "couldn't remove <path>: directory is in use. Close any editor / terminal / file-explorer window pointing at it and re-run `/mill-merge` (Step 4's idempotency will skip the merge)." Do not name a specific diagnostic tool in the message.

**In-place mode:** skip `git worktree remove`; from cwd run:
```bash
git checkout <parent_branch>
git branch -d "$CHILD_BRANCH"
```

Also remove `<git_root>/.millhouse/active.slug.md` (the canonical in-place marker).

### 11. Notify + report

`_notify.notify("mill-merge.done", f"task {slug} merged into {parent_branch}", slug=slug, parent=parent_branch)`.

Report to the user:

> "Merge complete for `<slug>`. Worktree and branch removed. Home.md updated."

## PR-path re-entry

When the entry-phase gate sees `phase: pr-pending`:

1. Resolve the PR via `gh pr list --head "$CHILD_BRANCH" --state all --json state,mergeCommit,number --jq '.[0]'`.
2. Interpret:
   - `state == "MERGED"` → continue to Step 5 (Home.md flip). Skip Steps 1–4 (merge lock no longer needed; merge has already landed via the external PR). The rest of the cleanup (active/, sidebar, junctions, worktree removal) runs as normal.
   - `state == "OPEN"` → report "PR #<N> still open. Waiting — re-run `/mill-merge` after it lands." Halt.
   - `state == "CLOSED"` without merge → report "PR #<N> closed without merging. Task branch is orphaned — run `/mill-abandon` if you want to discard, or open a new PR manually."
   - No PR found → report "status.md says pr-pending but no PR on this branch; inspect manually."

## Rollback (Steps 1–4 only)

Any failure between lock acquisition (Step 1) and the squash landing on parent (Step 4) rolls back via the checkpoint `mill-merge-in` created:

```bash
git -C <parent-path> reset --hard mill-checkpoint-<name>
```

Release the merge lock. Preserve the checkpoint branch. Report the failure with the step name.

Post-Step-4 failures (Home.md, sidebar, junctions, worktree removal) are **not** rolled back — the merge on parent is production state and un-doing it would waste the squash that the PR or direct merge already committed to origin.

## Board discipline

- Home.md writes go through `_wiki.write_commit_push` with the shared lock held.
- `active/<slug>/` deletion commits separately under the same shared lock.
- Phase transitions via `_status.append_phase`; hand-editing status.md is banned.
- Merge-lock file lives at `<parent-path>/.scratch/merge.lock`. Never placed anywhere else — other skills expect it there.
