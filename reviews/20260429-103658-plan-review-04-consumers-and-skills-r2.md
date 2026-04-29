# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 04-consumers-and-skills

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-consumers-and-skills
date: 2026-04-29
```

## Findings

### [BLOCKING] Card 21 — mill-resume Phase 6 old worktrees path unaddressed
**Step:** Card 21, Requirements
**Issue:** Card 21 states to drop all `wiki/active/<slug>/` references, but mill-resume Phase 6 ("Create worktree") independently uses the old path `<git-root-parent>/<repo-name>.worktrees/<slug>` — which never contains `wiki/active/<slug>/`, so the stated requirement leaves it untouched. An implementer following the card literally produces a SKILL.md that instructs creating worktrees at the wrong location for cross-machine resume.
**Fix:** Add explicit requirement: update Phase 6 to `git -C <git-root> worktree add <container>/wts/<slug> <branch_name>` and update `<worktrees-dir>` definition to `<container>/wts/`.

### [NIT] Card 17 — two config loads needed but plan phrases it as replacement
**Step:** Card 17, Requirements
**Issue:** The existing `_load_config(wiki_path, git_root)` call is needed before the pick to resolve `worktrees_dir`. The plan's phrasing "call `_load_config(wiki_path, selected_path)` (passing the chosen worktree root, NOT `git_root`/the hub)" reads as a replacement, not an additional call.
**Fix:** Clarify that the pre-pick hub config load is preserved; the per-worktree load is a second call made post-pick.

### [NIT] Card 18 — `container_path` derivation unstated for portal removal
**Step:** Card 18, requirement (e)
**Issue:** Plan says both `_apply_worktree_record` and `_apply_inplace_record` must call `_junction.remove(container_path / "portals" / slug)`, but neither receives `container_path` and the plan doesn't say how to obtain it.
**Fix:** State: compute `container_path = _paths.resolve_main_worktree_root(hub_root).parent` inline in both functions (both already receive `hub_root`).

### [NIT] Card 16 — "call stays" wording is vacuously true
**Step:** Card 16, Requirements
**Issue:** "Where any of the three scripts call `_paths.resolve_worktrees_dir(cfg, git_root)`, the call stays" — none of the three scripts currently call it, so the sentence implies an existing call that must actually be added.
**Fix:** Rephrase to: "Add `container_path = _paths.resolve_main_worktree_root(git_root).parent` to each script to derive the worktrees root for the `discover_active_worktrees` call."

## Verdict

REQUEST_CHANGES
Card 21 requirements omit the mill-resume Phase 6 worktrees-path update; that one gap would survive implementation and leave cross-machine resume broken.