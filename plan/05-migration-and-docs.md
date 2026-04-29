# Batch: migration-and-docs

```yaml
task: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split
batch: migration-and-docs
cards: 2
verify: null
depends-on: [consumers-and-skills]
```

## Batch Scope

This batch ships the one-shot migration tool that moves an existing mill clone from the old `hub/` + `worktrees/` layout to the new `wts/<repo>/` + `wts/<slug>/` + `portals/` layout, plus the CLAUDE.md update that documents the new layout for human readers. The migration script is the operator's tool; it is invoked manually once per clone, halts if any task is in flight, and supports `--dry-run`. CLAUDE.md gets the new layout diagram and updated path-invariants section. Verify is `null` for this batch because the migration script is exercised through manual smoke-tests (see Batch Tests below) and CLAUDE.md is documentation. After this batch lands and the migration runs, the clone's on-disk layout matches the new shape end-to-end and every consumer from batches 02–04 starts working against the new structure.

## Cards

### Card 23: `plugins/mill/scripts/millpy-migrate-layout.py` (new)

- **Reads:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_wiki.py`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/scripts/millpy-migrate-layout.py`
- **Requirements:** New CLI script `millpy-migrate-layout.py`. argparse: `--dry-run` (boolean; print planned operations and exit 0). Module-level docstring describes the operation and references discussion.md `## Decisions → migration-strategy` for the canonical step list. Behaviour: (a) Pre-flight halt — derive `wiki_path` directly as `main_root.parent / "wiki"` where `main_root` is `_paths.resolve_main_worktree_root(Path.cwd())`. Do NOT use `_paths.resolve_wiki_path`: that helper's sibling logic is calibrated for the NEW layout (`parent.name == "wts"` → `parent.parent / "wiki"`) and on the OLD layout (`<container>/hub/`) it falls through to prefix-form, returning `<container>/hub.wiki/` — a non-existent path. The OLD layout's structural invariant is "wiki is a sibling of hub at the container level", which equals `main_root.parent / "wiki"` regardless of whether the main_root dir is named `hub` (old) or `<repo>` (mid-migration). Halt with a clear error if `<wiki_path>/active/` does not exist (suggests already-migrated or unset clone). For each `<wiki_path>/active/<slug>/` directory, parse `status.md` and read `phase:`. If any phase is not in `{done, abandoned}`, halt with a list of in-flight slugs and a message instructing the user to merge or abandon them first. (b) Operations log — `Path(".scratch").mkdir(exist_ok=True)` (the `.scratch/` dir does not exist in a fresh checkout), then open `.scratch/migrate-<utc-compact-timestamp>.log` for write; every shell command and file operation is also echoed to stderr in `--dry-run`. (c) Step 1 — `mkdir <container>/wts` (idempotent: skip if exists). (d) Step 2 — for each existing child worktree under `<container>/worktrees/<slug>`, run `git -C <hub> worktree move <container>/worktrees/<slug> <container>/wts/<slug>`. The hub path is `<container>/hub` at this point (pre-rename). Use `_subprocess_util.run` and surface stderr on non-zero exit. (e) Step 3 — main worktree move: detect repo name from `git -C <container>/hub remote get-url origin` (last path segment, strip `.git`). `mv <container>/hub <container>/wts/<repo>` via `shutil.move`. Then `git -C <container>/wts/<repo> worktree repair` to fix child `.git` file references. (f) Step 4 — remove now-empty `<container>/worktrees/` via `rmdir` (fail loudly if not empty — that means a worktree-move failed silently). (g) Step 5 — `mkdir <container>/portals` (idempotent: skip if exists, matching Step 1's discipline so a re-run after partial failure does not crash); for each subdirectory of `<container>/wts/`, prepare to create `<container>/portals/<dirname>` junction → `<container>/wts/<dirname>`. `_junction.create` raises `ValueError` for ANY existing `link_path` (not only mismatched-target ones — see `_junction.py:create`'s `if link_path.exists() or link_path.is_symlink()` guard), so a naive re-run after partial failure crashes on already-correct entries. Implement explicit pre-check per entry: if the link path does not exist (broken/missing junctions count as "not exists" via `os.path.lexists`), call `_junction.create`; if it exists and resolves to the desired target, skip silently and log "portal already correct"; if it exists and resolves elsewhere, halt with a clear error naming the existing target and instructing the operator to remove the wrong junction manually before re-running. Use `os.path.lexists` plus `Path.resolve()` for the check; matches the same pattern `millpy-claim.py` uses for portal handling per Card 9. (h) Step 6 — print a banner instructing the operator to `cd <container>/wts/<repo>` and run `/mill-setup` (the skill, NOT a Python invocation here — mill-setup is a slash command). The migration script does NOT auto-run mill-setup; the operator does. The banner explicitly states this is the intended invocation order per discussion.md operator constraint. `--dry-run` prints the planned operations with absolute paths but performs no filesystem writes (no `mkdir`, no `worktree move`, no junction creation). Exit codes: 0 on success or successful dry-run; 1 on pre-flight halt or any subprocess failure. The script lives under `plugins/mill/scripts/` and follows the `millpy-*` naming convention; it is NOT registered in `_shortcuts.SHORTCUT_SCRIPTS` because it is run manually outside the normal mill workflow. No automated unit test — the discussion notes this as manual-verify-only.
- **Commit:** `feat(migrate): one-shot millpy-migrate-layout.py for old → new layout`

