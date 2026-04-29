# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 01-foundation

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 01-foundation
date: 2026-04-29
```

## Findings

### [BLOCKING] Prefix-form `resolve_worktrees_dir` test contradicts fallback change

**Step:** Card 4
**Issue:** Card 4 changes the fallback to `main_root.parent` but also states "Prefix-form tests (using `tmp_path / "foo"`) are unchanged." The existing assertion `got == tmp_path / "foo.worktrees"` will fail because `(tmp_path / "foo").parent == tmp_path`, not `tmp_path / "foo.worktrees"`. Verify breaks if the implementer follows the "unchanged" instruction literally.
**Fix:** Remove the contradictory "unchanged" clause; explicitly say to update the prefix-form `resolve_worktrees_dir` assertion to expect `tmp_path` (or drop the case entirely, noting prefix-form users must configure `spawn.worktrees_dir`).

### [NIT] `STANDARD_ENTRIES` removal not called out in test requirements

**Step:** Card 5
**Issue:** `test-gitignore-phase.py` imports `STANDARD_ENTRIES` directly; Card 5 removes it and replaces it with `GLOB_ENTRIES` / `ANCHORED_ENTRIES`, but the test-modification requirements don't mention updating this import. The test will fail at import, taking out the full file.
**Fix:** Add "replace `STANDARD_ENTRIES` import and all references with `GLOB_ENTRIES + ANCHORED_ENTRIES`" to Card 5's test-modification requirements.

### [NIT] `render_block` "overload" term is unimplementable as written

**Step:** Card 5
**Issue:** "Add a new `render_block(glob_entries, anchored_entries)` overload [...] keep old `render_block(hardlink_entries)` shape unchanged" — Python cannot have two functions with the same name; the second definition silently replaces the first.
**Fix:** Specify the mechanism: either an internal helper `_render_split_block(glob, anchored)` used by `upsert_split`, or a single function with an optional second positional argument (with type-dispatch on its presence).

### [NIT] `container_path` derivation in discussion.md is off by one `.parent`

**Step:** Card 3 (affects batch 03)
**Issue:** `discussion.md § review-template-paths` says consumers derive `container_path = resolve_main_worktree_root(cwd).parent`, giving `<container>/wts/`. Card 3's function body uses `container_path / "wts" / slug`, so `container_path` must be `<container>` — one more `.parent` up. Card 3's spec is internally correct; the discussion prose is wrong.
**Fix:** Card 3 needs no change; add a note that batch 03's implementer must derive `container_path = resolve_main_worktree_root(cwd).parent.parent` (not `.parent`) before calling `resolve_active_worktree`.

## Verdict

REQUEST_CHANGES
Card 4's "prefix-form tests unchanged" statement directly contradicts the fallback change and will break verify; fix it before proceeding.