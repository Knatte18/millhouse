All key claims verified. Composing the review.

# Review: (A) — Add status_md to paths config + refactor 14 callsites

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-13
```

## Findings

### [NOTE] write_initial_status callers not listed in Technical Context
**Section:** Technical Context — `_spawn_core.py:716,720`
**Issue:** The discussion defers adding `cfg` to `write_initial_status`'s signature to planning, but the two callers that must be updated (`millpy-spawn.py:240`, `millpy-claim.py:300`) are listed only for their dry-run-print lines, not for this propagation. A plan writer following the Technical Context literally could miss these caller updates.
**Fix:** Add a parenthetical to the `_spawn_core.py` entry noting that both caller sites also need `cfg` threaded in — both files are already listed, so this is a one-line clarification.

### [NOTE] _review_code.py needs import _paths — not mentioned
**Section:** Technical Context — `_review_code.py:220`
**Issue:** `_review_code.py` imports `resolve_path` from `_review_common`, not from `_paths`. Replacing line 220 with `_paths.status_path(...)` requires adding `import _paths` — not called out in the fix description.
**Fix:** Note the required import addition alongside the call-site substitution in the Technical Context entry for `_review_code.py:220`.

## Verdict

APPROVE
All core decisions are made, source claims verified, testing strategy concrete. Two NOTEs flag callsite-propagation gaps that could trip up the plan writer but do not block planning.