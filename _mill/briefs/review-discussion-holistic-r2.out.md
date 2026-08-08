MILL_REVIEW_BEGIN
# Review: _plan_validate.py: hardcoded tag-name check and fenced-code-block-unaware card parsing

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-08
```

## Findings

### [GAP] Multi-custom-tag-per-file message selection is nondeterministic and untested
**Section:** Technical context / `bug1-check-every-tagged-file-not-just-first`; `bug1-message-uses-discovered-tag`
**Issue:** `_go_file_custom_tags` is explicitly typed to return `set[str]` (per `bug1-rename-integration-specific-identifiers`), but the finding message uses "its first discovered tag" (Technical context, per-file loop) — Python set iteration order for strings is not stable discovery order and isn't guaranteed deterministic across runs. `bug1-any-tag-match-semantics`'s own motivating example (`//go:build scout && smoke`, one file with 2+ custom tags) has no corresponding TDD candidate in Testing, so this code path is never exercised.
**Fix:** Promote "first discovered tag for the message" to a proper `### Decision:` specifying a deterministic rule (e.g. `sorted(tags)[0]`, or preserve `re.findall`'s source-order via a list before the denylist-filter step), and add a single-file multi-composed-tag test case (clean + dirty) to the Bug 1 Testing list.

## Verdict

GAPS_FOUND
One unresolved determinism/coverage gap in the multi-custom-tag-per-file message path.
MILL_REVIEW_END
