# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure — 05-review-code-integration

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 05-review-code-integration
date: 2026-05-04
```

## Findings

### [BLOCKING] `holistic_timeout` absent from `wiki/config.yaml` and unowned
**Step:** Card 21
**Issue:** Card 21 reads `cfg["llm"]["holistic_timeout"]` at runtime, but `wiki/config.yaml` only defines `bulk_timeout`, `tool_use_timeout`, and `implementer_timeout`; Card 21's Modifies list does not include `wiki/config.yaml`, and B05's `depends-on` does not list `review-plan-integration` (the likely adder), so there is no guarantee the key exists when B05 executes.
**Fix:** Either add `wiki/config.yaml` to Card 21's Modifies and insert `holistic_timeout: <value>` there, or add `review-plan-integration` to B05's `depends-on` with an explicit note that B04 owns the config addition; Card 22(d) injects the key in-memory (`cfg["llm"]["holistic_timeout"] = 1800`), which masks the production-path KeyError in tests.

### [NIT] Stub exception-seeding mechanism undocumented for Card 22(a)/(b)
**Step:** Card 22
**Issue:** The card instructs "seed the stub to raise `LLMError` on first call" but the stub's `seed()` only accepts `(text, session_id)` tuples; no exception-sentinel path exists in the current stub, and Card 22 does not modify `_reviewer_test_stub.py`.
**Fix:** Add a sentence stating that B01 (content-helpers) extends `stub.seed()` to accept `LLMError` instances as sentinels — consistent with the shared "reviewer-timeout-kwarg" decision's claim that the stub is extended — so the implementer knows where this capability comes from and does not duplicate the change.

## Verdict

REQUEST_CHANGES
One blocking gap: `holistic_timeout` is read but never added to config and has no declared batch owner.