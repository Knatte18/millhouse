MILL_REVIEW_BEGIN
# Review: git-pr: gh pr create fails on GraphQL 5xx with no REST fallback documented

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-20
```

## Findings

### [BLOCKING:consistency] `head` field format contradicts itself across two decisions
**Section:** Decisions → rest-payload-construction vs. duplicate-pr-detection **Issue:** rest-payload-construction states `head` is "the bare branch name (no `owner:` prefix)... no cross-repo head format is needed," but duplicate-pr-detection's GET fallback command uses `-f head="<owner>:<branch>"` — the owner-prefixed form. The discussion never reconciles this; a plan writer reading the first decision's blanket "no owner: prefix" claim could "fix" the GET call to match, silently breaking the duplicate-PR lookup (GitHub's list-PRs `head` filter genuinely requires the `user:branch` form, unlike the create-PR `head` field — but the discussion doesn't say this). **Fix:** Add a sentence to duplicate-pr-detection (or rest-payload-construction) explicitly noting that GitHub's list-pulls endpoint requires `owner:branch` for `head` while create-pulls (same-repo) does not, so the two commands are correct as different, not inconsistent.

### [NIT:consistency] Pattern-matching rejected for trigger, then relied on for duplicate detection
**Section:** Decisions → rest-fallback-trigger vs. duplicate-pr-detection **Issue:** rest-fallback-trigger rejects matching GitHub's error text as "fragile... can drift across gh CLI versions and outage types," while duplicate-pr-detection is built entirely on a case-insensitive text match of GitHub's "already exists" message. The distinction (transient-outage text vs. a stable canonical 422 message) is real but never stated. **Fix:** One clause noting why the duplicate-PR message is treated as stable/canonical unlike the outage-text patterns rejected earlier, to preempt a plan-writer/reviewer flagging it as inconsistent.

## Verdict

REQUEST_CHANGES
One unreconciled contradiction in the `head` field format between two decisions risks a real implementation bug.
MILL_REVIEW_END