### Card 24: `CLAUDE.md` layout diagram + path-invariants update

- **Reads:**
  - `CLAUDE.md`
  - `wiki/active/container-restructure/discussion.md`
- **Modifies:**
  - `CLAUDE.md`
- **Creates:** none
- **Requirements:** Update the `## Project shape` paragraph (or equivalent) to describe the new layout: `<container>/wts/<repo>/` for the main worktree, `<container>/wts/<slug>/` for task worktrees, `<container>/portals/` for cross-worktree junctions, `<container>/wiki/` for the wiki clone, `<container>/codeguide/` for codeguide. Add a fenced ```text block with the following inline diagram (do NOT cite a `## Target layout` section — discussion.md has no such heading; this is the canonical diagram for CLAUDE.md, sourced from `wiki/proposal-container-restructure.md`):

  ```text
  c:/Code/millhouse/                ← container, named after the repo
    wts/                            ← all worktrees
      millhouse/                    ← main worktree, named after repo
      <slug>/                       ← task worktrees, named after slug
    wiki/                           ← wiki clone
    codeguide/                      ← codeguide clone
    portals/                        ← junctions to all task worktrees
      millhouse -> ../wts/millhouse
      <slug>    -> ../wts/<slug>
  ```

  Inside each worktree:

  ```text
  c:/Code/millhouse/wts/<slug>/
    plugins/                        ← (only meaningful in main worktree)
    ... (rest of repo files)
    .millhouse/
      active.slug.md
      config.local.yaml
    .others -> ../../portals/       ← single junction to portals dir
    .active -> ../../portals/<slug>/← resolves through portals to the task worktree
    reviews/                        ← per-task working state, on the branch
    discussion.md
    plan/
    status.md
  ``` Update the `## Path invariants` section to reference the new helpers: `_paths.resolve_hub_relative_path(worktree_root, hub_subpath)` for cwd-as-hub resolution, `_paths.resolve_active_worktree(container_path, slug)` for slug-to-worktree lookup, and the new `_sibling.resolve_path` rule (`parent.name == "wts"` → container-form). Drop or rewrite any prose that references `<container>/hub/` or `<container>/worktrees/`. Add a callout that the working state (`status.md`, `discussion.md`, `plan/`, `reviews/`) lives at the worktree root and is tracked on the task branch — same as the discussion's state-files-location decision but in CLAUDE.md's voice. The "Repo layout pointers" subsection updates the line referencing `worktrees_dir` to mention `wts/`. The `_legacy/` and `.scratch/` notes are unchanged. Markdown style follows existing CLAUDE.md (no fenced ```yaml here — CLAUDE.md uses fenced ```yaml only for the very-top metadata block, which doesn't change).
- **Commit:** `docs(CLAUDE): document new container layout + path invariants`

## Batch Tests

`verify: null` — no automated tests for this batch. Manual verification steps:

1. **Migration dry-run on the live clone.** From the hub (or wherever cwd allows), run `python plugins/mill/scripts/millpy-migrate-layout.py --dry-run` and read the printed plan. Confirm: every active worktree under `<container>/worktrees/<slug>` is listed; the main-worktree move (`hub` → `wts/<repo>`) is listed; the portal entries are listed for every worktree.
2. **Migration smoke-test on a `.scratch/` clone.** Copy the entire `<container>/` (hub + wiki + worktrees) to `.scratch/migrate-test/` (or use a fresh clone of the millhouse repo plus a synthesized child worktree). Run the migration without `--dry-run`. Verify the on-disk layout matches the target diagram. Re-run `mill-setup` from the new `wts/<repo>/` and confirm `_setup.create_hub_links` produces the expected junctions and hardlinks.
3. **Live migration.** Once cards 22 and 23 land and the operator has merged or abandoned all in-flight tasks (including this one), run the migration on the real clone. Verify: `mill-status` from the new hub reports the expected backlog; `mill-spawn` on a throwaway slug produces a worktree under `<container>/wts/`; `mill-merge` on that throwaway slug runs through the new teardown sequence cleanly.
4. **CLAUDE.md review.** Re-read the file end-to-end after Card 23. Confirm no stale references to `<container>/hub/` or `<container>/worktrees/` remain. Confirm the new diagram is consistent with discussion.md's target layout.

The migration script is intentionally manual — it operates on hub-level state that is hard to fixture and hard to roll back. Treating it as a one-shot operator-driven tool with a `--dry-run` preview matches discussion.md `## Decisions → migration-strategy`.
