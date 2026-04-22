# mill-merge + mill-merge-in (skills)

```yaml
type: skills (2)
layer: 03
v1_ref: plugins/mill/skills/mill-merge/ + plugins/mill/skills/mill-merge-in/
status: done — merged to main 2026-04-22 (branch impl/06-mill-merge)
note: "Both skills carry over from v1 almost verbatim. Only v2 platform mismatches need patching (module refs, config paths, junction config, plan frontmatter)."
```

## Implementation notes

Shipped `plugins/mill/skills/mill-merge/SKILL.md` + `plugins/mill/skills/mill-merge-in/SKILL.md`, plus two helpers and one load-bearing bug fix.

**Helpers added:**
- `_parent_branch.py` — `resolve(status_path, *, interactive=True)` reads the `parent:` row from status.md's fenced-yaml block and optionally falls back to a stdin prompt. `interactive=False` is the hook for mill-go's auto-merge path so it can fail fast without blocking.
- `_plan_dag.iter_batch_verifies(plan_dir)` — returns `(batch_name, verify_cmd)` pairs in topological order, skipping batches whose `verify:` is null. This is mill-merge-in's "replay the same tests implementation ran" loop.

**Load-bearing bug fix:** `_junction.remove` was skipping broken Windows junctions because `Path.exists()` returns False once their target is gone. Fixed by switching the early-return guard from `.exists() or .is_symlink()` to `os.path.lexists`. The `.active` junction in a task worktree points into `wiki/active/<slug>/` which mill-merge deletes before the junction-cleanup step; without the fix, `git worktree remove --force` would later crash with exit 255 when it hit the orphan reparse point. Surfaced during the integration test.

**Decisions made during discussion (summary):**
- `done` is the terminal phase for mill-merge entry. No final `complete` phase appended — the `active/<slug>/` dir is deleted moments later anyway.
- `git.require-pr-to-base` is kept in config. PR-path recovery: re-running `/mill-merge` detects `phase: pr-pending`, inspects the PR via `gh pr view`, and resumes cleanup from Step 5 onwards if the PR has landed on origin. No new `--post-pr` flag, no `mill-merge-finalise` skill.
- mill-merge-in's Verify replays each batch's own `verify:` in DAG order (iter_batch_verifies). Not a config command, not just the last batch. If every batch has `verify: null` — nothing runs.
- codeguide-update is invoked as `@codeguide:codeguide-update` (namespace fixed in that branch). Skipped silently when `_codeguide/Overview.md` is absent.
- Windows "directory in use" errors surface a generic "close anything pointing at it and re-run" message. No `handle.exe` hint.
- `plan_start_hash` was aspirational in the original spec; dropped entirely since the one-task-per-worktree rule + builder lock make stale-plan detection moot.
- `git.parent-branch` config override dropped. `status.md parent:` is the single source of truth, with an interactive prompt fallback (and `ParentBranchError` for auto-merge contexts).

**Deliberately not shipped in 06:**
- No v1-style notify entrypoint — v2's `_notify` (shipped in 05) is the API, and mill-merge already calls `_notify.notify("mill-merge.done", ...)` on success.
- No archive-to-`archive/<slug>/` when deleting `active/<slug>/`. Same as v1-out-of-scope — revisit if someone misses the history.
- No `mill-merge-finalise` skill for PR-path recovery. The re-run mechanism is enough until PR-path actually sees production use.

**Files added:** `plugins/mill/skills/mill-merge/SKILL.md`, `plugins/mill/skills/mill-merge-in/SKILL.md`, `plugins/mill/scripts/_parent_branch.py`, `plugins/mill/integration_tests/test-merge.py`. **Modified:** `plugins/mill/scripts/_plan_dag.py` (added `iter_batch_verifies` + `_read_batch_frontmatter`), `plugins/mill/scripts/_junction.py` (broken-junction fix).

## Purpose

- **mill-merge**: finalize a completed task. Run from the child worktree. Sync parent → self (via mill-merge-in), squash-merge self → parent, mark Home.md `[done]`, delete `active/<slug>/`, remove the wiki junction, drop the worktree + branch.
- **mill-merge-in**: sync the parent branch into the current branch. Usable standalone *or* as mill-merge's first step. Creates a rollback checkpoint, resolves merge conflicts with conservative policies, runs verify, optional codeguide-update.

## What carries over from v1 unchanged

