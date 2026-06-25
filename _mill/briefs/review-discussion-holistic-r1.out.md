MILL_REVIEW_BEGIN
# Review: Fix pre-existing unit-test failures, CRLF cleanliness false-positive, and review false-BLOCKING on Go

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-25
```

All six fixes are precisely anchored and verified against source: brief-path bug present identically in all three CLIs (plan L151 / code L150 write `resolve_task_path(project_root=resolve_hub_path(), ...)` while `git_root` is computed-but-unused at L103/L102); `worktree_snapshot_guard` all-or-nothing rule confirmed (`_review_common.py` L163); `is_ancestor(path, ancestor_sha, descendant_sha)` exists at `_pygit2_util.py` L211 with the exact cited signature; `_is_benign_windows_cleanup` failure_markers `["fail", "panic:", "build failed"]` confirmed (L189-193); `capture_snapshot` writes utf-8 with no `newline=""` (`_cleanliness.py` L24) and `_is_formatter_drift_only` uses bare `git diff`/`diff -w` without `--ignore-cr-at-eol` (L263/L274); code-finalize `--round` guard (L174-176) vs discussion auto-discover (L121-123) asymmetry confirmed. Scope in/out explicit, four decisions each carry rationale + rejected alternatives, constraints acknowledged, per-area testing strategy named with a whole-suite green gate. Plan-ready.

## Findings

### [NOTE] Go marker `FAIL\t` vs `\t` ambiguity for plan writer
**Section:** Technical context (Go review false-BLOCKING)
**Issue:** The marker set mixes `--- FAIL`, bare `FAIL` summary line, and `FAIL\t` — but `FAIL\t` written literally (backslash-t) would not match a real tab; the plan writer must decide whether to match a tab character, the literal `FAIL\t` go-test prefix, or a regex.
**Fix:** State the exact match semantics (e.g. line starts with `FAIL` followed by whitespace/tab, vs `--- FAIL` per-test) so the regression test and impl agree on the token shape.

## Verdict

APPROVE
Discussion is accurate, complete, and decisive; one non-blocking marker-semantics note for the plan writer.
MILL_REVIEW_END
