MILL_REVIEW_BEGIN
# Review: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [GAP] Reused line-based parsers can truncate a fence quoting markdown structure
**Section:** Technical context (reuse of `_parse_cards`/`_extract_requirements_text`) / Testing
**Issue:** `_parse_cards` terminates a card on any line starting with `### ` and `_extract_requirements_text` stops at any line matching `^-\s*\*\*[A-Za-z]+:\*\*`, both operating on raw lines with no fence-awareness; the proposed fence regex (`r"```[^\n]*\n(.*?)```"`) is also non-greedy and stops at the first `` ``` `` it meets. This is exactly the scenario the task targets — docs-editing cards quoting verbatim markdown source, which plausibly contains headings or bold-labeled bullets (`- **X:**`) or nested fences — so the very fences most likely to trigger the original bug can be silently mis-extracted (truncated) by the reused helpers, producing a false negative on the class of input the check exists to catch.
**Fix:** Add a Failure-modes/Testing note (and ideally a dirty test case) covering a Requirements fence whose quoted body contains a `### `-prefixed line or a `- **Field:**`-shaped line, confirming the check still fires or explicitly documenting this as an accepted limitation.

### [NOTE] No tie-break stated when dedented fence matches more than one `Edits:` file
**Section:** Technical context (`match-target-edits-only`) / Testing
**Issue:** When a card's `Edits:` lists multiple files and the dedented fence content is a substring of more than one, the discussion doesn't say which file's path is reported in the error's `path` field, and no test covers this.
**Fix:** State a deterministic tie-break (e.g. first match in `Edits:` declaration order) so implementation and tests are unambiguous.

## Verdict
GAPS_FOUND
One GAP: reused line-based parsing helpers may truncate exactly the quoted-markdown-structure fences this check targets.
MILL_REVIEW_END
