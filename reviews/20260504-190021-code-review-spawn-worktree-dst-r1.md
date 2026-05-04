# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo — spawn-worktree-dst

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: spawn-worktree-dst
date: 2026-05-04
```

## Findings

### [NIT] Worktree junction links anchor at `worktree_path`, not `dest_hub`
**Location:** `millpy-worktree.py` (inside `_cmd_create` junction loop)
**Issue:** `link_path = worktree_path / junction_rel` — for subfolder-install, this places junctions like `.millhouse/wiki` inside the stub's `.millhouse/` rather than `dest_hub / ".millhouse" / "wiki"`, diverging from spawn's `create_hub_links(dest_hub, ...)` which anchors at `dest_hub`. Card 12's requirements don't ask for this change, and the subfolder test mocks junctions to `{}`, so no test catches it.
**Fix:** Change `link_path = worktree_path / junction_rel` to `link_path = dest_hub / junction_rel` and update Card 12 requirements accordingly before the next batch.

### [NIT] `_run_main_with_mocks` leaves `resolve_hub_path` / `resolve_hub_relative_path` as raw MagicMocks
**Location:** `test-millpy-spawn.py:_run_main_with_mocks`
**Issue:** `paths_mock` is a plain `MagicMock()`, so `resolve_hub_path()` and `resolve_hub_relative_path(wt, ".")` both return MagicMocks. Existing tests check only kwargs on `write_active_marker`/`write_initial_status` and happen to pass, but assertions on `create_hub_links`'s first arg (tested in the separate `test_create_hub_links_called_after_portal_creation`) would silently pass with a MagicMock path if `hub_subpath` were non-`"."`.
**Fix:** Add `paths_mock.resolve_hub_path.return_value = Path("/fake/repo")` and `paths_mock.resolve_hub_relative_path.side_effect = lambda wt, sub: wt if sub == "." else wt / sub` in `_run_main_with_mocks`.

## Verdict

APPROVE — all four cards' requirements are faithfully realised; two nits, zero blockers.