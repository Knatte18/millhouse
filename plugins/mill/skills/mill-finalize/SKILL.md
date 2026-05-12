---
name: mill-finalize
description: Orchestrate end-of-task finalization. Decides PR-vs-direct via config, dispatches to /git-pr (PR mode) or /mill-merge (direct mode). Invoked by mill-go Handoff Step 5 or run manually after mill-go completes.
---

# mill-finalize

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are the end-of-task finalization orchestrator. Your job is to choose the correct merge path and execute it. PR mode creates a pull request for human review before squash-merge; direct mode delegates immediately to /mill-merge. You never create a PR if the config says direct is fine, and you never squash directly if the config requires a PR.

## Entry

1. Resolve `git_root` via `_paths.resolve_git_root()`, `wiki_path` via `_paths.resolve_wiki_path(git_root)`.
2. `_wiki.sync_pull(wiki_path, slug="mill-finalize")`.
3. Load config: `cfg = _config.load_config(wiki_path, git_root)`.
   `signature: _config.load_config(wiki_path: Path, worktree_root: Path) -> dict` — deep-merges `<wiki_path>/config.yaml` with `<worktree_root>/.millhouse/config.local.yaml`.
4. Resolve task data: `active_data = _marker.task_data(git_root, wiki_path, cfg)`. On `MarkerError` → halt: "This worktree has no registered task branch — mill-finalize needs a tracked branch. Run mill-claim to register it, or merge manually."
5. `slug = active_data['slug']`.
6. `status_path = git_root / "task" / "status.md"`. Call `data = _status.read_status(status_path)`. Verify `data["phase"] == "done"`. If not: halt "status.md phase is `<value>`; mill-finalize expects `done`. Run mill-go first to bring the task to done."
   `signature: _status.read_status(status_path: Path) -> dict` — returns flat dict with keys `phase`, `task`, `current_batch`, `last_timeline_entry`, `blocked_reason`. Access phase via `data["phase"]` (not `data["yaml"]["phase"]` — that is `read_full`'s shape).

## Dispatch

Read these config keys from the deep-merged config (`cfg`):

- `require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))` — default false.
- `base_branch = cfg.get("git", {}).get("base_branch", "main")` — default "main".
- `parent_branch = _parent_branch.resolve(status_path, interactive=False)` — reads `parent:` from status.md. On `ParentBranchError` → halt with the error message.

**PR mode** activates when `require_pr is True` AND `parent_branch == base_branch`.

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
git add task/status.md
git commit -m "mill-finalize: pr-pending for <slug>"
```

### Step 3: Cleanup commit (issue #268)

Remove the task state directory so it does not appear in the PR diff:

```bash
git rm -r task/
git commit -m "chore: pre-merge cleanup"
```

Idempotency: if `task/` is already absent (re-run after partial failure), `git rm -r task/` prints "did not match any files" — treat as a no-op. If the working tree has nothing to commit, skip the commit.

### Step 4: Push task branch

```bash
CHILD_BRANCH=$(git branch --show-current)
git push origin "$CHILD_BRANCH"
```

### Step 5: Create PR

Invoke `/git-pr <base_branch>` (the base branch as argument). The skill generates title and body from commit history. It will not halt on its step 1.5 guard because `task/status.md` is absent (cleanup already ran). If `/git-pr` fails → halt and surface the error; do not roll back status.md or the cleanup commit (push already happened; operator can create the PR manually via GitHub UI or `gh pr create`).

### Step 6: Home.md → [pr-pending]

```python
with _wiki.wiki_lock(wiki_path, slug):
    _tasks_md.set_phase_at(wiki_path / "Home.md", slug, "pr-pending")
    _wiki.write_commit_push(wiki_path, ["Home.md"], f"task: pr-pending {slug}", slug=slug)
```

`signature: _tasks_md.set_phase_at(path: Path, slug: str, phase: str | None) -> None`
`signature: _wiki.wiki_lock(wiki_path: Path, slug: str) -> ContextManager[None]`
`signature: _wiki.write_commit_push(wiki_path: Path, paths: list[str], msg: str, *, slug: str) -> None`

### Step 7: Halt

Report to the user:

> "PR created for `<slug>`. Home.md updated to [pr-pending]. Run `/mill-merge` after the PR merges on GitHub to complete teardown (archive tag, [done] flip, worktree cleanup)."

## Board discipline

- `task/status.md` writes are committed on the task branch via `git add` + `git commit`. Never written to the wiki.
- Home.md writes go through `_wiki.write_commit_push` (acquires the wiki lock internally). For the read-modify-write in Step 6, wrap in `with _wiki.wiki_lock(wiki_path, slug):`.
- No `cd` to wiki or parent worktree. All parent-branch git operations use `git -C <parent-path>` if ever needed.
- `${CLAUDE_PLUGIN_ROOT}` for all intra-plugin path references.
