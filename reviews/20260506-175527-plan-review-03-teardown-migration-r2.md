# Review: 12 (C) — Restructure hub junction layout — 03-teardown-migration

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-teardown-migration
date: 2026-05-06
```

## Findings

### [BLOCKING] `build_plan` read_parent_branch also needs fallback
**Step:** Card 10, Requirement 2
**Issue:** Requirement 2 patches two `status.md` reads inside `_apply_inplace_record`, but `build_plan` also calls `_status.read_parent_branch(wt_path / "status.md")` inside the `if phase == "done":` block. After Req 1 reads phase from `task/status.md`, the `read_parent_branch` call still targets the (now absent) root `status.md`, returning `None` and silently skipping the unmerged-commits guard — a migrated worktree with unmerged work would be moved to `to_remove_done`.
**Fix:** Add the same `_task_status if _task_status.exists() else _legacy_status` pattern to the `read_parent_branch` call in `build_plan`'s `if phase == "done":` block; this falls squarely under the shared decision `task-status-path-fallback` ("any consumer that reads `status.md` by path").

### [BLOCKING] `_timestamp` used but not imported in Card 11
**Step:** Card 11, Requirement 4e / Requirement 1
**Issue:** `_step_rename_junctions` uses `_timestamp.now_utc_compact()` to generate `ts`, but Requirement 1 only adds `import _setup, _spawn_core, _gitignore, _config` — `_timestamp` is absent from the import list. Code produced by following the spec verbatim raises `NameError` at runtime.
**Fix:** Add `import _timestamp` to the imports list in Requirement 1 (or substitute `datetime.datetime.now(datetime.timezone.utc).strftime(...)` inline, consistent with the existing `_run_migration` timestamp generation in the same file).

### [NIT] Redundant pre-check before idempotent `_junction.remove`
**Step:** Card 11, Requirement 4e (old-junction manual strip loop)
**Issue:** `if path.exists() or path.is_symlink(): _junction.remove(path)` — `remove()` already calls `os.path.lexists` internally and returns silently when absent; the guard is dead code and misses broken junctions (`lexists` True, `exists` False).
**Fix:** Call `_junction.remove(path)` directly without the pre-check.

## Verdict

REQUEST_CHANGES — two blockers: missing `read_parent_branch` fallback in `build_plan` and missing `_timestamp` import.