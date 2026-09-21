MILL_REVIEW_BEGIN
# Review: mill-plan/mill-start planning-process gaps, round 2

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-21
```

## Findings

### [BLOCKING:consistency] Testing section omits disposition for four of eight fixes
**Section:** Testing
**Issue:** Only #1083, #1054a, #1056 get concrete test-extension bullets, and only #1084+#1083 (bullet 4) and #1086 (bullet 5) get an explicit "no automated test, verify by reading rendered text" disposition. #1076 (batch-sizing sentence + fix-table row), #1063 (discussion_sha `-C`/`:./` git-command fix, three call sites), #1045 (heading rename), and #1054b (the new "finalize advances the round" paragraph) have no stated testing disposition at all — not even the prose-only carve-out #1086 explicitly received.
**Fix:** Add each of #1076/#1063/#1045/#1054b to bullet 4 or bullet 5 (whichever fits), or add an explicit sixth bullet giving #1063 in particular — an actual git-command construction, not pure prose — a "verify by running the command in both flat and nested layout" disposition rather than silence.

### [NIT:scope] Ambiguous anchor for 1054b's new paragraph placement
**Section:** Decision 1054-finalize-advances-round
**Issue:** "immediately before step 2's dispatch instructions" is ambiguous against the current file: step 2 opens with "Waiting is never a decision point" / dispatch-mode resolution boilerplate before the actual Agent-mode-vs-subprocess branching text begins several paragraphs later — a plan writer could reasonably place the new paragraph at either point.
**Fix:** Name the exact anchor sentence/heading the new paragraph must precede (e.g. "immediately before the 'If `agent` (Claude provider only):' branch").

## Verdict

REQUEST_CHANGES
Testing coverage is inconsistent across the eight fixes; the rest is well source-grounded.
MILL_REVIEW_END
