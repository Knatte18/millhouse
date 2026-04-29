# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 03-state-on-worktree

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-state-on-worktree
date: 2026-04-29
```

## Findings

### [BLOCKING] `resolve_container_path` absent from plan
**Step:** Card 12
**Issue:** Card 12 calls `_paths.resolve_container_path(Path.cwd())`, crediting it to "Card 4" (batch 02), but the overview's `_paths.py` changes list only `resolve_hub_relative_path` and `resolve_active_worktree` — `resolve_container_path` appears nowhere in any batch plan or in the current source, so it will not exist when batch 03 runs.
**Fix:** Either extend batch 02's `_paths.py` spec to add `resolve_container_path` (contract: `resolve_main_worktree_root(cwd).parent.parent`, returning `<container>/` — two levels up, not one, because one level gives `<container>/wts/` which makes `resolve_active_worktree` land at `<container>/wts/wts/<slug>`), or replace the Card 12 reference with the inline expression `resolve_main_worktree_root(Path.cwd()).parent.parent` plus a comment explaining why the double-parent is required.

### [BLOCKING] Card 15 omits Phase: Active path update
**Step:** Card 15, mill-start Phase: Active
**Issue:** After Card 11, `status.md` lives at `<worktree_root>/status.md`, but mill-start Phase: Active still tells the operator to verify it at `<WIKI_PATH>/active/<slug>/status.md`; this phase is not named in Card 15's explicit update list and requirement (c)'s catch-all ("drop any prose referencing `<WIKI_PATH>/active/<slug>/...`") is easily missed when the implementer works through the enumerated phases.
**Fix:** Name Phase: Active explicitly in Card 15's requirements, changing the verification target from `<WIKI_PATH>/active/<slug>/status.md` to `<worktree_root>/status.md` to match the written location after Card 11 lands.

### [NIT] Card 11 forced-failure test lacks corruption technique
**Step:** Card 11, test-spawn-core.py
**Issue:** The requirement names "corrupted git index → non-zero `git add` exit" without specifying how to induce that state, leaving the implementer free to patch `_subprocess_util.run` directly, which would not exercise the actual subprocess error path.
**Fix:** Specify the concrete technique — e.g., delete `<repo>/.git/index` before calling `write_initial_status` — so the test drives a real non-zero exit from the `git add` subprocess.

### [NIT] Module docstring not in Card 11 scope
**Step:** Card 11, `_spawn_core.py` module-level API summary
**Issue:** The module docstring still lists `write_initial_status(wiki_path, …)` with "lock + commit+push" semantics; Card 11's requirements do not mention updating it.
**Fix:** Include the module-level docstring entry in Card 11's requirements, renaming the parameter to `worktree_path` and updating the summary line from "Render + write `active/<slug>/status.md`; lock + commit+push" to "Render + write `status.md` at worktree root; stage + commit on task branch".