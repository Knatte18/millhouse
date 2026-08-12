MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [BLOCKING:scope] `_subprocess_util.py` missing from Context in Batch 1 Cards 1–2
**Location:** 01-parent-liveness-module.md, Card 1 (`Context: none`) and Card 2 (`Context: _archive_tag.py, _marker.py`).
**Issue:** Card 1's `check_liveness` and Card 2's `resolve_dead_parent` both call `_subprocess_util.run(...)` and read `.returncode`/`.stdout` off its result, but `_subprocess_util.py` — the file where that function lives — is not listed in either card's `Context:` or `Edits:`. Card 1 has zero Context files at all for a function it calls for the first time in this module. Card 2's `.stdout` extraction (step 5, "Parse the successful `show` output's stdout") is only inferable by analogy to `_archive_tag.py`'s own `_subprocess_util.run` usage, which is in Context but is not the file the function is defined in.
**Fix:** Add `plugins/mill/scripts/_subprocess_util.py` to `Context:` for Card 1 and Card 2 so the implementer can confirm the call signature and return-object shape (`.returncode`, `.stdout`, `check=` semantics) without cold-start exploration.

## Verdict

REQUEST_CHANGES
One Context-completeness gap in Batch 1 (Cards 1–2 call `_subprocess_util.run` without that file in Context).
MILL_REVIEW_END
