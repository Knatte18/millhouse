# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo — 03-spawn-worktree-dst

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-spawn-worktree-dst
date: 2026-05-04
```

## Findings

### [BLOCKING] Card 12 imports missing `resolve_container_path`
**Step:** Card 12 — Fix millpy-worktree.py
**Issue:** Requirements update the inline tokens dict to use `resolve_container_path(git_root)` for `CONTAINER_PATH`, but the import additions only list `resolve_hub_path` and `resolve_hub_relative_path`. `resolve_container_path` is not currently imported in `millpy-worktree.py` and isn't mentioned in the import instruction, so the implementer following the card literally will produce a `NameError` at runtime.
**Fix:** Add `resolve_container_path` to the `from _paths import ...` line in Card 12's requirements alongside `resolve_hub_path` and `resolve_hub_relative_path`.

### [NIT] Card 11 Test 2 assertion (e) uses wrong call_args accessor
**Step:** Card 11 — Update test-millpy-spawn.py, Test 2
**Issue:** Requirement (e) asserts `_setup.create_hub_links` was called with `target_root=worktree_path / "src/Models"`, but `create_hub_links` is invoked positionally (`_setup.create_hub_links(dest_hub, wiki_path, dest_tokens)`), so `call_args.kwargs.get("target_root")` returns `None` — the assertion silently passes or fails incorrectly.
**Fix:** Change assertion to check `call_args.args[0] == worktree_path / "src/Models"`.

## Verdict

REQUEST_CHANGES
One import gap in Card 12 will cause a runtime `NameError`; fix before implementing.