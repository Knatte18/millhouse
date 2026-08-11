MILL_REVIEW_BEGIN
# Review: Surface reviewer time/tool-call cost + a review-summary command

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Error-path calls lose duration_s entirely
**Section:** Decisions -- "Reviewer-call return contract becomes a small dataclass" / "Duration for multi-call rounds: sum across every retry, at every layer"
**Issue:** `_invoke()` (`_llm_claude.py` lines ~350-400) computes `dt` but on failure raises `LLMError`/`LLMSessionError`/`LLMRateLimitError` instead of returning (verified against `_llm_common.py`: these exceptions carry only a message string, no duration field). `_review_code.py::run()`'s `except LLMError` branches (lines 678-692, 744-758) build an `ERROR`-verdict `reviews[...]` entry with no `dt` available, and never call `finalize()`, so the `--duration-s` persistence path is never reached for these rounds either. The dataclass-return Decision and the retry-summation Decision both only describe the success path.
**Fix:** Add a Decision for surfacing duration on the exception path (e.g. attach `duration_s` to the raised error, or have callers time the call themselves and merge it into the synthetic `ERROR` review entry) -- a timed-out or rate-limited round is exactly the highest-cost case this task exists to make visible, and today's design silently drops it.

### [BLOCKING:design] Caller-enumeration method is still unreliable after the r1 fix
**Section:** Technical context -- "`_reviewer_single.run()` ... Confirmed callers of `run_bulk`/`run_tool_use`/`_reviewer_single.run`, re-grepped across the whole repo"
**Issue:** The r1-added whole-repo re-grep still names only `bench-reviewers.py` as the fourth caller needing lockstep updates. `plugins/mill/integration_tests/smoke-llm-claude.py` (unpacks `text, sid = _llm_claude.run_bulk(...)` / `run_tool_use(...)` at lines 84, 127, 174, 194) and `smoke-llm-gemini.py` (same pattern against `_llm_gemini.run_bulk`/`run_tool_use` at lines 72, 114, 151) call the provider modules directly and unpack bare 2-tuples exactly like `bench-reviewers.py` did -- neither file is named anywhere in discussion.md, and both sit outside `run-all.py`'s coverage, so they would silently break under the new dataclass contract.
**Fix:** Per the "unreliable enumeration method is one design finding, not N scope findings" rule: don't just add these two files to the list -- state a Decision for a reliable enumeration method (e.g. grep for each provider module's public function names repo-wide, or an import-graph check run at implementation time) rather than trusting another one-off manual grep pass that has now missed callers twice.

## Verdict

REQUEST_CHANGES
Duration is lost on every error/timeout call path, and the caller enumeration is still incomplete after one prior widening pass.
MILL_REVIEW_END
