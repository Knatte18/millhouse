MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] No test exercises the r8 first-match-wins root precedence
**Section:** Testing (interacts with Resolvability gate r8 fix) **Issue:** The r8 fix's entire point is that the new symbol-search filesystem walk must stop at the first root (git_root/root, then project_root/root-or-bare, then bare git_root) that produces any match, never union across roots — this is new code, not a reuse of `resolve_existing_paths` itself (Technical context: "the walk itself is new code"). The enumerated Testing list (12 bullets) has no case constructing a fixture where the search key exists under more than one of these root candidates to confirm first-match-wins over union; a regression back to the rejected v1 union behavior would pass every listed test. **Fix:** Add a Testing bullet mirroring the existing `test_git_root_threading_with_subfolder_cwd_clean` pattern (`plugins/mill/unit_tests/test-plan-validate.py:5291`, already exercises `root=`/`git_root=` together for a different check) — a fixture where a symbol's declaring file sits under `git_root/root` while an unrelated same-named symbol also exists outside `root` but under bare `git_root`, asserting the walk stops at the first producing root and the ambiguous/ignored second root's match is never consulted.

## Verdict

REQUEST_CHANGES
The r8 fix's core precedence behavior lacks a corresponding test case in the enumerated Testing section.
MILL_REVIEW_END
