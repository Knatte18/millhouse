# Review: 12 (C) — Restructure hub junction layout — 03-teardown-migration

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-teardown-migration
date: 2026-05-06
```

## Findings

### [BLOCKING] Dangling junction detection misses Windows NTFS junctions

**Step:** Card 10, Requirement 3
**Issue:** `(active_link.exists() or active_link.is_symlink()) and not active_link.is_dir()` evaluates to `False` for a dangling Windows junction — `exists()` returns False when the target is gone, and `is_symlink()` is False for NTFS reparse-point junctions. The junction is never removed.
**Fix:** Replace with `os.path.lexists(str(active_link)) and not active_link.is_dir()`. Card 12 test 3 must patch `os.path.lexists` accordingly, not `Path.exists`.

### [BLOCKING] `_config.load_config` called with config file path, not worktree root

**Step:** Card 11, Requirement 4b
**Issue:** `_config.load_config(wiki_path, hub_root / ".millhouse" / "config.local.yaml")` passes the config *file* path as `worktree_root`; the function signature is `load_config(wiki_path, worktree_root)` and internally constructs `worktree_root / ".millhouse" / "config.local.yaml"` itself. The conditional `if that file exists` is also redundant — `load_config` is lenient when the file is absent.
**Fix:** Use `cfg = _config.load_config(wiki_path, hub_root)` unconditionally.

### [BLOCKING] `_gitignore.upsert` does not exist

**Step:** Card 11, Requirement 4f
**Issue:** `_gitignore.upsert(hub_gitignore, _gitignore.GLOB_ENTRIES)` references a function that is not in `_gitignore.py`'s public API; the module only exposes `render_block` and `upsert_split`.
**Fix:** Use `_gitignore.upsert_split(hub_gitignore, hub_gitignore, _gitignore.GLOB_ENTRIES, _gitignore.ANCHORED_ENTRIES)`.

### [NIT] Card 11 Req 4e produces N commits instead of one for the task/ move

**Step:** Card 11, Requirement 4e (working-state move)
**Issue:** "git mv src → dst, then git commit" inside the per-file loop creates one commit per file, polluting branch history.
**Fix:** Stage all `git mv` operations first, then issue a single commit covering all four paths.

## Verdict

REQUEST_CHANGES — three BLOCKINGs: dangling-junction detection (Windows), wrong `load_config` argument, and non-existent `_gitignore.upsert`.