- **Cross-worktree invariant**: never `cd <parent-worktree>`. Use `git -C <parent-path>` for every parent-branch operation. (This is the rule that makes the whole flow safe to run from a child worktree.)
- **Merge lock** at `<parent-path>/.millhouse/scratch/merge.lock` with PID + timestamp + branch. Stale after 5 min. Wait up to 5 min for a live holder.
- **Direct squash-merge** as default (`git merge --squash` + single commit). Idempotent if re-run after a partial failure (merge-already-applied is a no-op).
- **PR path (opt-in)**: when `git.require-pr-to-base: true` AND `parent-branch == base-branch`, create a PR via `gh` instead of merging directly. Sets `phase: pr-pending` and stops.
- **Checkpoint + rollback** in mill-merge-in: branch named `mill-checkpoint-<slug>` created before the parent merge; `git reset --hard <checkpoint>` on any failure. Checkpoint is preserved on failure for investigation.
- **Conflict policy in mill-merge-in**:
  - Whitespace/formatting only → accept current branch.
  - Package lock files → accept current branch + regenerate via install command.
  - Build artefacts → accept current branch.
  - Real code conflicts → attempt resolution; never `-X theirs`/`-X ours` on real code.
  - Unresolvable → roll back, escalate.
- **No-op guarantee for mill-merge-in**: if `git log HEAD..<parent>` is empty, exit immediately — no checkpoint, no verify, no codeguide-update. This lets mill-merge call it cheaply as a first step.
- **Cleanup order in mill-merge**: merge lands in parent → Home.md `[active]` → `[done]` → delete `active/<slug>/` on wiki → regenerate sidebar → remove wiki junction from worktree → drop worktree + branch.

## v2 adaptations

Everywhere v1 references will not resolve; swap during full-write:

| v1 reference | v2 equivalent |
|---|---|
| `wiki.sync_pull(cfg)` | `_wiki.sync_pull(<WIKI_PATH>)` (add helper if absent) |
| `paths.slug_from_branch(cfg)` | Read `.millhouse/active.slug.md` (same convention as mill-start/mill-plan/mill-go) |
| `.millhouse/wiki/active/<slug>/...` | `<WIKI_PATH>/active/<slug>/...` — resolve `<WIKI_PATH>` via `_wiki.read_junctions` and `_junction.resolve_target`. Never use the junction path as authoritative. |
| `millpy.core.config.load_merged(...)` | load `<WIKI_PATH>/config.yaml` + `.millhouse/config.local.yaml` (v2 has no flat helper yet — planner for full-write may need one, or inline yaml.safe_load) |
| `status_md.append_phase(...)` | `_status.append_phase(...)` (planned in mill-spawn/mill-start/mill-plan) |
| `tasks_md.parse/render/write_commit_push` | `_tasks_md.*` (planned alongside mill-spawn). For mill-merge this is the `[active]` → `[done]` rewrite. |
| `regenerate_sidebar` via `python -m millpy.entrypoints...` | `_sidebar.regenerate(<WIKI_PATH>)` (already in v2) |
| `millpy.core.junction.remove` + `paths.project_dir()` | `_junction.remove(<junction-path>)` with `<junction-path>` resolved from the wiki's `junctions:` block. Remove every junction the worktree owns (wiki junction, `.active/` junction). |
| Reading verify from `.millhouse/task/plan.md` (v1) | Read `verify:` from `<WIKI_PATH>/active/<slug>/plan/00-overview.md` frontmatter. v2 plans also have per-batch `verify:` — merge-in uses the overview-level one. |
| `millpy.entrypoints.notify` | No v2 equivalent yet. Default to stdout-only reporting in v2.0 (see `05-mill-go-skill.md` open design point on notifications). |

## Decisions (v2-specific)

- **Merge direction and final marker**: `[active]` → `[done]`. v1 had both `[completed]` and `[done]` inconsistently; v2 standardises on `[done]` (matches `05-mill-go-skill.md`).
- **Delete `active/<slug>/` on merge**: yes, same as v1 — the task's record is the squashed commit + the Home.md entry. Keeping stale `active/` directories forever is clutter. Archive-to-`archive/` is NOT in scope for v2.0; revisit if someone misses the history.
- **Junction cleanup**: remove *every* junction the worktree set up (`.millhouse/wiki`, `.active/`, plus any additional junctions configured in `junctions:`). Resolve via the same `_wiki.read_junctions` + `_junction.resolve_target` machinery used at spawn/setup.
- **PR-path status.md**: set `phase: pr-pending` and stop. No direct merge, no Home.md rewrite. The PR-merge machinery is external; mill-merge only initiates. When the PR is eventually merged, the user re-runs mill-merge (or a dedicated `mill-merge-finalise`) to clean up — *spec needed later if this becomes common*.
- **Failure rollback boundary**: any failure after the parent squash-merge lands is NOT rolled back (you don't want to un-do a successful production merge if the Home.md write fails — that's a retry, not a disaster). v1's boundary: rollback via checkpoint applies up to and including the parent merge; after that, partial-success with retry-instruction.

