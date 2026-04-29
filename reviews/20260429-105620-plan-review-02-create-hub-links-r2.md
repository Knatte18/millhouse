# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — 02-create-hub-links

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-create-hub-links
date: 2026-04-29
```

## Findings

### [BLOCKING] Card 7 note contradicts Card 9 on `container_path` expression
**Step:** Card 7 (`recreate_active_junction` signature change), "Note" paragraph
**Issue:** Card 7 says callers compute `container_path` via `_paths.resolve_main_worktree_root(git_root).parent`, but Card 9 explicitly warns NOT to use this because in the new layout it returns `<container>/wts/`, landing the portal entry at `<container>/wts/portals/<slug>` instead of `<container>/portals/<slug>`.
**Fix:** Rewrite Card 7's "Note" to say callers supply `container_path` via `_paths.resolve_container_path(git_root)` (from Card 4), matching Card 9's explicit guidance.

### [NIT] Card 6 hardlink creation omits "link does not exist" path
**Step:** Card 6 (`_setup.create_hub_links` requirements, hardlink logic)
**Issue:** The spec says "skip on inode match, back up on inode mismatch, then create via `Path.hardlink_to`" but never covers the first-run case where `link_path` doesn't exist — `Path.stat()` raises `FileNotFoundError` there.
**Fix:** Add one sentence: "If `link_path` does not exist, skip the inode check and proceed directly to `Path.hardlink_to`."

### [NIT] Card 7 docstring guidance is self-contradictory
**Step:** Card 7 (docstring update)
**Issue:** Says to "drop the line that says 'mill-spawn does NOT call this helper'" but immediately notes the comment is "now true for a different reason" — dropping a correct comment removes useful documentation for no benefit.
**Fix:** Change "drop the line" to "update the line to reflect that mill-spawn routes through `_setup.create_hub_links` rather than calling this helper directly."

### [NIT] Test mock maps don't account for new imports added by Cards 8–9
**Step:** Cards 8 and 9 (test extension requirements)
**Issue:** After Card 8, `millpy-spawn.py` will import `_setup` at module level; `_run_main_with_mocks` has no `_setup` entry in its stub map, causing an import error on exec. Similarly, `test-millpy-claim.py`'s `_make_stub_map` has no `resolve_container_path` on the `_paths` mock, so `container_path / "portals"` returns a `MagicMock` that won't satisfy the call-order assertions.
**Fix:** Cards 8 and 9 should explicitly state that the stub maps must add `_setup` (with `create_hub_links` mocked) and `resolve_container_path` (returning a concrete `Path`) respectively.

## Verdict

REQUEST_CHANGES
Card 7's "Note" prescribes the wrong expression for `container_path`, directly contradicting Card 9's explicit prohibition of the same expression.