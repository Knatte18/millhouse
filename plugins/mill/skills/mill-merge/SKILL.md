---
name: mill-merge
description: Squash-merge a completed task branch to its parent, create archive tag, flip Home.md [done]. Direct merge only — PR dispatch lives in mill-finalize. Worktree, branch, portal, and legacy wiki cleanup handled by /mill-cleanup. Runs from the child worktree.
---

# mill-merge

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are an integration engineer.
Your job is to merge a completed task branch back to its parent safely.
You never force-merge, never pass a defect downstream, and never lose work.
Always run from the child worktree — never from the parent.

**Cross-worktree invariants (same as v1, load-bearing):**

- mill-merge runs from the child worktree.
- `cd <parent-worktree>` is forbidden — it corrupts the shell cwd for the rest of the session.
- All parent-branch git operations go through `git -C <parent-path>`.

## Entry

1. **Step 1 — Resolve mode + load config.**
   Resolve `git_root` via `_paths.resolve_git_root()`, `wiki_path` via `_paths.resolve_wiki_path(git_root)`, and `container_path` via `_paths.resolve_container_path(git_root)`.
   Load the deep-merged config: `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`.
   Try to call `active_data = _marker.task_data(git_root, wiki_path, cfg)`.
   On `_marker.MarkerError` (detached HEAD, prefix mismatch, slug absent from Home.md), halt immediately with: *"This worktree has no registered task branch — `mill-merge` needs `status.md` to know the parent branch.
   Run `mill-claim` to convert this worktree to a tracked task, or merge manually."*
   On success: extract `slug = active_data['slug']` and call `mode_inplace = _inplace.is_inplace(slug, git_root, cfg)`.
   Set `mode = 'inplace'` if `mode_inplace` else `mode = 'worktree'`.

   Stale-worktree edge: this disambiguation procedure — including its `status.md` write/commit/push side effects below — fires only when a genuine ambiguity exists.
   Run `git worktree list --porcelain` unconditionally first (cheap, read-only, no side effects) and inspect the entry for `<worktrees-dir>/<slug>/`.
   If that entry is present, current, and its branch matches the active task branch: no ambiguity — the `mode` already set above (from `_inplace.is_inplace()`) is trustworthy as-is.
   Skip the rest of this Stale-worktree edge block and continue to Step 1.5.
   If that entry is absent from the output, or its recorded branch no longer matches the active task branch (a stale registration): genuine ambiguity — treat the directory as in-place cruft, `mode = 'inplace'`, and run the disambiguation procedure below.
   Before appending the timeline row below, derive the path variables inline (Path Setup in Step 1.5 has not run yet at this point): `worktree_root = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` and `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`.
   Capture `original_phase = _status.read_full(status_path)["yaml"].get("phase")` before mutating anything, then `_status.append_phase(status_path, f"self-resolved-stale-worktree-{mode}", _timestamp.now_utc_iso())`. `append_phase` overwrites the top-level `phase:` field as well as appending the timeline row — since Step 5 immediately below reads that same `phase:` field and expects exactly `done` or `pr-pending`, restore it before continuing: `_status.append_phase(status_path, original_phase, _timestamp.now_utc_iso())`.
   Commit both mutations together: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-merge: self-resolved stale-worktree ambiguity ({mode})"` and push before continuing.
   If the entry is present but its state does not cleanly resolve to either "current and matching" or "stale/absent/mismatched" above (an inconclusive `git worktree list --porcelain` read), fall back to the existing safe default and halt: report to the operator that the branch matches the current cwd AND `<worktree_path>` exists, that `git worktree list --porcelain` output was inconclusive, and that the run is stopping rather than guessing.

   If `mode == 'worktree'` AND `git worktree list --porcelain` shows the cwd is the main worktree:

   - When `active_data` is not None → halt with: "mill-merge from the main worktree requires in-place mode (no separate worktree exists for the active slug).
     The active marker says `<slug>` is on branch `<branch>`;
     mill-merge cannot proceed."

   Config keys to read:
   - `git.require_pr_to_base` (bool, default false) — read for the branch-protection fallback message only;
     PR dispatch itself is handled by mill-finalize.
   - `git.base_branch` (string) — the repo's canonical base (usually `main`).
     Falls back to `main` if absent.
     Used in the branch-protection fallback to set the PR `--base` target correctly.

   **In-place mode bypass:** when `mode == 'inplace'`, the existing Steps 1 (acquire merge lock on parent) and 2 (invoke `mill-merge-in`) are SKIPPED.
   There is no separate parent worktree to lock;
   the merge is purely local.
   Continue from Step 3 (capture child branch) onward, but treat "child" and "parent" as branches in the same working tree (cwd is the hub).
   For the squash merge in Step 5 (Direct squash), omit the `-C <parent-path>` flag — the merge runs against the current working tree directly.

