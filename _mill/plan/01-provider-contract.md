# Batch: provider-contract

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "provider-contract"
number: 1
cards: 9
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-llm-claude.py test-llm-gemini.py test-reviewers.py
depends-on: []
```

## Batch Scope

Introduces `ReviewerCallResult` and flips every reviewer-call *provider* to return it: both LLM
provider modules and the in-process test stub. `_reviewer_single.run()` gets a deliberately
temporary two-line unwrap so its own return shape stays `(text, session_id)` for this batch only —
batch 2 removes that adapter and converts the three review backends. Nothing outside
`plugins/mill/scripts/_llm_*.py`, `_reviewer_test_stub.py`, `_reviewer_single.py` and their tests
changes here; the review backends still see today's 2-tuple.

The externally-visible interface batch 2 consumes: `_reviewer_single.run()` will return
`ReviewerCallResult` once the adapter is deleted, and the three metric fields
(`duration_s`, `tool_calls`, `cost_usd`) are already populated by both providers by the end of this
batch.

## Cards

### Card 1: `ReviewerCallResult` + duration-carrying exceptions in `_llm_common.py`

- **Context:**
  - `plugins/mill/scripts/_reviewer_single.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `from __future__ import annotations` is already present; add `from dataclasses import dataclass`
  and define a module-level dataclass `ReviewerCallResult` with exactly these fields, in this order:
  `text: str`, `session_id: str`, `duration_s: float | None = None`, `tool_calls: int | None = None`,
  `cost_usd: float | None = None`. Its docstring must state that `tool_calls` and `cost_usd` are
  `None` wherever a provider or dispatch mode cannot supply them (gemini always; the claude psmux
  branch always; the claude subprocess branch when the installed CLI's `"result"` event omits the
  corresponding field), and that `duration_s` is wall-clock seconds for the whole call including any
  internal retry.
  Give `LLMError` an `__init__(self, message: str, *, duration_s: float | None = None)` that calls
  `super().__init__(message)` and assigns `self.duration_s = duration_s`, so `str(exc)` is unchanged
  and every existing single-argument raise site keeps working with `duration_s` defaulting to `None`.
  `LLMSessionError` and `LLMRateLimitError` inherit it unchanged — do not give them their own
  `__init__`. Update the module docstring's opening line to say it also defines the shared
  reviewer-call return dataclass, not only the exception hierarchy.
- **Commit:** `feat(llm): add ReviewerCallResult and duration-carrying LLM exceptions`

### Card 2: count tool-use blocks and read cost in `_parse_stream_json`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Change `_parse_stream_json`'s return type from `tuple[str, str | None]` to
  `tuple[str, str | None, int | None, float | None]`, returning
  `(final_text, session_id, tool_calls, cost_usd)`.
  Inside the existing per-line loop, in the `event_type == "assistant"` branch, count every content
  block that `isinstance(block, dict) and block.get("type") == "tool_use"` into a running
  `tool_use_blocks` integer (counted across every `assistant` event, additively — do not reset per
  event, and do not make the count conditional on the event also carrying text blocks).
  In the `event_type == "result"` branch, additionally read `obj.get("num_turns")` into a
  `native_turns` variable when it is an `int` (and not a `bool`), and `obj.get("total_cost_usd")`
  into `cost_usd` when it is an `int` or `float` (and not a `bool`), coercing to `float`.
  After the loop, `tool_calls` is `native_turns` when that is not `None`, else `tool_use_blocks`
  (the block count is the fallback, the native field wins when both are present). The
  `raise LLMError("claude returned no content")` behaviour when `final_text is None` is unchanged.
  Update the docstring to document all four returned values and the native-field-wins precedence.
  The `_scan_rate_limit` function is untouched.
- **Commit:** `feat(llm): count tool_use blocks and read total_cost_usd in stream-json parsing`

