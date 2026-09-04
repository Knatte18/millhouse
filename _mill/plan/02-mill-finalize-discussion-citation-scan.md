# Batch: mill-finalize-discussion-citation-scan

```yaml
task: "mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs"
batch: "mill-finalize-discussion-citation-scan"
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fixes #930: `mill-finalize`'s pre-merge `_mill/` cleanup silently breaks any permanent-doc citation of `_mill/discussion.md` (e.g. a roadmap/Done entry), with nothing in the verify chain catching it. Two cards, both required per `_mill/discussion.md`'s Decision: a non-blocking scan-and-warn in `mill-finalize` Step 3 (catches citations that already exist) and a doc note in `CLAUDE.md` (prevents new ones from being written). No dependency on batch 1 or batch 3 — different files, independent root batch. `verify: null` per the overview's "SKILL.md procedure edits carry `verify: null`" Shared Decision.

## Cards

### Card 5: mill-finalize Step 3 — scan for surviving _mill/discussion.md citations before cleanup

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Immediately before the two branches of `### Step 3: Cleanup commit (issue #268)` run (the `base_tracks_task_dir` True branch's `git -C <worktree> rm -r --ignore-unmatch <task_dir>` / `git -C <worktree> checkout <parent_branch> -- <task_dir>` pair, and the False branch's `git -C <worktree> rm -r <task_dir>`), add a non-blocking scan step. Grep the git-tracked tree (e.g. `git -C <worktree> grep`), excluding `<task_dir>` itself and excluding `plugins/**/SKILL.md`, `plugins/**/unit_tests/**`, and `plugins/**/integration_tests/**` (the tooling's own self-referential mentions of the `_mill/discussion.md` convention — not citations of any real task's discussion file), for the markdown-link-context pattern — a markdown link target ending in `_mill/discussion.md`, e.g. `[...](../_mill/discussion.md)` — rather than a bare literal-string match (a bare-string scan matches this repo's own tooling docs and would produce a false-positive warning on effectively every run; the link-context pattern targets what #930's actual repro looked like: a roadmap/Done-entry doc with a real markdown link). If any hits are found, print a warning to the operator (ASCII-only) listing the citing files and stating the link is about to go dead because `<task_dir>` is being removed or restored-from-base. State explicitly in the new text that this scan never halts Step 3 under any outcome, matching Step 3's existing idempotency framing for the rm-path and restore-path branches.
- **Commit:** `feat(mill-finalize): warn on surviving _mill/discussion.md citations before cleanup (#930)`

### Card 6: CLAUDE.md — document that citing _mill/discussion.md from a permanent doc is unsafe

- **Context:** none
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `## Hard constraints`, immediately after the existing bullet "**Working state never goes to wiki.** `_mill/` lives on the task branch. Wiki holds only `Home.md`.", add a new bullet stating that citing `_mill/discussion.md` (or any other `_mill/`-rooted path) from a permanent/roadmap doc (e.g. a wiki Done entry or module doc) is unsafe, because `_mill/` is deleted or restored-from-base at merge time (`mill-finalize` Step 3 / `mill-merge` Step 4's cleanup commit) and the file no longer exists on the parent branch once the task merges.
- **Commit:** `docs(CLAUDE.md): warn against citing _mill/discussion.md from permanent docs (#930)`

## Batch Tests

`verify: null`. Both cards are pure doc/SKILL.md-procedure edits — no executable surface. Verification is re-reading the rendered `mill-finalize/SKILL.md` Step 3 section and the new `CLAUDE.md` bullet for internal consistency and correct placement, matching the discussion.md Testing section's stated approach for this bug.
