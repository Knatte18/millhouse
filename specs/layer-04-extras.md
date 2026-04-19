# Layer 04 — Remaining skills

```yaml
status: draft
depends-on: [layer-01-bootstrap, layer-02-review, layer-03-orchestration]
delivers: [mill-start, mill-plan, mill-merge, mill-cleanup, mill-status, mill-abandon, mill-groom]
loc-budget: 900
```

## Goal

Round out the workflow. Layers 01-03 deliver a working task-execution pipeline. Layer 04 adds the bookend skills (start a task, write a plan for it, merge the result, clean up after).

## Why this is the last layer

If Layers 01-03 ship and work, mill is useful. Layer 04 is polish and ergonomics. Landing it last keeps us honest: if we run out of steam after Layer 03, we have a working product, not a half-built one.

## v1 reuse for this layer

From `C:\Code\millhouse-legacy\plugins\mill\scripts\millpy\`:

| v1 source | v2 target | What to take |
|---|---|---|
| `skills/mill-start/SKILL.md` | `skills/mill-start/SKILL.md` | **Reference** — workflow for discussion-phase interaction. Drop v1's sub-skill references. |
| `skills/mill-plan/SKILL.md` | `skills/mill-plan/SKILL.md` | **Reference** — planner phase. Drop v1's plan-v2/v3 format dispatch. |
| `skills/mill-merge/SKILL.md` | `skills/mill-merge/SKILL.md` | **Reference** — merge flow (switch to main, merge --no-ff, push, update wiki). Lift the git command sequence. |
| `skills/mill-cleanup/SKILL.md` | `skills/mill-cleanup/SKILL.md` | **Reference** — worktree removal + junction teardown. |
| `skills/mill-status/SKILL.md` | `skills/mill-status/SKILL.md` | **Reference** — the table-output format for listing worktrees. |
| `skills/mill-abandon/SKILL.md` | `skills/mill-abandon/SKILL.md` | **Reference** — abandon flow. v2 differs: task returns to Home.md backlog, `active/<slug>/` is deleted (not archived). |
| `templates/status-discussing.md`, `status-abandoned.md` | `templates/status.md` | **Consolidate** — v1 had multiple status-file variants. v2 has ONE status.md; phase is a field, not a file name. |

See `ref-v1-reuse.md` for the full lifting protocol.

## Deliverables

### 1. `mill-start` — discussion phase for a task

**Arguments:**
```
mill-start [<slug>]
```

**Behaviour:**

1. If slug given: move to that worktree. Else: pick from `mill-list` interactively.
2. Spawn Claude in discussion mode: reads task description, explores codebase, produces `discussion.md`
3. Discussion.md is the input to `mill-plan`
4. Uses `providers/claude.py::implement()` (agent writes to worktree) with a discussion brief template
5. Updates status.md: `phase: discussing`

No review by default. If user wants discussion reviewed, they run `mill-review --type discussion --file discussion.md` manually.

### 2. `mill-plan` — produce a plan from discussion

**Arguments:**
```
mill-plan [--max-review-rounds N]
```

**Behaviour:**

1. Read `.millhouse/.active/discussion.md`
2. Spawn Claude in planning mode: produces `plan.md` following `templates/plan.md` schema
3. Validate plan against schema (runs format validator)
4. If `--max-review-rounds > 0`: run `mill-review --type plan`, iterate until APPROVE or rounds exhausted
5. Write final plan to `.millhouse/.active/plan.md`, commit to wiki
6. Update status.md: `phase: planning` → `phase: planned`

Plan format is the one locked in Layer 03 (single flat file, `## Card N:` headings).

### 3. `mill-merge` — merge a completed task

**Arguments:**
```
mill-merge [--no-cleanup]
```

**Behaviour:**

1. Verify current worktree is on a task branch (slug matches `.millhouse/.<slug>.slug.md`)
2. Verify status.md says `phase: done` (or prompt to continue if not)
3. Switch to the primary clone's main branch (not the task worktree)
4. `git merge --no-ff <slug>` with a clean merge commit
5. Push hub's main
6. Update wiki: move `active/<slug>/` to `archive/<slug>/` → `archive/<slug>/`, commit, push
7. Unless `--no-cleanup`: call `mill-cleanup <slug>` to remove worktree

### 4. `mill-cleanup` — remove a worktree

**Arguments:**
```
mill-cleanup <slug>
```

**Behaviour:**

1. From the primary clone: `git worktree remove ../worktrees/<slug>`
2. Delete `.millhouse/.active` junction and `.<slug>.slug.md` in the worktree (already handled by git worktree remove if the worktree is clean)
3. Optionally: prune local branch `<slug>` if merged

### 5. `mill-status` — show current state of all worktrees

**Arguments:** none

**Behaviour:**

1. List all worktrees under `../worktrees/`
2. For each, read `.millhouse/.<slug>.slug.md` + `wiki/active/<slug>/status.md`
3. Print a table:
   ```
   SLUG             BRANCH            PHASE         LAST UPDATE
   fix-foo          fix-foo           implementing  2026-04-19T12:34
   refactor-bar     refactor-bar      planning      2026-04-18T09:15
   ```

### 6. `mill-groom` — backlog management (interactive)

Comprehensive backlog grooming — the skill v1 kept wanting but never properly had. Replaces v1's narrower `mill-revise-tasks`.

**Scope (what the skill proposes to do, subject to user approval per step):**