### Card 3: `_invoke` returns `ReviewerCallResult` with cumulative duration

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Import `ReviewerCallResult` alongside the existing `LLMError, LLMSessionError, LLMRateLimitError`
  import from `_llm_common`.
  Change `_invoke`'s return annotation to `ReviewerCallResult`.
  psmux branch: every `raise LLMError(...)`/`raise LLMSessionError(...)` in that branch passes
  `duration_s=time.monotonic() - start`; the success return becomes
  `ReviewerCallResult(text=text, session_id=session_id, duration_s=dt, tool_calls=None, cost_usd=None)`.
  Subprocess branch: leave the existing first-attempt `dt = time.monotonic() - start` computation,
  the fast-fail-retry gate that reads `dt < 2.0`, and the gate's debug print exactly as they are —
  they must keep evaluating the first attempt's timing before the retry decision. After the retry
  block (whether or not a retry ran), add a second, separate
  `total_dt = time.monotonic() - start` read, computed before the `result.returncode != 0` error
  block so the error raises can use it. Every `raise` in the subprocess branch passes
  `duration_s=total_dt`, except the two pre-`dt` spawn/timeout raises in the `except Exception`
  wrapper, which pass `duration_s=time.monotonic() - start`.
  Unpack the four-value `_parse_stream_json` return, and return
  `ReviewerCallResult(text=text, session_id=effective_sid, duration_s=total_dt, tool_calls=tool_calls, cost_usd=cost_usd)`.
  Update `_invoke`'s docstring: it now returns a `ReviewerCallResult`, and it documents the two
  distinct `time.monotonic()` reads (first-attempt `dt` for the retry gate, cumulative `total_dt`
  for the reported duration).
- **Commit:** `feat(llm): return ReviewerCallResult with cumulative duration from _invoke`

### Card 4: public claude entry points return the new type

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Change `run_bulk` and `run_tool_use` return annotations to `ReviewerCallResult`; their bodies keep
  returning `_invoke(...)` directly. Update both docstrings' return sentences.
  `run_implementer` keeps its `tuple[str, str]` annotation and external contract, but its body must
  become `result = _invoke(...)` followed by `return result.text, result.session_id` — a mechanical
  unwrap so its own callers (`_implementer_claude.py` via `millpy-implement.py`/`millpy-fix.py`) are
  unaffected. Add a one-line comment on that unwrap stating it exists solely to preserve
  `run_implementer`'s 2-tuple contract. `cleanup_session` is untouched.
- **Commit:** `feat(llm): return ReviewerCallResult from run_bulk/run_tool_use`

### Card 5: `_llm_gemini` mirrors the contract with duration only

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/scripts/_llm_gemini.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Import `ReviewerCallResult` from `_llm_common` alongside the existing exception imports.
  `_parse_gemini_stream_json` is unchanged (still returns `(final_text, session_id)`) — gemini-cli
  exposes no tool-call or cost signal this task is willing to guess at.
  `_invoke` returns `ReviewerCallResult(text=text, session_id=effective_sid, duration_s=dt, tool_calls=None, cost_usd=None)`,
  and every `raise LLMError(...)`/`LLMSessionError(...)`/`LLMRateLimitError(...)` in it passes
  `duration_s=time.monotonic() - start` (for the `resume=True` guard that raises before `start` is
  assigned, pass no `duration_s` at all — there is no elapsed time to report).
  `run_bulk` and `run_tool_use` change their return annotations to `ReviewerCallResult` and update
  their docstrings' return sentences; their bodies still `return _invoke(...)`.
- **Commit:** `feat(llm): return ReviewerCallResult from gemini provider`

### Card 6: test stub and dispatcher adapter

- **Context:**
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/scripts/_reviewer_single.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `_reviewer_test_stub.run` keeps popping a `(text, session_id)` 2-tuple off `_queue` — `seed()`'s
  input contract is unchanged, so no existing flow test's seeding needs to change — but wraps the
  popped pair in `ReviewerCallResult(text=text, session_id=session_id, duration_s=0.0, tool_calls=None, cost_usd=None)`
  before returning, and its return annotation becomes `ReviewerCallResult`. `duration_s` is `0.0`
  (a real in-process call that genuinely took no measurable time), not `None`. Update the module
  docstring's `run()` bullet accordingly, keeping the statement that `seed()` takes 2-tuples.
  `_reviewer_single.run` keeps its `tuple[str, str]` annotation for this batch: replace both
  `return stub.run(...)` and `return fn(prompt_text, **kwargs)` with a call assigned to a local
  `result` followed by `return result.text, result.session_id`. Mark each with a comment reading
  that this unwrap is temporary and is removed in the dispatcher-flip batch, and add the same note
  to the module docstring's spec-contract section.
- **Commit:** `feat(reviewers): wrap stub returns in ReviewerCallResult behind a temporary adapter`

