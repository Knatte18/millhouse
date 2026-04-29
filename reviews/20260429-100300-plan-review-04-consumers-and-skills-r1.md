# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 04-consumers-and-skills

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-consumers-and-skills
date: 2026-04-29
```

## Findings

### [BLOCKING] Card 17: `active_dir` semantic split not specified — will delete worktrees
**Step:** Card 17, requirement (b) + (c) + `apply_plan`
**Issue:** Renaming `active_dirs → active_worktrees` means `active_dir_by_slug` maps slug → worktree root, so `SlugRecord.active_dir` becomes the worktree root. But `apply_plan` calls `shutil.rmtree(record.active_dir)` on every cleaned record — this would wipe the entire git worktree directory. Additionally, `_apply_inplace_record` reads `parent_branch = _status.read_parent_branch(record.active_dir / "status.md")`; on a fresh layout where the wiki dir is gone, `active_dir` would need to be None, causing silent cleanup abort. Requirements (b) and (c) are mutually inconsistent: (b) implies `active_dir` = worktree root; (c) implies `active_dir` = optional legacy wiki dir.
**Fix:** Explicitly restructure `SlugRecord` to carry two separate fields — e.g. `worktree_path` (always the worktree root, used for status reads and `_read_phase`) and `wiki_active_dir: Path | None` (the legacy `wiki/active/<slug>/` for conditional removal). Update `build_plan` to populate both, `apply_plan` to rmtree only `wiki_active_dir`, and `_apply_inplace_record` to read `parent_branch` from `worktree_path / "status.md"` (falling back to `hub_root / "status.md"` for in-place tasks).

### [NIT] Card 15: `_worktree.list_worktrees` / `worktree_map` not addressed
**Step:** Card 15 requirements
**Issue:** Both `millpy-status.py` and `millpy-inspect.py` call `_worktree.list_worktrees` to build a `worktree_map`. After switching to `discover_active_worktrees`, this map is redundant — the discovery scan already returns `(path, slug, title)` triples covering the same data. The card's requirements don't say to remove or replace these calls, leaving dead imports and potentially stale data (two sources for the same paths).
**Fix:** Add to Card 15 requirements: remove `_worktree.list_worktrees` calls in both scripts; populate `worktree_map` (or the WORKTREE display column) directly from the `discover_active_worktrees` result.

### [NIT] Card 16: `load_config` call site must use chosen-worktree path
**Step:** Card 16 requirements
**Issue:** Both launcher scripts currently call `_load_config(wiki_path, git_root)` where `git_root` is the hub — reading `.millhouse/config.local.yaml` from the hub, not from the selected worktree. The `hub_relative_path` key is written per-worktree at setup time. Reading it from the hub produces the hub's own value, not the chosen worktree's.
**Fix:** Clarify in requirements that the `load_config` call must use `selected_path` (the chosen worktree root) as the second argument so the per-worktree `config.local.yaml` is read. One sentence is sufficient: "call `_load_config(wiki_path, selected_path)` after selection."

## Verdict

REQUEST_CHANGES
Card 17's `active_dir` semantic ambiguity would cause `apply_plan` to `shutil.rmtree` live git worktrees.