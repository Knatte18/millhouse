MILL_REVIEW_BEGIN
# Review: _config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args

```yaml
duration_s: 163.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-19
```

## Findings

### [NIT:consistency] Rationale misstates worktree's declared type
**Section:** Decisions > `_treeguard.py` gets its own module-local guard (Rationale)
**Issue:** "the declared signature says `Path | None` either way" is inaccurate — `worktree: Path` has no `| None`; only `git_root: Path | None` does (confirmed at `_treeguard.py:37`). The code block three lines above is correct and unambiguous, so this is prose-only.
**Fix:** Reword to "both are Path-typed in the signature (only `git_root` also permits `None`)" or similar.

## Verdict

APPROVE
All file/line/behavior claims verified against source; decisions have rationale and rejected alternatives; testing and verify-command are correct.
MILL_REVIEW_END