### Card 7: `test-llm-claude.py` covers the new metrics and return shape

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Update every existing assertion that unpacks or indexes `run_bulk`/`run_tool_use`'s return as a
  2-tuple to read `.text`/`.session_id` off the returned `ReviewerCallResult` instead (including the
  `text, returned_sid = run_bulk(...)`, `text, sid = run_bulk(...)`, and `result_tuple = run_bulk(...)`
  sites).
  Add direct `_parse_stream_json` cases against synthetic stream-json strings (no real CLI):
  (a) no tool_use blocks anywhere -> `tool_calls == 0`;
  (b) several `assistant` events with mixed `text` and `tool_use` blocks -> count is the total across
  all events;
  (c) a terminal `result` event carrying `num_turns` -> that value wins over the block count;
  (d) a terminal `result` event without `num_turns` -> the block count is used;
  (e) a `result` event carrying `total_cost_usd` -> `cost_usd` is that float; absent -> `None`.
  Add a case asserting the subprocess success path returns a `ReviewerCallResult` whose `duration_s`
  is a non-negative float, and a case asserting that an `LLMError` raised from a non-zero exit
  carries a non-`None` `duration_s` attribute.
  Add a case for the fast-fail-retry path asserting the raised/returned `duration_s` reflects the
  cumulative time across both attempts rather than only the first attempt's sub-2-second `dt`
  (assert it is greater than or equal to the first attempt's, using a fake subprocess runner that
  makes the second attempt measurably slower).
- **Commit:** `test(llm): cover tool-call counting, cost extraction and cumulative duration`

### Card 8: gemini tests and the two smoke tools

- **Context:**
  - `plugins/mill/scripts/_llm_gemini.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-llm-gemini.py`
  - `plugins/mill/integration_tests/smoke-llm-claude.py`
  - `plugins/mill/integration_tests/smoke-llm-gemini.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `test-llm-gemini.py`, update the `text, sid = run_bulk(...)` and `result = run_bulk(...)`
  sites for the `ReviewerCallResult` return, and add assertions that a successful call yields
  `tool_calls is None`, `cost_usd is None`, and a non-negative float `duration_s`.
  In `smoke-llm-claude.py` and `smoke-llm-gemini.py`, replace every
  `text, sid = _llm_claude.run_bulk(...)` / `_llm_gemini.run_bulk(...)` / `run_tool_use(...)` /
  `seed_text, seed_sid = ...` / `recall_text, recall_sid = ...` unpack with attribute access on the
  returned result, and print the newly available `duration_s`/`tool_calls`/`cost_usd` alongside each
  smoke's existing output line so a manual run surfaces them. Neither smoke is covered by
  `run-all.py`; leave their docstrings' manual-run instructions otherwise intact.
- **Commit:** `test(llm): update gemini tests and provider smoke tools for ReviewerCallResult`

### Card 9: `test-reviewers.py` provider fakes return the new type

- **Context:**
  - `plugins/mill/scripts/_reviewer_single.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/scripts/_llm_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  The `fake_run_bulk` and `fake_run_tool_use` doubles that `_reviewer_single.run` dispatches into
  currently return bare `(text, session_id)` tuples; they must return
  `ReviewerCallResult` instances instead, since the adapter added in card 6 reads `.text`/
  `.session_id` off whatever the provider returns. Update their return annotations too.
  The `text, session_id = _reviewer_single.run(...)` / `text, sid = _reviewer_single.run(...)`
  assertion sites stay as 2-tuple unpacks in this batch — `_reviewer_single.run` still returns a
  2-tuple until batch 2. Add an assertion in the stub-dispatch case that the value the stub produced
  round-trips through the adapter unchanged.
- **Commit:** `test(reviewers): return ReviewerCallResult from provider fakes`

## Batch Tests

`verify:` runs `test-llm-claude.py`, `test-llm-gemini.py` and `test-reviewers.py` — the three unit
test files this batch edits, and the only automated coverage of the modules it changes. The two
`integration_tests/` smoke tools it also edits are outside `run-all.py` by design (they invoke a real
CLI); per discussion.md's Testing section they must be checked by hand against a live provider after
this batch lands, which is an operator action, not part of `verify:`.

The three review backends still consume `_reviewer_single.run`'s unchanged 2-tuple in this batch, so
`test-review-*-flow.py` are unaffected and are deliberately not in the `--only` list.
