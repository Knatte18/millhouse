# Batch: docs

```yaml
task: "35 (A) — Centralize path resolution across all three modes"
batch: docs
number: 5
cards: 3
verify: null
depends-on: [1]
```

## Batch Scope

Pin the new contract in human-readable form. CLAUDE.md `## Path invariants` gets one paragraph mandating both helpers and banning the inline path constructions they replace. `mill-claim/SKILL.md` gets a short section explicitly documenting in-place semantics (the proposal called this skill "currently confused with mill-spawn"). `mill-spawn/SKILL.md` gets at most a one-liner cross-reference if the worktree-vs-in-place split is not already mentioned.

Pure documentation batch — no code paths exercised, no tests to run. `verify: null`.

Depends on Batch 1 because the docs reference the new helper API (`resolve_active_worktree` new signature, `resolve_active_hub`).

## Cards

### Card 8: CLAUDE.md ## Path invariants — mandate the centralized helpers

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add one new bullet to the `## Path invariants` section of `CLAUDE.md`. Insert it immediately after the existing bullet that begins `**All path resolution goes through `_paths.py`.**` (currently at line 115). The new bullet must be one paragraph, no headings, no worked example.

  Body of the new bullet (verbatim):

  ```markdown
  - **Slug-to-path resolution goes through `resolve_active_worktree` / `resolve_active_hub`.** Any code that needs "the worktree directory for a given slug" calls `_paths.resolve_active_worktree(container, slug, *, cfg, git_root)`. Any code that needs "where `.millhouse/` and `task/` live for a given slug" calls `_paths.resolve_active_hub(container, slug, *, cfg, git_root)`. Both helpers detect in-place mode (hub IS the worktree, no `<container>/wts/<slug>/` directory) and sub-dir hub configs (`hub_relative_path != "."`). Inline `container / "wts" / slug` constructions are banned outside `_paths.py`; inline `<wt> / hub_relative_path` arithmetic is banned outside `_paths.resolve_hub_relative_path`. `discover_active_worktrees`-style enumerations of `<container>/wts/` are exempt — they enumerate, not slug-resolve.
  ```

  Also update the existing `**All path resolution goes through `_paths.py`.**` bullet at line 115. Replace the parenthetical fragment that reads `resolve_active_worktree(container_path, slug) for slug-to-worktree lookup (returns <container>/wts/<slug> after verifying .millhouse/active.slug.md)` with `resolve_active_worktree(container, slug, *, cfg, git_root) for slug-to-worktree lookup; resolve_active_hub(container, slug, *, cfg, git_root) for slug-to-hub lookup (handles in-place mode and sub-dir hub configs)`. The rest of that bullet is unchanged.
- **Commit:** `docs(claude-md): mandate resolve_active_worktree / resolve_active_hub helpers`

### Card 9: mill-claim/SKILL.md — document in-place semantics

- **Context:**
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-claim/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Append a new section to `mill-claim/SKILL.md` after the `## Run it` block. The section explicitly documents the in-place contract.

  New section to append (verbatim):

  ```markdown

  ## In-place mode

  mill-claim does NOT create a `<container>/wts/<slug>/` directory. The current worktree (the hub itself) IS the task worktree for this slug. The task branch is checked out in place; `.millhouse/active.slug.md` is written at the hub.

  Downstream skills (mill-start, mill-plan, mill-go, review scripts) resolve the active worktree via `_paths.resolve_active_worktree(container, slug, *, cfg, git_root)`, which returns the hub path in in-place mode. `task/discussion.md`, `task/plan/`, `task/reviews/`, and `task/status.md` live at `<active_hub>/task/...` — when `hub_relative_path` is set in `.millhouse/config.local.yaml`, that is `<git_root>/<hub_relative_path>/task/...`, NOT `<git_root>/task/...`.

  Use mill-spawn instead when you want a separate worktree directory for the task.
  ```

  Do not modify the existing `## Run it` section or the frontmatter.
- **Commit:** `docs(mill-claim): document in-place semantics and active_hub resolution`

### Card 10: mill-spawn/SKILL.md — one-liner cross-reference to mill-claim

- **Context:**
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/skills/mill-claim/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-spawn/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The current `mill-spawn/SKILL.md` describes the worktree-creation flow but does not contrast with mill-claim's in-place mode. Append a single-line cross-reference at the end of the file, after the existing closing line `Exits 0 (not 1) when the backlog is empty. Prints worktree path, branch, and status path on success. Takes and releases the wiki lock during the claim step.`

  New trailing line (verbatim, with the leading blank line):

  ```markdown

  Use mill-claim instead when you want to claim the task in the current checkout (in-place) without creating a separate worktree directory.
  ```

  No other changes to the file.
- **Commit:** `docs(mill-spawn): cross-reference mill-claim's in-place mode`

## Batch Tests

`verify: null` — pure documentation batch. No runnable surface beyond the markdown files themselves. mill-go's plan-validator does not parse SKILL.md or CLAUDE.md content; the cards are verified by the holistic plan review and the holistic code review at end-of-task.
