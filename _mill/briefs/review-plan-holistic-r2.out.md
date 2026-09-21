MILL_REVIEW_BEGIN
# Review: Misc infra/wiki/PR/self-hosting reliability bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

### [BLOCKING:scope] Card 3 Context omits `_gh_issues.py` despite Requirements naming `detect_repo`
**Location:** Batch 2 (`02-pr-state-and-cache-freshness.md`), Card 3.
**Issue:** Requirements direct the implementer to add `import _gh_issues` and call `_gh_issues.detect_repo(Path(cwd))`, and assert a specific type-hint fact about it ("`detect_repo` expects a `Path | None`") — verified against `plugins/mill/scripts/_gh_issues.py` line 41, `def detect_repo(git_root: Path | None = None) -> str:`, so the claim itself is accurate, but the fact that Requirements must state it at all shows the implementer needs this file's contents. Card 3's `Context:` list is only `plugins/mill/scripts/_subprocess_util.py`; `_gh_issues.py` is absent from both `Context:` and `Edits:`.
**Fix:** Add `plugins/mill/scripts/_gh_issues.py` to Card 3's `Context:` list.

## Verdict

REQUEST_CHANGES
Card 3 (Batch 2) omits `_gh_issues.py` from Context despite Requirements naming `detect_repo` from it.
MILL_REVIEW_END
