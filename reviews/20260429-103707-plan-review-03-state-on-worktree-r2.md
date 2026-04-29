# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 03-state-on-worktree

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 03-state-on-worktree
date: 2026-04-29
```

## Findings

### [NIT] Card 12 — "stripping" vs. substituting `<SLUG>` in resolve_path
**Step:** Card 12 — resolve_path new body
**Issue:** "returns `active_worktree / path_tmpl` after stripping any `<SLUG>` substitution from `path_tmpl`" is genuinely ambiguous: `path_tmpl.replace("<SLUG>", "")` (strip to empty) vs. `path_tmpl.replace("<SLUG>", slug)` (substitute). Both produce wrong paths for stale templates and no-ops for new ones, but the intended semantics are unclear from the spec alone.
**Fix:** Add one explicit example: `path_tmpl.replace("<SLUG>", slug)` (or `replace("<SLUG>", "")`) so the implementer makes a deliberate choice rather than guessing.

### [NIT] Card 15 — mill-start "Phase: Active" not named in update list
**Step:** Card 15, point (a) update list
**Issue:** Point (c)'s catch-all ("drop any prose that references `<WIKI_PATH>/active/<slug>/...`") covers it, but "Phase: Active" contains an explicit hard-coded path `<WIKI_PATH>/active/<slug>/status.md` and is not called out in the enumerated section list — easy to miss alongside the larger structural changes.
**Fix:** Add "Phase: Active: update `<WIKI_PATH>/active/<slug>/status.md` → `<worktree_root>/status.md`" as a bullet in point (a)'s enumeration.

### [NIT] Card 11 — module-level docstring entry for write_initial_status not mentioned
**Step:** Card 11, Requirements
**Issue:** `_spawn_core.py`'s module docstring entry still describes `write_initial_status(wiki_path, ...)` with "lock + commit+push"; the plan doesn't ask the implementer to update it, leaving a stale Public API table.
**Fix:** Add one sentence to Card 11's requirements: "Update the module-level Public API entry to reflect the new parameter name and behaviour (worktree commit, no push, no lock)."

### [NIT] Card 14 — top-level wiki/config.yaml comment not addressed
**Step:** Card 14, Requirements
**Issue:** The plan says to update the section header above `paths:`, but the top-level file comment also says "Path placeholders use `<SLUG>` (uppercase). Substituted via str.replace in `_review_common.resolve_path()` — NOT via `_render.render()`." This will be stale after Card 14.
**Fix:** Add a note to Card 14 to also update the top-level comment (e.g. change that line to reference the new worktree-relative shape with no `<SLUG>` substitution).

## Verdict

APPROVE — no BLOCKINGs; four small documentation/clarity NITs that don't affect implementation correctness.