## Flow summary (mill-merge)

1. Entry: verify worktree (not main), read `status.md phase:` — must be `done` (the phase mill-go set).
2. Acquire merge lock on parent.
3. Append `complete` phase to `status.md` (final wiki write — same convention as v1, if we keep the "complete" marker post-`done`; otherwise skip).
4. Invoke **mill-merge-in** (sync parent → self).
5. Squash merge self → parent → push.
6. Home.md `[active]` → `[done]` via wiki-locked write.
7. Delete `<WIKI_PATH>/active/<slug>/` and commit.
8. Regenerate sidebar.
9. Remove all junctions owned by this worktree.
10. Release merge lock.
11. `git worktree remove --force <self>` + `git branch -d <branch>` from parent.
12. Report.

## Flow summary (mill-merge-in, standalone)

1. Entry: read parent branch from `git.parent-branch` config → fall back to `status.md parent:` → ask user.
2. `git log HEAD..<parent>` — if empty, exit (no-op guarantee).
3. Create checkpoint branch.
4. `git merge <parent>` with the conflict policy above.
5. Run verify (from `00-overview.md` frontmatter `verify:`, or skip if `N/A`).
6. Optional codeguide-update scoped to checkpoint diff.
7. Report.

On any failure after step 3: `git reset --hard <checkpoint>`, preserve the checkpoint, escalate to caller/user.

## Backend

**New / to add:**
- `_tasks_md.py` — parse/render Home.md + `[active]` → `[done]` replace. Same helper planned for mill-spawn.
- `_status.py` gains nothing new here; uses `append_phase` and `update_field` already planned.
- `_wiki.sync_pull(wiki_root)` — thin wrapper if we don't already have one. mill-merge's entry needs a clean way to pull the wiki.
- **Parent-branch resolution helper** — read `git.parent-branch` from config, fall back to `status.md parent:`, fall back to ask user. Single function so mill-merge and mill-merge-in share it.

**Reused / already exists:**
- `_wiki.py` — lock, write_commit_push.
- `_sidebar.regenerate` — sidebar refresh.
- `_junction.remove` + `_junction.resolve_target` — junction cleanup.
- `_subprocess_util.run` — all git ops via `git -C <parent-path>`.
- `codeguide-update` skill (when present) — invoked from mill-merge-in step 5 if `_codeguide/Overview.md` exists.

## Out of scope vs v1

- **No `mill-self-report` auto-fire** on merge completion. Can be invoked manually; see `03-mill-start-skill.md` open points on auto-reporting.
- **No notification entrypoint** in v2.0. Merge outcome is stdout + status.md only.
- **No archive-to-`archive/<slug>/`** when deleting `active/<slug>/`. Simplest thing now.

## Open design points

- **`status.md phase:` on merge completion**: does v2 write a final `complete` phase after `done` (v1 did), or is `done` terminal? Simpler to stop at `done` (consistent with Home.md marker). Confirm.
- **`phase: pr-pending` recovery**: when PR is merged externally, how does the user re-enter mill-merge to finish cleanup? A flag like `mill-merge --post-pr` or a separate `mill-merge-finalise`? Defer to usage experience.
- **Verify source for mill-merge-in**: does it use the overview `verify:` or the *most-recent-batch's* `verify:`? Overview is simpler; batch-level only matters if merge-in is run mid-implementation, which shouldn't happen post-`done`.
- **Codeguide-update trigger**: keep v1's "invoke skill if `_codeguide/Overview.md` exists" — confirm this is still the convention in v2.
- **Removed worktree cleanup in corrupted-state cases**: v1 had platform-aware diagnostics (`handle.exe`/`lsof`) when `git worktree remove` failed because the directory was in use. Keep or simplify? v2 lives on Windows primarily; `handle.exe` hint is worth keeping.
