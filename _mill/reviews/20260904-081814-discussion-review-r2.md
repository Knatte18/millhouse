MILL_REVIEW_BEGIN
# Review: mill-plan: review-round cap and skip-check threading bugs

```yaml
duration_s: 221.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [NIT:scope] `--approve` addition leaves usage-hint text unaddressed
**Section:** #948 decision / Step 0.5 argument parsing. **Issue:** Adding `--approve` to Step 0.5's token walk isn't paired with updating the frontmatter `argument-hint: "[--revise]"` or the hard-coded `usage: /mill-plan [--revise]` halt string, both of which become stale once `--approve` is a real token. **Fix:** Note in the decision that both surfaces should be extended (e.g. `[--revise|--approve]`) as part of the same edit.

### [NIT:consistency] "Waive remaining BLOCKINGs" decision lacks its own `### Decision:` heading
**Section:** #970 decisions. **Issue:** Unlike every sibling decision, the "Also document a live 'waive remaining BLOCKINGs at cap' instruction" item is a plain `- Decision:` bullet nested under the precedence-decision heading rather than its own `###` heading, despite being a substantively distinct decision with its own rationale/rejected pair. **Fix:** Give it a dedicated `### Decision:` heading for consistency with the file's own structural convention.

## Verdict

APPROVE
Round-1 BLOCKING precedence gap is resolved; all line-number, signature, and CLI-flag claims verified against source.
MILL_REVIEW_END
