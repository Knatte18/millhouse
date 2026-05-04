# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure — 05-review-code-integration

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 05-review-code-integration
date: 2026-05-04
```

## Findings

### [BLOCKING] `holistic_timeout` config key missing; Card 21 will KeyError
**Step:** Card 21
**Issue:** Card 21 uses `cfg["llm"]["holistic_timeout"]` directly, but `wiki/config.yaml` defines only `bulk_timeout`, `tool_use_timeout`, and `implementer_timeout`. No card in B05 adds `holistic_timeout`, and the batch declares itself independent of B04 (review-plan-integration), so there is no guaranteed prior batch to add it. The production code will raise `KeyError` on every holistic review call.
**Fix:** Card 21 must either (a) also modify `wiki/config.yaml` — add `holistic_timeout: 1800` alongside `bulk_timeout` and update the `Modifies:` field — or (b) change the access to `cfg["llm"].get("holistic_timeout", cfg["llm"]["bulk_timeout"])` to degrade safely if the key is absent.

### [NIT] Card 22 tests (a) and (b) require stub exception-raising not present in current stub
**Step:** Card 22
**Issue:** Tests (a) and (b) require seeding `LLMError` as a response from `_reviewer_test_stub.run`, but the current stub's `seed()` accepts only `list[tuple[str, str]]`; raising an exception on pop is not supported. Card 22 only modifies the test file, not the stub.
**Fix:** Confirm content-helpers (B01) extends `seed()` to accept `BaseException` entries and updates `run()` to `raise` them instead of returning; if it does not, Card 22 must add that capability to the stub's `Modifies:` field.

## Verdict

REQUEST_CHANGES — one blocking: `holistic_timeout` is absent from `wiki/config.yaml` and no card in this batch adds it.