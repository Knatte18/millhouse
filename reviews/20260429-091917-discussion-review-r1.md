# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: wiki/active/container-restructure/discussion.md
date: 2026-04-29
```

## Findings

### [GAP] `.others` junction missing from gitignore split
**Section:** `## Decisions → gitignore-split`
**Issue:** `ANCHORED_ENTRIES = ["/.active", *hardlink_names]` — the new `/.others` junction (created in every worktree by `_setup.create_hub_links`) is absent from both `GLOB_ENTRIES` and `ANCHORED_ENTRIES`. Confirmed: neither list in the discussion nor the current `_gitignore.py` covers `.others`. Every post-spawn worktree will show `.others` as untracked in `git status`.
**Fix:** Add `/.others` to `ANCHORED_ENTRIES` alongside `/.active`; update Q&A entry Q8 accordingly.

### [NOTE] `_review_common.resolve_path` container derivation implicit
**Section:** `## Decisions → review-template-paths`
**Issue:** Discussion states the new signature as `resolve_path(slug, key)` but doesn't say how `container_path` (required by `_paths.resolve_active_worktree`) is derived inside the function. Current implementation takes explicit `wiki_root`; the replacement parameter is unspecified.
**Fix:** State whether the function derives `container_path` internally via `_paths.resolve_main_worktree_root(git_toplevel).parent` or takes it as an explicit argument; confirm how the three review CLI scripts supply it.

### [NOTE] Migration-ordering gap: mill-setup before migration corrupts gitignore
**Section:** `## Decisions → migration-strategy`
**Issue:** Once new `_gitignore.py` ships, any standalone `mill-setup` run (before `millpy-migrate-layout.py`) rewrites `.gitignore` with `**/wts/` and drops `**/worktrees/`, leaving the still-existing `worktrees/` directory un-gitignored. The migration script re-runs mill-setup at step 6, but the constraint "don't run mill-setup standalone before migration" is not stated.
**Fix:** Add one line to the migration decision: operators must not run `mill-setup` standalone between deploying the new code and completing the migration.

## Verdict

GAPS_FOUND
One functional gap: `.others` junction requires a gitignore entry that the specification omits.