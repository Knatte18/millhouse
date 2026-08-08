MILL_REVIEW_BEGIN
# Review: _plan_validate.py: hardcoded tag-name check and fenced-code-block-unaware card parsing

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: uncertain -- best-effort guess "Claude Sonnet 4.5"-class; harness env metadata reports "Sonnet 5"
reviewed_file: _mill/discussion.md
date: 2026-08-08
```

## Findings

### [GAP] Loop breaks at first tagged edited file, not all
**Section:** Decisions/bug1-any-tag-match-semantics + Technical context `_check_verify_excludes_edited_tagged_test`
**Issue:** Verified against source (lines 2059-2068): the loop over `edited_test_tokens` sets `tagged_token` and `break`s at the *first* tagged file found, then checks only that file's tags against `verify:`. Generalizing to per-file custom tag *sets* (e.g. a batch editing both a `scout`-tagged and a `smoke`-tagged test) means a `verify:` command satisfying only the first-found file's tag would silently pass with 0 findings even though the second tagged file is excluded from the build -- reproducing bug 1's exact false-negative class inside the fix itself.
**Fix:** Decide explicitly whether the generalized check must validate *all* edited tagged files (union of required tags) or document/accept the single-file limitation as a scoped-out case.

### [GAP] New denylist duplicates and diverges from existing precedent
**Section:** Decisions/bug1-tag-discovery-via-denylist
**Issue:** `plugins/mill/scripts/_implementer_common.py` (lines 1014-1017) already has `_GO_BUILD_TAG_GOOS`/`_GO_BUILD_TAG_GOARCH` for an analogous purpose, deliberately small/non-exhaustive, with an explicit safe-degrade rationale: an unrecognized real GOOS/GOARCH value falls through to "treat as custom tag" harmlessly there. The discussion's new denylist is a much larger, independently-authored enumeration with the opposite failure direction: an unrecognized-but-real GOOS/GOARCH value here would be wrongly classified "custom," producing exactly the new false positive the decision's own rationale says must be avoided (`//go:build linux` requiring `-tags linux`).
**Fix:** Either reuse/extend the existing `_implementer_common.py` sets for consistency, or explicitly decide+justify why this check needs a different, larger list and different fallback-safety direction than the existing precedent in the same codebase.

### [NOTE] Call-site count in Technical context is off by one
**Section:** Technical context, `_parse_cards`
**Issue:** States "7 call sites ... (lines 750, 838, 872, 1503, 1715, 2511, plus its own definition)" -- grep confirms exactly 6 call sites at those lines; the definition isn't a call site, so the count is inaccurate (harmless to the fix itself).
**Fix:** Correct to "6 call sites."

### [NOTE] Generalized functions/docstrings still say "integration"
**Section:** Scope / Technical context (bug 1)
**Issue:** `_go_file_is_integration_tagged`, `_verify_command_has_integration_tag`, and the module docstring (lines 38-41: "...integration...-tagged file... matching -tags ...integration...") retain literal "integration" wording even though the check is being generalized to arbitrary custom tags. Scope doesn't decide whether these get renamed/reworded.
**Fix:** Note in Scope whether function names/docstrings are renamed as part of this task or left as legacy names.

## Verdict

GAPS_FOUND
Multi-tagged-file loop-break gap and denylist-precedent divergence are unresolved correctness risks in bug 1's generalization.
MILL_REVIEW_END
