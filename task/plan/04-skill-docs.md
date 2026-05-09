# Batch: skill-docs

```yaml
task: Drop active.slug.md marker
batch: skill-docs
number: 4
cards: 4
verify: null
depends-on: [2]
```

## Batch Scope

Update the 8 SKILL.md files that reference `active.slug.md`, `_active.read_slug`, `_active.read_all`, or the marker file in prose. All updates are documentation-only: replace API examples with the new `_marker` equivalents and drop prose mentions of the marker file. No code changes.

`verify: null` because SKILL.md is not executed — it is read by the agent at skill-load time. There is no run-time gate; correctness is verified by reading the rendered prose.

Cards group SKILL files into pairs of related skills to keep edits cohesive. Card numbering is global; cards in this batch start at 30.

## Cards

### Card 30: update `mill-go/SKILL.md` and `mill-plan/SKILL.md`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-go/SKILL.md`: Entry step 1 currently reads `Read the task slug: \`slug = _active.read_slug(Path(".millhouse"))\`` and the signature line `signature: _active.read_slug(mill_dir: Path) -> str`. Replace with `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)` plus `signature: _marker.slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str`. The error message stays the same shape: "Missing → halt with 'this worktree was not created by mill-spawn'." Adjust to refer to `MarkerError` instead of missing marker. In `mill-plan/SKILL.md`: Entry step 2 has the same pattern (`Read the slug via _active.read_slug(Path(".millhouse"))`); apply the identical replacement.
- **Commit:** `docs(mill-go,mill-plan): replace _active.read_slug references with _marker.slug_from_branch`

### Card 31: update `mill-merge/SKILL.md` and `mill-merge-in/SKILL.md`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-merge/SKILL.md`: Step 1 currently calls `active_data = _active.read_all(Path('.millhouse'))` and on `_active.ActiveError` halts; later (Step 3) calls `_active.read_slug`. Replace with `_marker.task_data(git_root, wiki_path, cfg)` and `_marker.MarkerError`. Update Step 3 to reuse the data already obtained in Step 1 (the original instruction said "reuse `active_data` — no second read needed"; preserve that intent with the new API). The `mode_inplace = _inplace.is_inplace(active_data, git_root, cfg)` call in Step 1 becomes `mode_inplace = _inplace.is_inplace(slug, git_root, cfg)`. **Step 8 in-place mode marker delete (line 222):** delete the line `Also remove \`<git_root>/.millhouse/active.slug.md\` (the canonical in-place marker).` — the surrounding `git checkout <parent_branch>` and `git branch -D "$CHILD_BRANCH"` already handle the cleanup. In `mill-merge-in/SKILL.md`: Entry step 2 has `Read the slug via _active.read_slug(Path(".millhouse"))`; apply the same replacement to `_marker.slug_from_branch`.
- **Commit:** `docs(mill-merge,mill-merge-in): switch to _marker API; drop marker delete line`

### Card 32: update `mill-start/SKILL.md` and `mill-claim/SKILL.md`

- **Context:**
  - `plugins/mill/scripts/_marker.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-claim/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-start/SKILL.md`: Entry step 2 (`Read the slug from .millhouse/active.slug.md via _active.read_slug(Path(".millhouse"))`) becomes `Read the slug via _marker.slug_from_branch(git_root, wiki_path, cfg)`. Phase: Select (the line `find the task heading whose slug matches the one from active.slug.md`) becomes `find the task heading whose slug matches the slug derived from the current branch`. In `mill-claim/SKILL.md`: the line `mill-claim does NOT create a <container>/wts/<slug>/ directory… The task branch is checked out in place; .millhouse/active.slug.md is written at the hub` becomes `mill-claim does NOT create a <container>/wts/<slug>/ directory… The task branch is checked out in place. The "this is a mill task worktree" signal is the branch+Home.md pair, not a marker file.`
- **Commit:** `docs(mill-start,mill-claim): replace marker references with branch+Home.md`

### Card 33: update `mill-terminal/SKILL.md` and `mill-autofix/SKILL.md`

- **Context:**
  - `plugins/mill/scripts/_spawn_core.py`
- **Edits:**
  - `plugins/mill/skills/mill-terminal/SKILL.md`
  - `plugins/mill/skills/mill-autofix/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-terminal/SKILL.md`: the description (`Scans the worktrees container for directories with an active.slug.md marker`) becomes `Scans the worktrees container for directories whose current branch maps to an active task in Home.md`. In `mill-autofix/SKILL.md`: drop the `rm -f .millhouse/active.slug.md` line at line 400 entirely (Phase 3.6 stuck-cleanup helper). The surrounding `git reset --hard HEAD; git clean -fd task/; git checkout <parent_branch>` block stays. Update any prose mention that refers to the marker file as the cleanup signal.
- **Commit:** `docs(mill-terminal,mill-autofix): drop marker references; remove rm -f marker line`

## Batch Tests

`verify: null`. Documentation-only batch.

Manual review: open each updated `SKILL.md` and confirm no remaining `active.slug.md`, `_active.`, or `read_slug(Path(".millhouse"))` references appear unless they are (a) historical context that explicitly says "the legacy marker, removed in task 38" or (b) a string literal in a code example unrelated to the change.
