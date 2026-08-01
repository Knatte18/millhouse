# Batch: mill-merge-self-resolve

```yaml
task: 'Non-interactive pipeline: only mill-start''s interview may prompt the operator'
batch: mill-merge-self-resolve
number: 5
cards: 2
verify: null
depends-on: []
```

## Batch Scope

`mill-merge/SKILL.md`'s `## Entry` has two operator-facing prompts unrelated to `pipeline.autonomous_mode` (mill-merge doesn't read that key): the stale-worktree ambiguity (Step 1, a raw `input()` call via `_inplace.prompt_stale_worktree`) and the parent-branch resolution call site (Step 4, an undefined `interactive=<True unless called non-interactively>` placeholder). Both get fixed independently — the stale-worktree case becomes agent-driven git-state investigation instead of a blocking prompt; the parent-branch case becomes a hardcoded `interactive=False` matching mill-finalize's existing call, with the resulting `ParentBranchError` converted to a clean `_status.set_blocked` halt. Neither `_inplace.py` nor `_parent_branch.py` needs a Python change — `_parent_branch.resolve` already supports `interactive=False` (mill-finalize already calls it that way); `_inplace.prompt_stale_worktree` is simply no longer called from the new call site (out of scope to delete per discussion — no other caller was confirmed absent-of-need). Both cards edit `## Entry` in the same file; ordered sequentially since they are two edits to the same section (Step 1 then Step 4) with no anchor overlap.

## Cards

### Card 10: Replace mill-merge's stale-worktree prompt with agent-driven investigation

- **Context:**
  - `plugins/mill/scripts/_inplace.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `## Entry`, Step 1, the "Stale-worktree edge" paragraph currently reads exactly:

```
   Stale-worktree edge: if `active_data` is not None AND the corresponding `<worktrees-dir>/<slug>/` directory exists AND the branch matches, call `_inplace.prompt_stale_worktree(slug, worktree_path)` and override `mode` based on the user's choice (`"inplace"` → `mode = 'inplace'`; `"worktree"` → `mode = 'worktree'`; `"abort"` → halt).
```

  Replace it with:

```
   Stale-worktree edge: if `active_data` is not None AND the corresponding `<worktrees-dir>/<slug>/` directory exists AND the branch matches, investigate the ambiguity directly instead of prompting: run `git worktree list --porcelain` and inspect the entry for `<worktrees-dir>/<slug>/`. If that entry is absent from the output, or its recorded branch no longer matches the active task branch (a stale registration), treat the directory as in-place cruft: `mode = 'inplace'`. If the entry is present, current, and its branch matches the active task branch, treat it as a genuine live worktree: `mode = 'worktree'`. Either way, `_status.append_phase(status_path, f"self-resolved-stale-worktree-{mode}", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-merge: self-resolved stale-worktree ambiguity ({mode})"` and push before continuing. Only when `git worktree list --porcelain` output does not disambiguate the two cases, fall back to the existing safe default and halt: report to the operator that the branch matches the current cwd AND `<worktree_path>` exists, that `git worktree list --porcelain` output was inconclusive, and that the run is stopping rather than guessing.
```

  This removes the call to `_inplace.prompt_stale_worktree` (an `input()` call) from this call site. `_inplace.py` itself is unchanged — it is listed in Context only so the implementer can confirm the exact behavior being replaced (`prompt_stale_worktree`'s docstring and numbered-options text) before writing the new prose.

  Clarifying note on the (unchanged) trigger condition: "the branch matches" compares the worktree directory's checked-out branch (from the `git worktree list --porcelain` entry) against the active task's branch (`active_data`'s branch, from Entry Step 1). Because git does not allow the same branch to be checked out in two worktrees simultaneously, the `mode = 'worktree'` resolution above may rarely fire in practice for a fully live, current registration — it exists as the correct-by-construction counterpart to the `mode = 'inplace'` (stale-registration) branch, not because it is expected to fire often. This ambiguity in "the branch matches" is pre-existing in the source being edited (the trigger condition itself is not changed by this card) and is called out here only for the implementer's benefit, not as something to resolve by rewording the unchanged quoted trigger text above.
- **Commit:** `docs(mill-merge): replace stale-worktree prompt with git-state investigation`

### Card 11: Harden mill-merge's parent-branch resolve call site to non-interactive

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `## Entry`, Step 4 currently reads exactly:

```
4. Resolve parent branch via `_parent_branch.resolve(status_path, interactive=<True unless called non-interactively>, expected_slug=slug)`. `slug` is already bound in Entry Step 1 as `active_data['slug']`. `status_path` is resolved via `_paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (set in Path Setup step 1.5) and `task_dir = status_path.parent` — state lives in `task_dir` on the task branch, not in the wiki.
```

  Replace it with:

```
4. Resolve parent branch via `_parent_branch.resolve(status_path, interactive=False, expected_slug=slug)`. `slug` is already bound in Entry Step 1 as `active_data['slug']`. `status_path` is resolved via `_paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])` (set in Path Setup step 1.5) and `task_dir = status_path.parent` — state lives in `task_dir` on the task branch, not in the wiki. On `_parent_branch.ParentBranchError` (status.md is missing the `parent:` row): `_status.set_blocked(status_path, f"missing parent: row for {slug}", timestamp=_timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-merge: blocked (missing parent: row) for {slug}"` and push, then halt with `BLOCKED: status.md is missing the parent: row for <slug> -- mill-spawn should have written it; set it manually and re-run /mill-merge.`
```

  This matches mill-finalize's existing call (`mill-finalize/SKILL.md:34`, a hardcoded `interactive=False`) and turns the resulting exception into a clean halt instead of ever blocking on stdin.
- **Commit:** `docs(mill-merge): harden parent-branch resolve to non-interactive`

## Batch Tests

`verify: null` — this batch edits only `plugins/mill/skills/mill-merge/SKILL.md`, a prose file interpreted by Claude Code at skill-invocation time. `_inplace.py` is read-only Context for Card 10 and is not modified; `_parent_branch.py` already supports `interactive=False` and needs no change (confirmed during Phase: Plan by reading `_parent_branch.resolve`'s signature and body in the task worktree). There is no runnable test surface for this batch. Correctness is verified by plan review and, downstream, by mill-go's code review reading the resulting diff.
