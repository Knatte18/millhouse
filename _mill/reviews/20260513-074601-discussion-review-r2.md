# Review: (A) — Central safe-rmtree helper + ban direct rmtree

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-13
```

## Findings

### [NOTE] POSIX walk described as no-op but symlink test contradicts that
**Section:** `### Platform behaviour` vs. `## Testing`
**Issue:** Platform behaviour says "reparse-walk step is a no-op on POSIX" but the test list includes `test_strips_symlink_inside_tree (POSIX)`, implying the `entry.is_symlink()` branch runs on POSIX. The Reparse-point detection section is consistent with the test; the Platform behaviour wording is not.
**Fix:** Clarify that only the junction-specific detection (`isjunction`/`st_file_attributes`) is guarded by `os.name == "nt"`; the symlink branch (`entry.is_symlink()`) runs cross-platform.

### [NOTE] test-cleanup.py:481 false positive in callsite analysis
**Section:** `## Technical context` — callsites to migrate
**Issue:** The analysis flags `unit_tests/test-cleanup.py:481` as needing "Whitelist or reword," but the actual text at that line is `# … worktree NOT rmtree'd —` which does not match `shutil\.rmtree`, `rmdir\s+/s`, or `os\.removedirs`. Verified by source read.
**Fix:** Remove the entry from the callsite list; no whitelist entry or rewording is needed for this file.

## Verdict

APPROVE — design is sound and complete; two NOTEs are cosmetic and do not block plan writing.