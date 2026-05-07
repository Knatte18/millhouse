# Review: 12 (C) — Restructure hub junction layout — 03-teardown-migration

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-teardown-migration
date: 2026-05-06
```

## Findings

### [BLOCKING] `_timestamp` missing from Card 11 Context
**Step:** Card 11, Requirement 1 / step 4c–4e
**Issue:** Requirements call `_timestamp.now_utc_compact()` but `_timestamp.py` is absent from Card 11's `Context:` and `Edits:` fields. No provided source file imports `_timestamp`; the module may be new (batch 02) or may not exist — either way the Context is incomplete per the context-completeness criterion.
**Fix:** Add `_timestamp.py` to Card 11 Context with its expected public API (`now_utc_compact() -> str`), or replace with inline `datetime` formatting as used in the rest of `millpy-migrate-layout.py` (e.g. `datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")`).

### [NIT] Token dict incomplete vs `_build_tokens` pattern
**Step:** Card 11, step 4e (recreate junctions)
**Issue:** The spec token dict `{"SLUG": slug, "WIKI_PATH": ..., "CONTAINER_PATH": ..., "HUB_PATH": ...}` omits `CWD_PATH` and `REPO` that `_build_tokens` in `millpy-spawn.py` provides. If any junction template in `wiki/config.yaml` references `<CWD_PATH>` or `<REPO>`, `_junction.resolve_target` will raise `ValueError` and abort mid-migration.
**Fix:** Construct tokens using the full `_build_tokens` pattern (`CWD_PATH`, `REPO`, plus slug-specific keys) rather than a minimal subset.

### [NIT] No test for `_apply_inplace_record` status path fallback
**Step:** Card 12
**Issue:** Card 10 Requirement 2 adds the two-path fallback to `_apply_inplace_record` (two call sites for `record.worktree_path / "status.md"`), but Card 12 adds no test exercising this path. The existing in-place test fixture writes `status.md` at root only.
**Fix:** Add a test variant where `task/status.md` exists at the worktree root and verify `_apply_inplace_record` reads phase and parent branch from the `task/` location.

### [NIT] `_gitignore.upsert` not in current API; batch 01 interface undocumented here
**Step:** Card 11, step 4f
**Issue:** Current `_gitignore.py` exposes `upsert_split` but not `upsert`. The call `_gitignore.upsert(hub_gitignore, _gitignore.GLOB_ENTRIES)` depends on batch 01 adding this function, but its signature and whether it covers anchored entries (`/.wiki`, `/.portals`) is not specified in this batch's plan.
**Fix:** Document the expected `upsert(path, entries)` contract in this batch or confirm via batch 01's plan that `upsert` with the proposed signature is exactly what batch 01 delivers.

## Verdict

REQUEST_CHANGES
`_timestamp.py` missing from Card 11 Context is BLOCKING; three NITs noted.