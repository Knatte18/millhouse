# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: wiki/active/container-restructure/discussion.md
date: 2026-04-29
```

## Findings

### [GAP] mill-claim and recreate_active_junction absent from module table
**Section:** Technical context — Modules touched
**Issue:** `millpy-claim.py:273` calls `_spawn_core.recreate_active_junction(wiki_path, slug, mill_dir)`, which creates `.active` → `wiki_path / "active" / slug`. After the layout change `.active` must target `<CONTAINER_PATH>/portals/<SLUG>/`. Neither `millpy-claim.py` nor `recreate_active_junction`'s required changes are in the module-touched table; mill-claim also has no portal-creation step mirroring mill-spawn's.
**Fix:** Add `millpy-claim.py` and the `recreate_active_junction` change in `_spawn_core.py` to the module table; state whether portal creation is mill-claim's responsibility or pre-exists via mill-spawn.

### [GAP] `<SLUG>` token undefined for main-worktree junction creation
**Section:** Decisions — junctions-block-semantic
**Issue:** `_setup.create_hub_links` iterates ALL junction entries including `.active: <CONTAINER_PATH>/portals/<SLUG>/` for both mill-setup and mill-spawn. Mill-spawn provides `<SLUG>`; mill-setup running against the main worktree has none. `_junction.resolve_target` raises `ValueError` on an unknown token. The decision doesn't state whether mill-setup supplies a fallback slug, whether `create_hub_links` silently skips entries with unresolvable tokens, or whether `.active` is excluded from main-worktree creation.
**Fix:** Specify the contract: either `create_hub_links` skips entries whose tokens are absent from the supplied dict, or mill-setup omits `.active` creation, or a sentinel placeholder is passed.

### [GAP] `resolve_path("wts", main_root)` returns wrong path in new layout
**Section:** Decisions — worktrees-dir-default-role
**Issue:** With `main_root = <container>/wts/<repo>` and the new hub-form rule (`parent.name == "wts"` → bare-name), `_sibling.resolve_path("wts", main_root)` returns `<container>/wts / "wts"` = `<container>/wts/wts`, not `<container>/wts/`. In the new layout the worktrees dir is `main_root.parent`, not a sibling reachable via `_sibling.resolve_path`.
**Fix:** State the correct fallback expression (e.g. `main_root.parent`) instead of `resolve_path("wts", main_root)`, and note that `_sibling.resolve_path` is not applicable here since `wts/` is now the parent directory, not a peer.

### [NOTE] Q19 absent from Q&A log
**Section:** Q&A log
**Issue:** Q&A goes Q1–Q18 then jumps to Q20; Q19 is missing.
**Fix:** Renumber or note the gap to avoid confusion when cross-referencing.

## Verdict

GAPS_FOUND  
Three blockers: mill-claim scope omission, undefined `<SLUG>` for main-worktree junctions, and a broken `resolve_worktrees_dir` fallback expression.