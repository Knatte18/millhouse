All three `finalize` signatures confirmed consistent with `raw_text` at positional index 2. Everything checks out across both batches. Final review below.

```markdown
MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-06
```

## Findings

No findings.

Verified end-to-end:
- Batch 1 (`html.unescape` at all four read sites): `_implementer_common.finalize_from_output` (`_implementer_common.py:849`), `millpy-review-code.py:185`, `millpy-review-discussion.py:146`, `millpy-review-plan.py:187` all wrap the `--agent-output` read exactly as specified. `import html` present and alphabetically ordered in all four files, matching existing import-style convention.
- New unit tests confirmed correct and non-trivially wired: `test-implementer-common.py` Case 63 patches `_forward_output` and asserts on the captured first positional arg (fully unescaped). `test-review-finalize.py`'s three new `test_review_*_finalize_unescapes_html_entities` functions correctly avoid the swallowed-`AssertionError` trap the plan called out — the boolean comparison is the function's return value, read via `call_args.args[2]` outside the `try` block. Verified `raw_text` is genuinely positional index 2 in all three backend `finalize()` signatures (`_review_code.py:508`, `_review_discussion.py:122`, `_review_plan.py:538`) — the index used in the tests is correct.
- Batch 2 doc edits all present and accurate: mill-go step 6 (`SKILL.md:152`) covers both #606 (`--review-file` re-pass requirement) and #599 (600000ms timeout recommendation, scoped to fix-CLI finalize only) in one paragraph as directed. mill-start `## Entry` has a new Step 0 (`SKILL.md:45`) mirroring mill-go's Step 0 pattern, forcing `mill:conversation` load unconditionally before steps 1-3. `mill:workflow`'s `## Anti-patterns` has a new item 3 (`SKILL.md:42`) with the Skill-tool staleness rule and an incident-#596 closing line, matching the style of items 1-2.
- No out-of-plan files: exactly the four `import html` sites plan-listed exist; no stray edits found. No cross-batch or shared-decision violations -- batches are independent and each stays within its own scope.

## Verdict

APPROVE
All cards in both batches correctly implemented; tests avoid the known assertion-swallowing pitfall; no out-of-plan or duplicated code found.
MILL_REVIEW_END
```