1.5.
**Path Setup.** `cfg` was loaded in step 1;
`container_path` and `slug` are in scope from Step 1. (If the stale-worktree edge above already derived `worktree_root`/`status_path` inline, this step is a no-op re-derivation — the computation is idempotent.)
Derive:
   ```python
   worktree_root = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)
   status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
   task_dir = status_path.parent
   ```
   No in-place vs worktree mode branch is needed: `resolve_active_worktree` checks in-place mode first (returns `git_root` when `_inplace.is_inplace` is true) and `resolve_active_hub` covers both modes, so the single call is correct whether `mode == 'inplace'` or `'worktree'`.
   Use these variables for all subsequent path references.

2. Slug already resolved in Step 1;
   reuse `active_data['slug']` — no second read needed.
3. *(Config already loaded in Step 1.)*
4. Resolve parent branch. `slug` is already bound in Entry Step 1 as `active_data['slug']`. `status_path` is resolved via `_paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (set in Path Setup step 1.5) and `task_dir = status_path.parent` — state lives in `task_dir` on the task branch, not in the wiki.
   Branch on `status_path.exists()` before calling `_parent_branch.resolve(...)` at all — the "file entirely absent" case (typical in the closed-PR re-entry path, where an earlier `mill-merge` invocation's own Step 4 cleanup commit already removed `task_dir`) has a resolvable fallback that the "file exists but the `parent:` row is missing" case does not.
   If `status_path.exists()` is `False`: skip the `_parent_branch.resolve(...)` call entirely for this run, set `parent_branch = cfg.git.base_branch` directly (already loaded in Entry Step 1, "Config keys to read," with its own documented `"main"` fallback when absent), and report the one-line operator-facing notice "status.md absent; assuming parent branch is `<base_branch>` (config `base_branch`) -- if this task's true parent differs (e.g. a stacked branch merging into something other than `base_branch`), abort and resolve manually."
   If `status_path.exists()` is `True`: call `_parent_branch.resolve(status_path, interactive=False, expected_slug=slug)` exactly as before.

   **Liveness check (#817):** when `_parent_branch.resolve(...)` above returns successfully, verify the returned `parent_branch` is still live:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import _preflight; exit(_preflight.check_helpers(['_parent_branch:check_liveness']))
   "
   ```

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import json
   import _parent_branch, _paths
   git_root = _paths.resolve_git_root()
   print(json.dumps({'alive': _parent_branch.check_liveness('<parent_branch>', git_root)}))
   "
   ```

   If `alive` is `true`, continue as before — no further action.

   If `alive` is `false`, resolve a successor:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import json
   import _parent_branch, _paths, _config
   git_root = _paths.resolve_git_root()
   cfg = _config.load_config(_paths.resolve_hub_path(), git_root)
   print(json.dumps(_parent_branch.resolve_dead_parent('<parent_branch>', git_root, cfg)))
   "
   ```

   Report the result to the operator and require confirmation before mill-merge proceeds, except in the `cycle` case, which always halts outright with no confirmation prompt (there is no candidate branch to confirm):
   - `outcome: "resolved"` — "Parent branch `<parent_branch>` no longer exists on origin. It appears to have been merged and archived (chain: `<hops, joined by ' -> '>`). The resolved successor parent is `<branch>`. Confirm before mill-merge proceeds against `<branch>`."
   - `outcome: "fallback"` — "Parent branch `<parent_branch>` no longer exists on origin. No archive-tag chain could resolve a successor (`<reason>`). Falling back to the repo's base branch `<branch>`. Confirm before mill-merge proceeds against `<branch>`."
   - `outcome: "cycle"` — halt outright, no confirmation prompt: "Archive-tag chain walk for `<parent_branch>` hit its 10-hop cap without resolving a live parent (chain: `<hops, joined by ' -> '>`). Investigate manually."

   On operator confirmation (the `resolved` and `fallback` cases only), rebind `status.md`'s `parent:` row to the new branch and use it for the remainder of this run. Derive `status_path` the same way the rest of this Entry Step 4 already does (Path Setup 1.5's `worktree_root = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` then `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`) — never a fresh `_paths.resolve_hub_path()` + literal `'_mill/status.md'` derivation, which walks from cwd instead of the already-resolved `worktree_root` and bypasses the config-driven `cfg['paths']['status_md']` the rest of the file always reads:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import _status, _paths, _config
   git_root = _paths.resolve_git_root()
   container_path = _paths.resolve_container_path(git_root)
   cfg = _config.load_config(_paths.resolve_hub_path(), git_root)
   worktree_root = _paths.resolve_active_hub(container_path, '<slug>', cfg=cfg, git_root=git_root)
   status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
   _status.update_field(status_path, 'parent', '<resolved_branch>')
   "
   git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-merge: rebind dead parent branch for {slug}"
   git -C <worktree> push
   ```

   `parent_branch` for the remainder of this run is now `<resolved_branch>`.

   This liveness check applies only to the `status_path.exists()` True branch (the actual `_parent_branch.resolve(...)` call) — it does not apply to the `status_path.exists()` False fallback branch above it, which already sets `parent_branch = cfg.git.base_branch` directly and has its own separate operator-facing notice.

   On `_parent_branch.ParentBranchError` (status.md is missing the `parent:` row): `_status.set_blocked(status_path, f"missing parent: row for {slug}", timestamp=_timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-merge: blocked (missing parent: row) for {slug}"` and push, then halt with `BLOCKED: status.md is missing the parent: row for <slug> -- mill-spawn should have written it; set it manually and re-run /mill-merge.`
5. **Phase gate — also the re-entry point for PR-path recovery.**

   **Try `_mill/status.md` first.**
   If `status_path.exists()`, try to read the raw `slug:` field via `_status.read_full(status_path)["yaml"].get("slug")`, wrapped in a try/except to handle malformed status.md files (e.g., missing yaml fence) gracefully — on parse error, treat the field as absent and fall through to the wiki lookup below (mirroring `_parent_branch._read_parent_from_status`'s tolerance).
   Read raw field, NOT `_status.read_slug()`, which falls back to `status_path.parent.name` (always literally `_mill` in this layout) when the field is absent, so it can never tell "field absent" apart from "field present and different";
   reading the raw field keeps this check's absent-field semantics consistent with `_parent_branch.py`'s `expected_slug` check (an absent `slug:` row is a no-op there, not a mismatch).
   Compare the result against `slug` (the already-resolved `active_data['slug']` from Entry Step 1) ONLY when the raw field is not `None`.

   If the raw `slug:` field is present AND does not match `slug`: do not read `phase:` from the table below at all.
   Instead, fall through to the exact branch below for "`status_path` is absent".

   Otherwise (slugs match,
   or the raw field is absent) read `phase:` from `status_path` and apply the table below.

   If `status_path` is absent (or the slug mismatch above triggered fallthrough): call `task = _client.get_task(wiki_path, slug)` (where `from wiki import _client`).
   Guard: `if task is None: halt("_mill/status.md absent and slug '<slug>' not found in wiki; cannot determine merge state.")`.
   If `task["status"] == "pr-pending"` → treat as `pr-pending` below.
   Otherwise → halt with "_mill/status.md absent and wiki does not show pr-pending for '<slug>';
   cannot determine merge state. (status.md slug did not match task slug '<slug>')" -- append the parenthetical only when a slug mismatch (not a genuinely absent file) triggered this branch.

   | phase | action |
   | --- | --- |
   | `done` | see *PR-state gate* below |
   | `pr-pending` | see *PR-state gate* below |
   | `complete` / missing / other | halt with "status.md phase is `<value>`; mill-merge expects `done`. If the task is not finished, run mill-go first." |

   When `phase: done`, cache the task fields from `_mill/status.md` now, while status.md still exists and before the Teardown Steps run:
   - `cached_task = _status.read_full(status_path)["yaml"].get("task", slug)` — the task title used in Step 5's squash commit message and Step 6's PR title.
   - `cached_task_description = _status.read_full(status_path)["yaml"].get("task_description", cached_task)` — the task description used in Step 6's PR body.

   Use `cached_task` and `cached_task_description` in all subsequent references to "task: field from status.md" and "task_description field from status.md".
   Step 4's `git rm -r _mill/` deletes status.md before Step 5 runs;
   reading from a cached variable avoids the read-after-delete failure.

### PR-state gate

This gate runs for both `done` and `pr-pending` phases, immediately after Step 5's phase check.
It must execute before any squash or teardown work begins.

**Capture child branch** (note: this is captured here, earlier than the existing Step 3 capture, because the gate needs it before any parent-side operations;
Step 3's capture remains for the squash flow):

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

- **`merged`** -- cleanup-only teardown: run Step 4 (cleanup commit, so the archive tag reflects a clean tip), then Step 5.5 (cache-helper preflight -- guards Step 6's `_archive_tag` import against a stale plugin cache `ModuleNotFoundError`), then Step 6 (archive tag), Step 7 (Home.md `[done]`), Step 8 (release lock -- no-op if never acquired), Step 9 (notify/report).
  Skip Steps 1, 2, and 5.

  Note: the local parent branch is intentionally NOT fast-forwarded here;
  it resyncs on the next parent-side fetch/pull.
  Do not add a parent ff-sync step (discussion Decisions/merged-remote-cleanup-only, Local-parent staleness).

- **`open`** -- halt and report, never auto-close:

  > "PR #<number> is still open -- close or merge it on GitHub, then re-run `/mill-merge`."

- **`closed`** -- this is the expected success signal for the `require_pr_to_base: true` inspection flow.
  The operator reviewed the PR on GitHub and closed it without merging — that IS the approval.
  Do NOT protest that the PR was not merged on GitHub.
  Do NOT ask for confirmation.
  Proceed immediately with the normal local squash exactly as the `done` fresh-merge flow (continue to Step 1).

  **Commit-message source:** the `closed` route can be reached from a `pr-pending` re-entry where `_mill/status.md` is typically absent (mill-finalize already `git rm -r`'d `task_dir`), so `cached_task` and `cached_task_description` may be undefined.
  Establish them before continuing to Step 1:

  - If `status_path.exists()`: read them exactly as the `done` branch caching block does (`_status.read_full(status_path)["yaml"].get("task", slug)` / `.get("task_description", cached_task)`).
  - Otherwise: `task = _client.get_task(wiki_path, slug)`.
    Guard: `if task is None: halt("slug '<slug>' not found in wiki; cannot derive commit message for closed route")`.
    Then: `cached_task = task["title"]`, `cached_task_description = task.get("title")` (title is the available field;
    there is no separate description field in the wiki task).
    This fallback feeds Step 5's squash commit message.

  **Caution -- branch-protection interaction:** in a branch-protected repo the Step 5 push may be rejected, triggering the existing Step 5 branch-protection fallback that auto-creates a NEW PR -- which contradicts the operator's deliberate close-without-merge.
  The fallback itself stays as-is, but be aware that `closed` -> local-squash is not guaranteed terminal (discussion Decisions/closed-no-merge-proceeds, Branch-protection interaction).

- **`none`** -- silent fallback to phase-based behavior (no new output):
  - If `phase: done`: continue to Step 1 (today's direct squash).
  - If `phase: pr-pending`: keep today's halt -- "status.md says pr-pending but no PR on this branch;
    inspect manually."

## Steps

### 1. Acquire merge lock on parent

Resolve the parent worktree path from `git worktree list --porcelain` (the entry whose branch matches the parent branch).
Write `<parent-path>/.scratch/merge.lock` with three lines: `pid`, `timestamp` (ISO-8601 UTC Z), `branch` (the child branch about to merge).

If the lock already exists:
- Re-read it.
  If timestamp is older than 5 min → stale → overwrite.
- Otherwise wait up to 5 min polling every 10 s for the lock to clear.
  After 5 min → halt with the holder info so the user can intervene.

### 2. Invoke mill-merge-in

Call the `mill-merge-in` skill, passing `<parent_branch>` — the value already resolved and bound at Entry Step 4 (including that step's `status_path`-absent fallback and its liveness-check rebind) — as `mill-merge-in`'s optional positional `<branch>` argument (documented in `mill-merge-in/SKILL.md` Entry step 3 as "for ad-hoc syncing from some other branch than the task's declared parent"), rather than a bare invocation.
Passing the value explicitly is what lets `mill-merge-in` skip its own independent `status.md` read — see Card 2 in this same batch for the corresponding `mill-merge-in`-side change this depends on.
This applies to Step 2 itself, not any one route — both the `done` fresh-merge route and the `closed` PR-state-gate route (the only two routes that reach Step 2 via `## Entry`'s "In-place mode bypass" / PR-state-gate routing) pass the argument.
If it reports failure → release the merge lock and halt.
Capture the checkpoint branch name it prints;
you may need it on rollback.

**Rebind on dead-parent substitution (#977):** if `mill-merge-in`'s Step 6 report (see `mill-merge-in/SKILL.md` Step 6, "Substituted parent branch" line) includes a `Substituted parent branch: <old> -> <new>` line, rebind `parent_branch` (this skill's own variable, bound at Entry Step 4) to `<new>` before continuing to Step 3. This is required because `mill-merge-in`'s own dead-parent liveness check (its Entry section's "Liveness check (#817)" paragraph) only ever resolves a successor for its own run — it has no mechanism to reach back into this caller's already-bound `parent_branch`, and Step 5 below reuses `parent_branch`/`<parent-path>` verbatim from here through push/rollback.
If `mode == 'worktree'`, also re-derive `<parent-path>` for the new branch: re-run `git worktree list --porcelain` and locate the entry whose branch matches `<new>`, the same lookup Step 1 above used for the original `parent_branch`.
If `mode == 'inplace'`, there is no separate parent worktree to re-derive (Step 5 already omits `-C <parent-path>` in that mode per the "In-place mode bypass" note in `## Entry`) — rebinding `parent_branch` alone is sufficient.

### 3. Capture child branch

```bash
CHILD_BRANCH=$(git branch --show-current)
```

Do this before switching to `git -C <parent-path>` calls — once you are operating on the parent, `git branch --show-current` there will report the parent's branch, not yours.

## Teardown sequence

Steps 4–7 implement the canonical merge sequence;
worktree, portal, and wiki active-dir teardown is handled by `/mill-cleanup`.
Each step is independent;
a failed step is reported with its name so the user can re-run from that step (Step 4's squash idempotency handles the common re-entry case).

**Step 8 (release merge lock) executes out of its numeric position on the direct-squash path:** once Step 5's squash+push succeeds (including via the sub-step 1a rebase-retry — see Card 1), Step 8 runs immediately — before Steps 5.5, 6, and 7 — since none of those three steps touch the locked parent worktree. See "Post-Step-5-success sequencing" at the end of `### 5. Direct squash` and `### 8. Release merge lock`'s own note. This reordering does not affect the `merged` PR-state route (`## Entry`), which already skips Steps 1/2 (never acquires the lock) and documents Step 8 there as a no-op.

> **Recovery note:** After teardown completes, the cleanup commit is permanently visible via `git log archive/<slug>`. Operators can inspect (or restore) the task-branch state at any point via `git checkout archive/<slug>`.

### 4. Cleanup commit

On the task branch (current cwd), remove the state directory that belongs to the task lifecycle, not to production code.

**Citation scan (non-blocking, #930).** Before removing `<task_dir>`, scan for permanent-doc citations of `_mill/discussion.md` that this deletion is about to invalidate. A citation can live in either the worktree's own tracked tree or the wiki, so this is two separate greps, both read-only and neither one halts this step under any outcome:

```bash
git -C <worktree> grep -InE '\]\([./]*_mill/discussion\.md\)' -- . \
    ':!<task_dir>' ':!plugins/**/SKILL.md' ':!plugins/**/unit_tests/**' ':!plugins/**/integration_tests/**'
```

```bash
git -C <wiki_path> grep -InE '\]\([./]*_mill/discussion\.md\)' -- .
```

`git grep` exits 1 with empty stdout when nothing matches — that is the expected common case, not an error. If either part produces any output (non-zero line count), print a warning to the operator (ASCII-only) listing the citing files/wiki pages: unlike `mill-finalize`'s Step 3 (which has a restore branch for stacked branches), `mill-merge`'s Step 4 always deletes `<task_dir>` outright — so the warning always says the link "is about to go dead", never the "silently repoints" variant. This scan never halts this step — it only warns.

```bash
git -C <worktree> rm -r <task_dir>
git commit -m "chore: pre-merge cleanup"
```

**Why:** squashing a branch that already has cleanup as its tip means the squash commit on the parent never includes transient task metadata.
The cleanup commit is itself preserved under the archive tag created in Step 6.

**Idempotency:** if `<task_dir>` is already absent (re-run after partial failure), `git rm -r` will warn "did not match any files" — treat as a no-op.
If the resulting working tree has nothing to commit, skip the commit.

### 5. Direct squash

PR dispatch lives in mill-finalize.
This step is direct path only.

- **Direct path:**

  Compute a repo-relative pathspec once, before this bash block, and reuse it for the two middle commands:

  ```python
  TASK_DIR_REL = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md']).parent.relative_to(worktree_root).as_posix()
  ```

  **Pre-squash dirty-parent-worktree check (`mode == 'worktree'` only):** before running the bash block below, run `git -C <parent-path> status --porcelain --untracked-files=no` and inspect its output.
  This check applies only when `mode == 'worktree'` (the `mode` variable bound at Entry Step 1) — skip it entirely when `mode == 'inplace'`, matching the existing in-place bypass documented at line 33 (Step 5 already omits `-C <parent-path>` in that mode, so there is no separate parent worktree to check).

  If the output is non-empty, halt Step 5 — do NOT run `merge --squash` — and report to the operator:

  > "The parent worktree is not clean — either (a) this is independent uncommitted work in the parent worktree: commit or stash it, then re-run `/mill-merge`; or (b) this is a partially-applied squash left over from a Step 5 that failed after `merge --squash`/`reset`/`checkout` already staged changes but before `commit` landed: run `git -C <parent-path> commit` to complete it, or `git -C <parent-path> reset --hard` to discard it, then re-run."

  **Rollback exemption:** this halt is exempt from `## Rollback (Steps 1-5 only)` below — see that section's "Dirty-parent-worktree halt and parent-fast-forward-failure halt (Step 5)" carve-out.
  Nothing has been mutated yet at this halt point, so there is nothing to roll back.

  **Pre-squash parent fast-forward (`mode == 'worktree'` only):** immediately after the dirty-parent-worktree check above confirms the parent worktree is clean, fast-forward the parent worktree's local branch to `origin/<parent_branch>`:

  ```bash
  git -C <parent-path> fetch origin "<parent_branch>"
  git -C <parent-path> merge --ff-only "origin/<parent_branch>"
  ```

  This step also applies only when `mode == 'worktree'` — skip it entirely in in-place mode, same gate as the dirty-parent-worktree check immediately above it.

  **Why:** `mill-merge-in` only advances the *child* branch to `origin/<parent_branch>`; it never touches the parent worktree's own local ref. Whenever `origin/<parent_branch>` has moved since the parent worktree last synced (a race, not specifically "non-linear history" — a plain fast-forward advance on origin triggers it just as easily as a merge commit), Step 5's squash-then-push below would otherwise run against a stale parent ref and get rejected as a non-fast-forward push.

  **Not a conflict with the `merged` PR-state route's own "do not ff-sync" note:** the `### PR-state gate`'s `merged` route (`## Entry`) documents that the local parent branch is intentionally NOT fast-forwarded there, and says not to add a parent ff-sync step. That note is about the `merged` route specifically, which skips Step 5 entirely (it only runs Steps 4, 5.5, 6, 7, 8, 9). This card's fast-forward step lives inside `### 5. Direct squash` itself, which the `merged` route never reaches — so the two notes describe disjoint code paths, not a contradiction.

  `merge --ff-only` fails only when the parent worktree's local branch and `origin/<parent_branch>` have genuinely diverged — the parent has local commits not present on `origin/<parent_branch>` AND `origin/<parent_branch>` has independently advanced past the parent's own last-synced point (neither ref is a fast-forward of the other). A parent with local-only commits whose `origin/<parent_branch>` has NOT independently moved is not a failure case — `--ff-only` reports "Already up to date" and exits 0 in that case, since a fast-forward trivially exists. If `merge --ff-only` fails (a genuine two-sided divergence — an out-of-band state this task does not otherwise expect), halt Step 5 — do NOT run `merge --squash` below — and report to the operator:

  > "The parent worktree's local branch has diverged from `origin/<parent_branch>` — it has local commits not present on the remote. Reconcile manually (commit/push, or investigate the divergence), then re-run `/mill-merge`."

  **Rollback exemption:** this halt is exempt from `## Rollback (Steps 1-5 only)` below, for the same reason as the dirty-parent-worktree halt immediately above it — nothing has been mutated at this halt point. See that section's "Dirty-parent-worktree halt and parent-fast-forward-failure halt (Step 5)" paragraph, which covers both halts.

  `reset --hard origin/<parent_branch>` is deliberately never used as the fast-forward mechanism here — it would silently discard any local-only commits on the parent worktree's branch, exactly the class of silent parent-state destruction the sibling rollback-target fix (Card 4) treats as a bug. `merge --ff-only` fails loudly instead.

  ```bash
  git -C <parent-path> merge --squash "$CHILD_BRANCH"
  git -C <parent-path> reset -q HEAD -- "$TASK_DIR_REL"
  git -C <parent-path> checkout -- "$TASK_DIR_REL" 2>/dev/null || true
  git -C <parent-path> commit -m "<cached_task>"
  git -C <parent-path> push
  ```

  Note: these two commands specifically require the relative form, because they run with `-C <parent-path>` and a relative pathspec resolves against that `-C` target -- the absolute, child-anchored `<task_dir>` value is never inside the parent's repo root when parent and child are separate worktree directories, and would resolve outside the parent's repo root and fail with "outside repository" (the exact #648 symptom). `$TASK_DIR_REL` is derived once and reused for both commands for this reason.
  Every other reference to `<task_dir>` in this skill (e.g. Step 4's `git -C <worktree> rm -r <task_dir>`, run against the child worktree) is unaffected and keeps its existing absolute form -- that one already resolves correctly within the child's own repo root.

  **Why:** The child cleanup commit deletes `task_dir`, so a parent that independently tracks `task_dir/_mill/status.md` at the same relative path would otherwise have its file deleted by the squash diff (the #497 bug-2 corruption). The restore step unstages and restores the parent's own `task_dir` from its pre-squash HEAD, using the `$TASK_DIR_REL` relative pathspec so the restore resolves inside the parent's own repo root rather than the child's, ensuring the squash only stages the intended production files. When the parent tracks nothing at `task_dir`, a bare `git checkout -- <pathspec>` against a pathspec absent from `HEAD`'s tree is not a no-op — it exits 1 with `error: pathspec '...' did not match any file(s) known to git`. The `2>/dev/null || true` guard swallows exactly that narrow, expected failure mode, matching the swallow-idiom already used in `mill-merge-in/SKILL.md:37`.

  After the restore, re-inspect the staged changes via `git -C <parent-path> diff --cached --stat` and proceed to commit only the intended production files.

  **On push failure — branch-protection fallback:**

  Capture the combined stdout+stderr of the `git push` command.
  If the exit code is non-zero:

  1. Check the captured output for any of these substrings: `Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006`.
     If a match is found, skip to sub-step 2 (branch-protection rejection) below.
     If none match, continue to sub-step 1a.

  1a. Check the captured output for `! [rejected]` together with either `(fetch first)` or `(non-fast-forward)` — git's own literal rejection markers for a plain non-fast-forward push rejection (distinct from the branch-protection substrings in sub-step 1 above, and from any other failure such as auth or network errors).

      If both markers are present:

      ```bash
      git -C <parent-path> fetch origin "<parent_branch>"
      git -C <parent-path> rebase "origin/<parent_branch>"
      ```

      On a rebase conflict (non-zero exit from `git rebase`): capture the conflicting files via `git -C <parent-path> diff --name-only --diff-filter=U`, then run `git -C <parent-path> rebase --abort`, then fail the step and trigger the Step 1–5 rollback, naming the conflicting files in the operator-facing report.

      On a clean rebase (exit 0): retry the push once —

      ```bash
      git -C <parent-path> push
      ```

      If this retry succeeds (exit 0): the parent now has the squash commit rebased onto the current `origin/<parent_branch>` tip — treat this exactly as if the original push above had succeeded, and continue from the "Post-Step-5-success sequencing" paragraph at the end of this `### 5. Direct squash` section.
      If this retry also fails: fail the step and trigger the Step 1–5 rollback.

      If neither marker is present (this is not a plain non-fast-forward rejection — e.g. an auth or network failure): fail the step and trigger the Step 1–5 rollback (do not attempt any fallback) — this is the unchanged "no match" behavior for any failure that is neither branch-protection nor a plain non-fast-forward rejection.

  2. If a match is found in sub-step 1 — branch-protection rejection — undo the local squash commit on the parent:

     ```bash
     git -C <parent-path> reset --hard origin/<parent_branch>
     ```

  3. Check whether a PR already exists for the child branch (handles re-runs after partial failure):

     ```bash
     gh pr list --head "$CHILD_BRANCH" --state open --json number,url --jq '.[0]'
     ```

     If a PR exists, capture its `url` field and skip to sub-step 5 (push child branch).

  4. If no open PR exists, create one.
     Use `<parent_branch>` (not `<base-branch>`) as the `--base` target — in the fallback the two values may differ (e.g., parent is `develop`, base is `main`):

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

  6. Flip Home.md to `[pr-pending]`:

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     from pathlib import Path; import _paths
     from wiki import _client
     wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
     _client.set_phase(wiki_path, '<slug>', 'pr-pending')
     "
     ```

     This wiki call is the sole durable record of the `pr-pending` transition for this fallback path — `status_path` no longer exists at this point (Step 4's own cleanup commit, which runs earlier in this same invocation, already removed it), so there is nothing left in `_mill/status.md` to append a phase to; this matches the wiki-fallback convention this file's own Entry Step 5 phase gate already documents for when `status_path` is absent.

  7. Report to the user:

     ```
     Direct push rejected by branch protection — switched to PR path. PR: <url>. Consider setting `git.require_pr_to_base: true` in mill-config.yaml.
     ```

  8. Skip to Step 8 (Release lock).
     Do not run Steps 6 (archive tag) or 7 (Home.md flip).
     Re-run `/mill-merge` after the PR lands to complete teardown.

  **Idempotency check:** if `git merge --squash` prints "Already up to date" or `git commit` prints "nothing to commit" → skip `push` and proceed to Step 6.

  **Post-Step-5-success sequencing:** whenever Step 5 succeeds — either via the original `git -C <parent-path> push` above, or via sub-step 1a's rebase-retry push under "On push failure — branch-protection fallback" — run Step 8 (release merge lock) immediately next, before proceeding to Step 5.5. This applies to the direct-squash path only (this section); it does not apply to the `merged` PR-state route, which never reaches this section and has its own unaffected Step 8 no-op note in `## Entry`.

### 5.5. Preflight check for cache helpers

Before attempting Step 6's archive-tag import, verify that the plugin cache is complete.
Run:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
from pathlib import Path
import _preflight
exit(_preflight.check_helpers(['_archive_tag']))
"
```

If the check returns non-zero (helper missing), the error message to stderr names the missing module(s) and instructs the operator to refresh the plugin cache.
The operator must reinstall/update the cache and re-run `/mill-merge`.

**Rationale:** a stale plugin cache (missing `_archive_tag.py`) would otherwise crash at Step 6 with a cryptic `ModuleNotFoundError`.
Catching it early provides an actionable message.

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
if result.get('push_failed'):
    print(f'[mill-merge] WARNING: archive tag push failed -- reconcile {result[\"tag\"]} with remote manually: {result.get(\"push_error\")}')
"
```

Idempotently tags the cleanup-commit tip of the task branch.
The helper handles the three conflict cases — same-SHA no-op, ancestor force-update, divergent move-aside — so re-running `/mill-merge` after a partial teardown never fails at this step.
See `_archive_tag.py` for the resolution logic.

### 7. Home.md — mark [done]

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
from pathlib import Path; import _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
_client.set_phase(wiki_path, '<slug>', 'done')
"
```

**Failure handling after the squash landed on parent:** do NOT roll back the merge.
The merge lock was already released by Step 8's early execution (see "Post-Step-5-success sequencing" at the end of `### 5. Direct squash`), so there is nothing left to release here.
Report the error, tell the user "Merge landed on <parent> but <step> failed: <err>.
Re-run `/mill-merge` to retry — Step 5's idempotency check will skip the squash."
This is the non-destructive boundary: once the parent has the squash, it stays.

### 8. Release merge lock

Delete `<parent-path>/.scratch/merge.lock`.
Run this in a `finally:` equivalent so the lock is released on every exit path.

**Execution point on the direct-squash path:** this step runs immediately after Step 5 succeeds (see "Post-Step-5-success sequencing" at the end of `### 5. Direct squash`), before Steps 5.5, 6, and 7 — not at the end of the Teardown sequence as its position in this document might otherwise suggest. On any of the pre-squash halts in Step 5 (dirty-parent-worktree, parent-fast-forward-failure) or a Step 1–5 rollback, this step still runs at its normal point in the Rollback/halt flow, unchanged.

**In-place mode:** no merge lock was acquired (Entry Steps 1 and 2 were skipped).
Skip lock release.

### 9. Notify + report

`_notify.notify("mill-merge.done", f"task {slug} merged into {parent_branch}", slug=slug, parent=parent_branch)`.

Report to the user:

> "Merge complete for `<slug>`. Worktree intact — run `/mill-cleanup --apply` to remove worktree, branch, portal, and legacy wiki active-dir. Archive tag `archive/<slug>` created. Home.md updated to `[done]`."

**Verify after teardown:** confirm `git tag -l archive/<slug>` returns the tag, and `Home.md` shows `[done]` for `<slug>`.

**No self-report from this skill.**
Reflection is the orchestrator's job — `mill-go` fires `/mill-self-report --auto` at its Handoff (step 6) when `pipeline.auto_report: true`. mill-merge is too narrow in scope to host its own reflection pass;
if it is invoked from a separate thread (i.e. not chained from mill-go's auto_merge path), the user can run `/mill-self-report` manually if reflection is wanted.

## PR-path re-entry

PR-path re-entry for both `done` and `pr-pending` phases is now handled by the `### PR-state gate` in `## Entry`.
All merged/open/closed/none routing is defined there.

## Rollback (Steps 1–5 only)

Any failure between lock acquisition (Step 1) and the squash landing on parent (Step 5) rolls back the parent worktree to `origin/<parent_branch>`:

```bash
git -C <parent-path> reset --hard origin/<parent_branch>
```

Release the merge lock.
Preserve the checkpoint branch.
Report the failure with the step name.

**Why `origin/<parent_branch>`, not the checkpoint:** `mill-checkpoint-<name>` is created in the *child* worktree by `mill-merge-in` and points at the child's own pre-merge-in history — resetting the parent worktree to it checks the parent out to unrelated child commits, regardless of which Steps 1-5 failure triggered the rollback. `origin/<parent_branch>` is the correct rollback target for the parent worktree in every case.

**Cleanup-commit rollback (Step 4):** if the cleanup commit fails mid-way (e.g. `git rm` succeeded but `git commit` failed), reset the task branch:

```bash
git reset --hard HEAD
```

**Dirty-parent-worktree halt and parent-fast-forward-failure halt (Step 5):** the pre-squash dirty-parent-worktree check and the pre-squash parent-fast-forward check (both `mode == 'worktree'` only) that halt Step 5 before `merge --squash` runs are exempt from this rollback — no reset applies, and there is no `git reset --hard` at all.
Nothing has been mutated yet at either halt point: running `git -C <parent-path> reset --hard origin/<parent_branch>` there would destroy exactly the independent uncommitted (or unpushed local-commit) parent-worktree work each halt message tells the operator to reconcile manually.

Post-Step-5 failures (archive tag, Home.md, sidebar) are **not** rolled back — the merge on parent is production state and un-doing it would waste the squash that the PR or direct merge already committed to origin.

## Board discipline

- Wiki mutations go through `_client` calls (`set_phase`, `upsert_task`, `merge_tasks`);
  the daemon serializes all writes and pushes automatically.
  For multi-step atomic operations use `_client.merge_tasks`.
- Task state (status file, discussion file, plan dir, reviews dir) lives in the task directory (`_mill/` for current worktrees, `task/` for legacy) on the task branch — never in the wiki.
  The cleanup commit removes the entire `task_dir` directory from the branch tip before squash.
- Phase transitions via `_status.append_phase`;
  hand-editing `_mill/status.md` is banned.
- Merge-lock file lives at `<parent-path>/.scratch/merge.lock`.
  Never placed anywhere else — other skills expect it there.
