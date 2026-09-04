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
- **Requirements:** Immediately before the two branches of `### Step 3: Cleanup commit (issue #268)` run (the `base_tracks_task_dir` True branch's `git -C <worktree> rm -r --ignore-unmatch <task_dir>` / `git -C <worktree> checkout <parent_branch> -- <task_dir>` pair, and the False branch's `git -C <worktree> rm -r <task_dir>`), add a non-blocking scan step with two parts, since a citation can live in either place, each given as a literal fenced bash block matching the rest of this file's established bash-block convention (Step 3's and Step 4's own git invocations). Part 1 — grep the git-tracked worktree tree, excluding `<task_dir>` itself and excluding `plugins/**/SKILL.md`, `plugins/**/unit_tests/**`, and `plugins/**/integration_tests/**` (the tooling's own self-referential mentions of the `_mill/discussion.md` convention — not citations of any real task's discussion file), for the markdown-link-context pattern rather than a bare literal-string match (a bare-string scan matches this repo's own tooling docs and would produce a false-positive warning on effectively every run; the link-context pattern targets in-repo permanent docs, e.g. a project backlog or module doc tracked in this same git repo):

  ```bash
  git -C <worktree> grep -InE '\]\([./]*_mill/discussion\.md\)' -- . \
      ':!<task_dir>' ':!plugins/**/SKILL.md' ':!plugins/**/unit_tests/**' ':!plugins/**/integration_tests/**'
  ```

  Part 2 — separately grep the resolved wiki path (`wiki_path`, already bound at this skill's own Entry step 1 via `_paths.resolve_wiki_path(git_root)`) for the same markdown-link-context pattern:

  ```bash
  git -C <wiki_path> grep -InE '\]\([./]*_mill/discussion\.md\)' -- .
  ```

  This covers the wiki-board case the `930-scan-and-document-discussion-citations` Shared Decision was originally framed around (a Done/roadmap entry in the wiki's `Home.md`), which Part 1 alone cannot reach: per this repo's own architecture (`CLAUDE.md`: "Wiki holds only `Home.md`," a sibling clone resolved via `_paths.resolve_wiki_path`, never part of `<worktree>`'s own git repository), `git -C <worktree> grep` structurally cannot see wiki content, so a wiki-path grep is a distinct, necessary second check, not an alternative phrasing of Part 1. This wiki-path grep is read-only (`git -C <wiki_path> grep` reads the wiki's own checkout, no mutation) — it does not go through `_wiki.wiki_lock` or `_client`, since it performs no write. If either part finds hits (non-zero line count on stdout; `git grep` exits 1 with empty output on no match, which is the expected common case, not an error), print a warning to the operator (ASCII-only) listing the citing files/wiki pages and stating the link is about to go dead because `<task_dir>` is being removed or restored-from-base. State explicitly in the new text that this scan never halts Step 3 under any outcome, matching Step 3's existing idempotency framing for the rm-path and restore-path branches.
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
