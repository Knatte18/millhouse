I've verified all plan cards against the source files. Here is my review.

MILL_REVIEW_BEGIN
# Review: Fix mill-start instruction gaps, baseline long-path on Windows, and language skill tooling reliability — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-09
```

## Findings

### [NIT] Card 4 test must use a temp dir for project_root
**Location:** Batch 2 / Card 4
**Issue:** `compute_baseline` unconditionally runs `scratch_dir.mkdir(parents=True, exist_ok=True)` on `project_root/.scratch` (`_verify_baseline.py:148-149`), so a bare "throwaway" `project_root` does real filesystem work and can create stray dirs or error — contradicting the card's "no real filesystem work" claim.
**Fix:** Specify that `project_root` (and `git_root`) be a `tempfile.TemporaryDirectory` as in `test-worktree.py`, so the `.scratch` mkdir lands in an auto-cleaned temp path.

### [NIT] Card 1 Context omits `_paths.py`
**Location:** Batch 1 / Card 1
**Issue:** Requirements name `_paths.resolve_git_root` / `_paths.resolve_wiki_path`, whose file is not in `Context:`/`Edits:`. Mitigated because both signatures already appear inline in the edited `SKILL.md` `signature:` lines, so no cold-start exploration is forced — but it technically trips the context-completeness rule.
**Fix:** Optionally add `plugins/mill/scripts/_paths.py` to Card 1 `Context:`; otherwise acceptable given the inline signatures.

## Verdict

APPROVE
Plan is faithful, well-scoped, and source-accurate; only two minor test/context NITs.
MILL_REVIEW_END