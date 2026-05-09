---
name: mill-merge
description: Finalize a completed task. Cleanup commit on task branch, squash-merge to parent, archive tag, Home.md flip, worktree+branch+portal removal, optional legacy wiki cleanup. PR-path honoured via git.require-pr-to-base. Runs from the child worktree.
---

# mill-merge

You are an integration engineer. Your job is to merge a completed task branch back to its parent safely. You never force-merge, never pass a defect downstream, and never lose work. Always run from the child worktree — never from the parent.

**Cross-worktree invariants (same as v1, load-bearing):**

- mill-merge runs from the child worktree.
- `cd <parent-worktree>` is forbidden — it corrupts the shell cwd for the rest of the session.
- All parent-branch git operations go through `git -C <parent-path>`.

## Entry

1. **Step 1 — Resolve mode + load config.**
   Resolve `git_root` via `_paths.resolve_git_root()`, `wiki_path` via `_paths.resolve_wiki_path(git_root)`, and `container_path` via `_paths.resolve_container_path(git_root)`. Load the deep-merged config: read `<wiki_path>/config.yaml` and overlay `<git_root>/.millhouse/config.local.yaml` if present (same deep-merge pattern used elsewhere). Try to call `active_data = _active.read_all(Path('.millhouse'))`. On `_active.ActiveError` (no marker / malformed), halt immediately with: *"This worktree has no active marker — `mill-merge` needs `status.md` to know the parent branch. Run `mill-claim` to convert this worktree to a tracked task, or merge manually."* On success: extract `slug = active_data['slug']` and call `mode_inplace = _inplace.is_inplace(active_data, git_root, cfg)`. Set `mode = 'inplace'` if `mode_inplace` else `mode = 'worktree'`.

   Stale-worktree edge: if `active_data` is not None AND the corresponding `<worktrees-dir>/<slug>/` directory exists AND the branch matches, call `_inplace.prompt_stale_worktree(slug, worktree_path)` and override `mode` based on the user's choice (`"inplace"` → `mode = 'inplace'`; `"worktree"` → `mode = 'worktree'`; `"abort"` → halt).

   If `mode == 'worktree'` AND `git worktree list --porcelain` shows the cwd is the main worktree:

   - When `active_data` is not None → halt with: "mill-merge from the main worktree requires in-place mode (no separate worktree exists for the active slug). The active marker says `<slug>` is on branch `<branch>`; mill-merge cannot proceed."

   Config keys to read:
   - `git.require-pr-to-base` (bool, default false) — when true AND parent-branch equals base-branch, the skill creates a PR instead of merging directly.
   - `git.base-branch` (string) — the repo's canonical base (usually `main`). Falls back to `main` if absent.

   **In-place mode bypass:** when `mode == 'inplace'`, the existing Steps 1 (acquire merge lock on parent) and 2 (invoke `mill-merge-in`) are SKIPPED. There is no separate parent worktree to lock; the merge is purely local. Continue from Step 3 (capture child branch) onward, but treat "child" and "parent" as branches in the same working tree (cwd is the hub). For the squash merge in Step 4 (Direct path), omit the `-C <parent-path>` flag — the merge runs against the current working tree directly.

2. `_wiki.sync_pull(<WIKI_PATH>, slug=slug)`.
3. Read slug via `_active.read_slug(Path(".millhouse"))` (already resolved in Step 1; reuse `active_data` — no second read needed).
4. *(Config already loaded in Step 1.)*
5. Resolve parent branch via `_parent_branch.resolve(status_path, interactive=<True unless called non-interactively>)`. `status_path` is `git_root / "task" / "status.md"` — state lives in `task/` on the task branch, not in the wiki.
6. **Phase gate — also the re-entry point for PR-path recovery.** Read `git_root/task/status.md`'s `phase:`.

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

## Teardown sequence

