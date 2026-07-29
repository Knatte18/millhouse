MILL_REVIEW_BEGIN
# Review: Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4-6
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

All four bug scopes cross-checked against current source: `_archive_tag.py` push call sites (lines 65-68, 105-108, 154-161), `_review_plan.py`'s buggy `elif` gate (line 730) and the correct sibling pattern in `_review_discussion.py` (lines 251-252), `_test_registry.write_to` (line 58-68) and `_test_helpers.write_local_overlay` (line 305) and `_reviewers.load`'s fallback condition (lines 163-167), and `_implementer_common.py`'s unguarded success-path override (lines 1648-1660) plus `_attach_commit_sha` (line 385). All line numbers, call-site counts (11 for `write_to`, 7+6 for `write_local_overlay`, 14 inline in `test-reviewers.py`), and behavioral descriptions in Technical Context match the source exactly. mill-merge SKILL.md Step 6's current unconditional reads (`action`/`tag`/`moved_aside_to`, no `push_failed`) also confirmed. The 40-char/64-char SHA reconciliation (round-3 fix) is consistent across Scope, Decision, and Testing. The `reviewer_override`-gate carve-out (out of scope) matches the docstring at lines 657-666 and the independent `rounds != 0` check at line 718. No new inaccuracies, contradictions, or gaps found this round.

## Verdict

APPROVE
All four bug descriptions, decisions, and scope boundaries verified accurate against current source; no new findings.
MILL_REVIEW_END
