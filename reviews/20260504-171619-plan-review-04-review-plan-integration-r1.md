# Review: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure — 04-review-plan-integration

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 04-review-plan-integration
date: 2026-05-04
```

## Findings

### [BLOCKING] Card 18 omits `cfg["llm"]` fixture update

**Step:** Card 18 (Tests), coordinating with Card 14  
**Issue:** Card 14 reads `cfg["llm"]["bulk_timeout"]` and `cfg["llm"]["holistic_timeout"]` unconditionally near the top of `run()`. All existing test fixtures (tests 1–15) use a cfg built by `_make_plan_fixture` that has no `"llm"` key; every existing test will raise `KeyError` after Card 14 lands, violating Card 18's own "existing tests must continue to pass" requirement.  
**Fix:** Card 18's Requirements must explicitly state: update `_make_plan_fixture` to include `"llm": {"bulk_timeout": None, "holistic_timeout": None}` in the returned cfg (None passes through to reviewer defaults), so the existing suite stays green and test (d) can override the values it needs to assert.

---

### [NIT] Tests 6/7 break when B01 adds `timeout` to stub kwargs

**Step:** Card 18 (Tests), interaction with `_reviewer_test_stub` changes from B01  
**Issue:** Tests 6 and 7 assert `retry_kwargs == {"session_id": "sid-1", "resume": True}` (exact equality). After B01's Card 7 adds `timeout: int | None = None` to `stub.run()` and captures it in the kwargs dict, the actual dict becomes `{"session_id": "...", "resume": True, "timeout": None}`, causing both assertions to fail.  
**Fix:** Card 18 Requirements should list "update tests 6 and 7 to include `"timeout": None` in the expected kwargs dict."

---

### [NIT] Test (a) mechanism for LLMError not specified

**Step:** Card 18 test (a) — all-ERROR returns valid ReviewResult  
**Issue:** "seed the stub to raise `LLMError` for every call (use a stub-callable that raises)" does not say how — `stub.seed()` only accepts `(text, session_id)` tuples; neither the stub's current API nor B01's additions include exception-seeding.  
**Fix:** Clarify the intended mechanism: monkey-patch `stub.run = lambda *a, **kw: (_ for _ in ()).throw(LLMError("…"))` (or a named function), restoring the original in a `finally` block.

## Verdict

REQUEST_CHANGES  
One blocking gap: `cfg["llm"]` absent from test fixtures breaks all existing tests after Card 14.