Steps 4–10 implement the canonical teardown. Each step is independent; a failed step is reported with its name so the user can re-run from that step (Step 4's squash idempotency handles the common re-entry case).

> **Recovery note:** After teardown completes, the cleanup commit is permanently visible via `git log archive/<slug>`. Operators can inspect (or restore) the task-branch state at any point via `git checkout archive/<slug>`.

### 4. Cleanup commit

On the task branch (current cwd), remove the state directory that belongs to the task lifecycle, not to production code:

```bash
git rm -r task/
git commit -m "chore: pre-merge cleanup"
```

**Why:** squashing a branch that already has cleanup as its tip means the squash commit on the parent never includes transient task metadata. The cleanup commit is itself preserved under the archive tag created in Step 6.

**Idempotency:** if `task/` is already absent (re-run after partial failure), `git rm -r` will warn "did not match any files" — treat as a no-op. If the resulting working tree has nothing to commit, skip the commit.

### 5. PR path or direct squash?

- **PR path** — activate when `git.require-pr-to-base: true` AND `parent-branch == base-branch`:

  ```bash
  gh pr create --base "<base-branch>" --head "$CHILD_BRANCH" \
      --title "<task: field from status.md>" \
      --body "<one-line summary from status.md>"
  ```

  Update `task/status.md` via `_status.append_phase(status_path, "pr-pending", _timestamp.now_utc_iso())` and push the task branch so the PR has the cleanup commit. Skip to Step 11 (Release lock) — no Home.md flip, no further cleanup. Re-run `/mill-merge` after the PR lands to continue from the PR-path re-entry.

- **Direct path** (everything else):

  ```bash
  git -C <parent-path> merge --squash "$CHILD_BRANCH"
  git -C <parent-path> commit -m "<task: field from status.md>"
  git -C <parent-path> push
  ```

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
         --title "<task: field from status.md>" \
         --body "Auto-created: direct push was rejected by branch protection.

     <task_description field from status.md>"
     ```

     Capture the PR URL printed by `gh pr create`.

  5. Push the child branch so the PR has the cleanup commit:

     ```bash
     git push origin "$CHILD_BRANCH"
     ```

  6. Append the `pr-pending` phase and commit+push `task/status.md` on the task branch:

     ```python
     _status.append_phase(status_path, "pr-pending", _timestamp.now_utc_iso())
     ```

     ```bash
     git add task/status.md && git commit -m "chore: pr-pending after branch-protection fallback" && git push
     ```

  7. Report to the user:

     ```
     Direct push rejected by branch protection — switched to PR path. PR: <url>. Consider setting `git.require-pr-to-base: true` in wiki/config.yaml.
     ```

  8. Skip to Step 11 (Release lock). Do not run Steps 6 (archive tag), 7 (Home.md flip), 8 (worktree/branch removal), or 9 (portal removal). Re-run `/mill-merge` after the PR lands to complete teardown.

  **Idempotency check:** if `git merge --squash` prints "Already up to date" or `git commit` prints "nothing to commit" → skip `push` and proceed to Step 6.

### 6. Archive tag

```bash
git tag archive/<slug> "$CHILD_BRANCH"
git push origin "archive/<slug>"
```

Tags the cleanup-commit tip of the task branch before the branch is deleted. The tag is cheap, persistent, and lets any operator recover the full task history via `git checkout archive/<slug>`.

### 7. Home.md — mark [done]

Under the wiki shared lock so no concurrent task writes Home.md mid-flip.

```python
with _wiki.wiki_lock(<WIKI_PATH>, slug):
    home_text = home_path.read_text(encoding="utf-8")
    new_text = _tasks_md.set_phase(home_text, slug, "done")
    home_path.write_text(new_text, encoding="utf-8")
    _wiki.write_commit_push(<WIKI_PATH>, ["Home.md"], f"task: complete and merge {slug}", slug=slug)
```

**Failure handling after the squash landed on parent:** do NOT roll back the merge. Report the error, release all locks, tell the user "Merge landed on <parent> but <step> failed: <err>. Re-run `/mill-merge` to retry — Step 5's idempotency check will skip the squash." This is the non-destructive boundary: once the parent has the squash, it stays.

### 8. Drop the worktree + branch

**Worktree mode:**

Call `_worktree.remove_safe` — it strips every junction declared in `wiki/config.yaml` inside the worktree (`.wiki`, `.active`, plus any future entries) BEFORE removing the worktree, and falls back to `shutil.rmtree` only if `git worktree remove --force` fails with a long-path error. The junction-strip is non-skippable; you cannot lose the wiki by accident.

```bash
python -c "
from pathlib import Path
import _wiki, _worktree
wiki = Path(r'<WIKI_PATH>').resolve()
worktree = Path(r'<container-path>/wts/<slug>').resolve()
parent = Path(r'<parent-path>').resolve()
_worktree.remove_safe(worktree, cwd=parent, junctions_cfg=_wiki.read_junctions(wiki))
"
git -C <parent-path> branch -D "$CHILD_BRANCH"
```

**Why this matters (GitHub issue #100):** `git worktree remove --force` is junction-safe on its own, but on Windows it can fail with "Filename too long" when `.scratch/` contains deeply nested claude session JSONs. A naive fallback to `cmd /c rmdir /s /q` or `shutil.rmtree` follows NTFS junctions by default and wipes the wiki, the portals directory, and any sibling worktree the junctions point to. `_worktree.remove_safe` strips junctions first so the fallback is junction-blind. Never invoke `rmdir /s` or `shutil.rmtree` on a worktree path directly — always go through `remove_safe`.

**On `remove_safe` raising:**

| Exception | Handling |
|---|---|
| `WorktreeLockedError` | Print to stderr: `"[worktree] cannot remove <path>: directory is in use — close this CC session and run:\n    git worktree remove --force <path>\n    git branch -D $CHILD_BRANCH"`. Skip the `git branch -D "$CHILD_BRANCH"` line that follows `remove_safe`. Continue to Step 9. |
| `WorktreeError` (other) | Halt with the captured error message — do NOT manually run `rmdir` or `rmtree` as a workaround. |

**In-place mode:** skip `git worktree remove`; from cwd run:
```bash
git checkout <parent_branch>
git branch -D "$CHILD_BRANCH"
```

Also remove `<git_root>/.millhouse/active.slug.md` (the canonical in-place marker).

### 9. Remove portal entry

```python
_junction.remove(container_path / "portals" / slug)
```

Tolerate already-gone. `container_path` was resolved in Entry Step 1 via `_paths.resolve_container_path(git_root)`.

### 10. Remove wiki active directory

Always attempt to remove `wiki_path / "active" / slug`. An existence guard prevents `FileNotFoundError` from racing or partially-migrated states:

1. `if (wiki_path / "active" / slug).exists(): shutil.rmtree(wiki_path / "active" / slug)`.
2. If the directory existed and was removed, commit+push via `_wiki.write_commit_push(<WIKI_PATH>, [f"active/{slug}/"], f"task: remove active dir {slug}", slug=slug)`.

If the directory does not exist, skip the commit — the guard makes this safe to call unconditionally.

### 11. Regenerate sidebar + release merge lock

`_sidebar.regenerate(<WIKI_PATH>)` (re-acquires its own wiki lock internally). Pushes a `_Sidebar.md` update.

Delete `<parent-path>/.scratch/merge.lock`. Run this in a `finally:` equivalent so the lock is released on every exit path.

**In-place mode:** no merge lock was acquired (Entry Steps 1 and 2 were skipped). Skip lock release.

### 12. Notify + report

`_notify.notify("mill-merge.done", f"task {slug} merged into {parent_branch}", slug=slug, parent=parent_branch)`.

Report to the user:

> "Merge complete for `<slug>`. Worktree and branch removed. Archive tag `archive/<slug>` created. Home.md updated."

**Verify after teardown:** confirm `<container>/wts/<slug>` is gone, `$CHILD_BRANCH` is gone from `git branch`, `<container>/portals/<slug>` is gone, `git tag -l archive/<slug>` returns the tag, and `Home.md` shows `[done]` for `<slug>`.

### 13. Auto-fire self-report

If the deep-merged config has `pipeline.auto_report: true`, invoke `/mill-self-report --auto`. The skill checks `gh auth` itself and bails cleanly if absent.

This placement (post-teardown) is deliberate: self-reporting fires after every observable failure mode — implementation, planning, junction teardown, squash conflicts, push rejection, sidebar regen, Home.md flip, etc. mill-go used to fire self-report at its Handoff, but that placement could not observe merge-time failures. The trigger now lives here so a single self-report covers the full task lifecycle.

**Failure path:** if any earlier step in this skill halted (rollback, PR-pending, lock-busy), Step 13 is skipped — those halts already surface diagnostics to the user, and self-report would only add noise. Self-reporting fires only after a successful teardown.

## PR-path re-entry

When the entry-phase gate sees `phase: pr-pending`:

1. Resolve the PR via `gh pr list --head "$CHILD_BRANCH" --state all --json state,mergeCommit,number --jq '.[0]'`.
2. Interpret:
   - `state == "MERGED"` → continue to Step 6 (archive tag). Skip Steps 1–5 (merge lock no longer needed; squash has already landed via the external PR). The rest of the teardown (tag, Home.md flip, worktree/branch/portal removal, legacy wiki cleanup) runs as normal.
   - `state == "OPEN"` → report "PR #<N> still open. Waiting — re-run `/mill-merge` after it lands." Halt.
   - `state == "CLOSED"` without merge → report "PR #<N> closed without merging. Task branch is orphaned — run `/mill-abandon` if you want to discard, or open a new PR manually."
   - No PR found → report "status.md says pr-pending but no PR on this branch; inspect manually."

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

Post-Step-5 failures (archive tag, Home.md, sidebar, worktree/branch/portal removal) are **not** rolled back — the merge on parent is production state and un-doing it would waste the squash that the PR or direct merge already committed to origin.

## Board discipline

- Home.md writes go through `_wiki.write_commit_push` (which acquires the wiki lock internally). For multi-operation windows use `with _wiki.wiki_lock(wiki_path, slug):`.
- `active/<slug>/` deletion commits separately via `_wiki.write_commit_push` after the wiki lock is released (Step 10 always attempts this; the existence guard makes it safe).
- Task state (`task/status.md`, `task/discussion.md`, `task/plan/`, `task/reviews/`) lives in `task/` on the task branch — never in the wiki. The cleanup commit removes the entire `task/` directory from the branch tip before squash.
- Phase transitions via `_status.append_phase`; hand-editing `task/status.md` is banned.
- Merge-lock file lives at `<parent-path>/.scratch/merge.lock`. Never placed anywhere else — other skills expect it there.
