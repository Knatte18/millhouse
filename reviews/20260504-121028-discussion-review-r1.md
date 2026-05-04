I have enough source context. Writing the review now.

# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md
date: 2026-05-04
```

## Findings

### [GAP] `_invoke` restructuring for rate-limit detection unspecified
**Section:** Decision `llm-rate-limit-error-class` / Technical Context `_llm_claude.py`
**Issue:** `_invoke` raises `LLMError` (or `LLMSessionError`) before calling `_parse_stream_json` when `result.returncode != 0` (lines 218–224 of `_llm_claude.py`). The decision only says "extend `_parse_stream_json`" — but `_parse_stream_json` is never called on non-zero exit, so no rate-limit event can be observed from it. The testing section confirms `_invoke` must be the call-site that raises `LLMRateLimitError` (test: "mock `_subprocess_util.run` to return non-zero exit + this stdout, expect `LLMRateLimitError`"), but the Bonus test also says `_parse_stream_json` alone returns `(text, session_id)` without raising — leaving the integration point (who observes the rate-limit flag, and via what mechanism) unresolved.
**Fix:** State explicitly how `_invoke` is restructured: e.g., always call `_parse_stream_json` before the exit-code branch, return an extended tuple `(text, sid, rate_limit_observed)`, and raise `LLMRateLimitError` when non-zero exit + `rate_limit_observed`; or describe an alternate integration path.

### [GAP] Total-fail check in `_review_plan.run` blocks ERROR-only JSON output
**Section:** Decision `error-only-aggregate-retry-in-skill`
**Issue:** `_review_plan.run` lines 529–534 raise `ReviewError("All sub-reviews failed: ...")` when all reviews are ERROR. The CLI catches `ReviewError`, prints to stderr, and exits 1 with no JSON. SKILL.md step 4.5 is specified to fire "after step 4c parses the JSON envelope" and check `all(r["verdict"] == "ERROR" for r in result["reviews"])` — impossible to evaluate with no JSON on stdout. The decision says "backend stays stateless" but never says to remove or transform the total-fail check, leaving the ERROR-only retry in the SKILL.md dead code.
**Fix:** State explicitly that the total-fail check must be removed (or replaced with a return of a valid `ReviewResult` with `REQUEST_CHANGES` verdict and all-ERROR `reviews[]`), so the all-ERROR round produces parseable JSON the orchestrator can act on.

### [NOTE] `_plan_validate` non-existent-path check will false-positive on Deletes tokens
**Section:** Technical Context `_plan_validate.py`
**Issue:** After `parse_batch_refs` is extended to return `Deletes:` tokens, `_check_non_existent_path` (which calls `parse_batch_refs`) will flag intentionally-deleted files as `non-existent-path` errors when they are absent from disk. The discussion says "extend the non-existent-path check to know about `Deletes:`" but does not specify the mechanism — whether `compute_deletes_union()` is passed as a new parameter, or another guard is used.
**Fix:** State whether `deletes_union` (from `compute_deletes_union`) should be added as a parameter to `_check_non_existent_path` and how it gates the error (skip token if it is in `deletes_union`).

## Verdict

GAPS_FOUND
Two structural gaps — rate-limit `_invoke` integration and removal of the total-fail check — would produce broken implementations without explicit guidance.