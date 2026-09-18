MILL_REVIEW_BEGIN
# Review: mill-go-base: orchestration robustness gaps

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-18
```

## Findings

### [BLOCKING:consistency] Scope "Out" bullet contradicts the 1031 Decision on millpy-implement.py
**Section:** `## Scope` / Out (bullet "No CLI-internals changes to `millpy-review-discussion.py` / `millpy-review-code.py` / `millpy-implement.py` beyond what #1005 needs (none — ...)") vs `### 1031-parallel-entry-baseline`.
**Issue:** Read in isolation (as Out-of-scope bullets normally are), this reads as a task-wide freeze on `millpy-implement.py`'s CLI surface, but the very next Decision block mandates adding a new `--module-wide-only` flag to `millpy-implement.py --stage baseline` for #1031 — a genuine CLI-internals change to the same file the Out bullet names.
**Fix:** Reword the bullet to scope the "no changes" clause explicitly and only to #1005 (e.g. "#1005 needs no CLI-internals changes to these three files — its fix is a `_status.py` helper plus one call-site edit; `millpy-implement.py` still gains the `--module-wide-only` flag, but that's #1031's Decision, not #1005's"), so a plan writer skimming Scope alone doesn't need to cross-reference Decisions to avoid a false constraint.

## Verdict

REQUEST_CHANGES
One BLOCKING: reword the Out bullet naming millpy-implement.py so it doesn't read as contradicting the 1031 Decision.
MILL_REVIEW_END