1. **Import incoming GitHub issues** into `Home.md` as new tasks, with:
   - Slug derivation from issue title or number
   - Duplicate check against existing slugs
   - Preserve issue number as metadata (e.g., `## task-slug (#42)`)
   - Option to close the issue with a "tracked in tasks" comment
2. **Extract long-body tasks** to `wiki/proposals/<slug>.md` (as the old mill-revise-tasks did), leaving a short description + `[Background →]` link
3. **Detect duplicates** — two task entries that are clearly the same concern — propose merging
4. **Flag stale tasks** — entries that haven't been touched in a long time or reference extinct codepaths — propose archiving or deleting
5. **Reformat Home.md** — consistent spacing, alphabetical sort within sections, etc.

**Form: interactive skill.** Not a one-shot script. The user runs `/mill-groom`, Claude walks through each proposed change, user approves/rejects per operation. Low-risk changes (reformatting) can be auto-applied; high-risk (merges, deletions) always ask.

**Helper scripts it uses:**
- `plugins/mill/scripts/_wiki.py` for commits
- `plugins/mill/scripts/fetch-issues.py` (lifted from v1) for GitHub issue fetching
- `plugins/mill/scripts/_render.py` for any template substitution

**Configuration:**

```yaml
# wiki/config.yaml
grooming:
  github-repo: <owner>/<repo>         # where to fetch issues from
  issues-label: task                   # only issues with this label (optional)
  stale-threshold-days: 90             # flag tasks untouched for this long
  long-body-threshold-words: 150       # extract proposals over this size
```

**Why it's broader than v1:** v1 had `mill-revise-tasks` for issue-import only, and format tidying never got properly done. v2 merges both into one skill that owns the whole backlog-hygiene concept.

### 7. `mill-abandon` — mark a task as abandoned

**Arguments:**
```
mill-abandon [<slug>]
```

**Behaviour:**

1. If in a worktree: use that worktree's slug. Else require `<slug>` arg.
2. Prompt for abandon reason (optional note).
3. Re-insert task entry into `wiki/Home.md` (so the task returns to the backlog). Reason note is appended to the task description if provided.
4. Delete `wiki/active/<slug>/` from the working tree.
5. Commit + push the wiki (with lock, since Home.md is shared).
6. Leave the worktree on disk. User runs `mill-cleanup` separately.

**Why delete instead of archive:** abandoning means "changed direction" — the discussion/plan/reviews are not reference material, just a dead end. Wiki git history still has them if anyone wants to look. Keeping the task entry in Home.md lets you (or someone else) pick it up again later without "task is in archive" confusion.

**If you want to preserve the attempt's artefacts:** don't use mill-abandon. Instead, use `mill-merge` on a branch that never actually implements anything substantial (or with `--no-merge` to just archive state without merging to main).

## File layout

```
plugins/mill/
  scripts/
    mill-start.py       ← ~100 LOC
    mill-plan.py        ← ~150 LOC (includes plan validation)
    mill-merge.py       ← ~150 LOC (git ops are the bulk)
    mill-cleanup.py     ← ~60 LOC
    mill-status.py      ← ~100 LOC (parses multiple status files)
    mill-abandon.py     ← ~60 LOC
  providers/
    claude.py           ← adds discuss()/plan() functions or separate brief templates
  templates/
    discussion-brief.md
    planner-brief.md
    merge-commit-message.md
    (schemas)
  skills/
    mill-start/SKILL.md
    mill-plan/SKILL.md
    mill-merge/SKILL.md
    mill-cleanup/SKILL.md
    mill-status/SKILL.md
    mill-abandon/SKILL.md
  integration_tests/
    test-full-lifecycle.ps1  ← spawn → start → plan → go → merge → cleanup
```

## Acceptance criteria

After this layer ships, a user can:

1. `mill-add fix-foo` (Layer 01)
2. `mill-spawn fix-foo` (Layer 03)
3. `cd ../worktrees/fix-foo && mill-start` → gets a discussion.md
4. `mill-plan` → gets a reviewed plan.md
5. `mill-go` → implements the plan, runs code review
6. `mill-merge` → merges to main, moves task to archive in wiki
7. Everything is auditable: status.md, discussion.md, plan.md, reviews/ all present in wiki for history

## Design decisions locked

- **Phase names in status.md:** `discussing`, `planning`, `planned`, `implementing`, `reviewing`, `done`, `abandoned`. Fixed enum, no free-form.
- **Completed tasks move to archive/; abandoned tasks return to Home.md.** Abandoning deletes `active/<slug>/` from the tree (git history preserves it). Archive is for lasting reference material only.
- **Merge is a separate step.** `mill-go` does NOT auto-merge. User decides when to merge.
- **Cleanup is reversible.** Until `mill-cleanup` runs, the worktree is still there and the user can revisit.

## Non-goals for Layer 04

- Merge conflict resolution (let git handle it, user resolves manually)
- Automatic status-file validation on every command (Layer 04+, maybe)
- Cross-task dependencies (no `depends-on` at task level; only within a plan)
- Task archiving / retention policies

## Open questions

- [ ] Where does `archive/<slug>/` live? In the wiki alongside `active/` (as `archive/`), or in a separate repo for history?
- [ ] Does `mill-merge` also update hub's `.millhouse/.active` junction (remove it) after cleanup?
- [ ] Do we keep a `mill-resume` for picking up a worktree on another machine, or is that handled by just cloning the wiki and running `mill-setup`?
