# Review: 12 (C) — Restructure hub junction layout — 02-spawn-wiki-config

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-spawn-wiki-config
date: 2026-05-06
```

## Findings

### [BLOCKING] Card 6 passes `git_root` not `resolve_hub_path()` to `recreate_active_junction`
**Step:** Card 6, req 4
**Issue:** The change specifies `_spawn_core.recreate_active_junction(slug, git_root, container_path)`, justifying it with `mill_dir.parent == git_root`. This equality only holds for standard layout. In subfolder installs `resolve_hub_path()` (cwd = hub subdir) differs from `git_root` (repo root), so `.active` would be placed at `git_root / ".active"` (repo root) instead of the hub directory — exactly the regression `test_hub_paths_use_cwd_not_git_root` was written to prevent.
**Fix:** Pass `resolve_hub_path()` instead of `git_root`, matching Card 5 req 4's correct approach.

### [NIT] Card 9 `test_main_happy_path` assertion still wrong after edit
**Step:** Card 9, test-millpy-claim.py
**Issue:** The plan updates `expected_mill_dir` to `expected_hub_root = Path("/fake/repo")`. But in the test stub map `resolve_hub_path` returns `Path("/fake/repo")` and `resolve_git_root` also returns `Path("/fake/repo")` — the test cannot distinguish `git_root` from `resolve_hub_path()`, so it won't catch the subfolder-install regression above.
**Fix:** If `git_root` is corrected to `resolve_hub_path()` (per the BLOCKING fix), the assertion still passes; if left as `git_root`, add a distinct hub_path value to expose the divergence.

### [NIT] Card 3 Context omits `_paths.py`
**Step:** Card 3, req 6
**Issue:** Req 6 tells the implementer to resolve `wiki_path` via `_paths.resolve_wiki_path(_paths.resolve_git_root())`, but `_paths.py` is absent from Context.
**Fix:** Add `plugins/mill/scripts/_paths.py` to Card 3 Context.

## Verdict

REQUEST_CHANGES — one BLOCKING: Card 6 must pass `resolve_hub_path()` not `git_root` to `recreate_active_junction`.