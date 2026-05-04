# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo — foundation

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: foundation
date: 2026-05-04
```

## Findings

### [NIT] Unnecessary `_git_init` in three `_config` tests
**Location:** `plugins/mill/unit_tests/test-config.py:55,75,96`
**Issue:** `_git_init(wt_root)` is called in the three existing `load_config` tests, but `load_config` no longer calls any git commands, making this dead setup.
**Fix:** Remove the `_git_init` calls and the `import subprocess` + `_git_init` helper entirely from this file.

### [NIT] `resolve_hub_path` "relative path" test uses an absolute path
**Location:** `plugins/mill/unit_tests/test-paths.py:50–57`
**Issue:** The third test constructs `parent / rel` which equals `tmp_path` — an absolute path — so it does not actually exercise `.resolve()` on a relative input as the plan intended.
**Fix:** Pass a truly relative path (e.g. `Path(".")` or `Path(tmp_path.name)` with `os.chdir`) to verify relative-to-absolute resolution. Alternatively rename the test comment to "assembled absolute path" to match what is actually being tested.

## Verdict

APPROVE — implementation is faithful to all four cards and shared decisions; two NITs only.