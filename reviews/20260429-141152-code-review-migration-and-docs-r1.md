# Review: 11 — par-C — Container layout overhaul + cwd-as-hub everywhere + gitignore-split — migration-and-docs

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: migration-and-docs
date: 2026-04-29
```

## Findings

### [NIT] Unused `dry_run` param in `_log` and `_check_in_flight`
**Location:** `millpy-migrate-layout.py:42`, `millpy-migrate-layout.py:68`
**Issue:** Both `_log` and `_check_in_flight` accept `dry_run: bool` but never reference it; `_log`'s write guard uses `log_fh is not None` (correctly set to None in dry-run), making the param dead in both functions.
**Fix:** Remove `dry_run` from both signatures and call sites; the behavior is already controlled via `log_fh`.

### [NIT] `os.path.realpath` vs plan's `Path.resolve()` in portal pre-check
**Location:** `millpy-migrate-layout.py:201`
**Issue:** Plan spec says "Use `os.path.lexists` plus `Path.resolve()` for the check"; implementation uses `os.path.realpath` for the existing-target comparison. Functionally equivalent on most paths but deviates from spec.
**Fix:** Replace `str(Path(os.path.realpath(str(link_path))))` with `str(Path(link_path).resolve())`.

### [NIT] Trivially dead conditional `hub_display`
**Location:** `millpy-migrate-layout.py:237`
**Issue:** `hub_display = new_main_root if not dry_run else new_main_root` — both branches are identical.
**Fix:** `hub_display = new_main_root`.

### [NIT] Log file opened outside `try` block
**Location:** `millpy-migrate-layout.py:162–168`
**Issue:** `log_fh = open(...)` precedes the `try/finally` that closes it; the `finally` still runs on `SystemExit`, so the leak window is only the two `print` statements between open and try — effectively zero risk but slightly non-idiomatic.
**Fix:** Move `log_fh = open(...)` to the first line inside the `try` block.

## Verdict

APPROVE
Four NITs, all cosmetic; core migration logic, preflight checks, dry-run path, and CLAUDE.md update are plan-compliant and correct.