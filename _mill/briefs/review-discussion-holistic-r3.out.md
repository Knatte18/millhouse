MILL_REVIEW_BEGIN
# Review: Review prompt/output file listings resolve plan-relative paths to absolute before display, instead of keeping them relative

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] `build_reattached_section` call site missing from Scope/Technical context
**Section:** Scope / Technical context / Testing.
**Issue:** `_review_common.py:1357` `build_reattached_section()` calls `bulk_files(file_paths)` (line 1368) with no `roots` arg, emitting `--- FILE: <abs> ---` delimiters. It is called live from `_review_plan.py:298`, `_review_plan.py:1120`, and `_review_code.py:770` inside the NEED_CONTEXT resume-retry path (a separate `retry_prompt`, not the `artefact_section`/`prompt_text` covered by the enumerated sites). Scope's bullet 3 and Technical context's caller inventory enumerate only 5 assembly sites (4 in `_review_plan.py`, 1 in `_review_code.py`); this 6th `bulk_files` call site is absent from both, and from the flow-level test plan (items 7-9 assert only on the primary `prompt_text`, never on the resume `retry_prompt`). Post-fix, the manifest above and the tool-use `read_list` will be relative while the NEED_CONTEXT re-attachment echoes absolute paths in the same conversation — exactly the "actively confusing" split the `tool-use-mode-relative` decision warns against, and the `keyword-only-optional-roots` decision's own stated guard (flow-level prompt assertions) will not catch it since that site is untested.
**Fix:** Add `build_reattached_section` to Scope/Technical context as a 6th call site requiring the new `roots: DisplayRoots | None` parameter (threaded from the two `_review_plan.py` NEED_CONTEXT branches and the one in `_review_code.py`), and add a flow-level test asserting the resume `retry_prompt` also carries no absolute-root prefix.

## Verdict

REQUEST_CHANGES
Discussion misses a sixth `bulk_files` call site (NEED_CONTEXT re-attachment) that would still leak absolute paths.
MILL_REVIEW_END
