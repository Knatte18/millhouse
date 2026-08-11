# Discussion: Surface reviewer time/tool-call cost + a review-summary command

```yaml
task: Surface reviewer time/tool-call cost + a review-summary command
slug: reviewer-cost-summary
status: discussing
parent: main
```

## Problem

Reviewer rounds run as opaque cost centers: the orchestrator dispatches a reviewer, waits, and gets
back a verdict/findings report, but nothing about *how expensive* that round was (wall-clock time,
tool-call count, model, effort) is visible without digging into raw session logs or transcripts. The
user wants a quick way to see review cost + outcome at a glance — either baked into each review
report, printed by the orchestrator right after each round, or both — plus a command that prints a
summary table across a task's reviews (tool-calls, model, effort, time-spent, verdict per round).

**Why now:** no external trigger — this is a workflow-visibility gap the user noticed while running
reviews day to day.

## Scope

**In:**
- Extending `_llm_claude.py`'s (and, in lockstep, `_llm_gemini.py`'s and `_reviewer_test_stub.py`'s)
  reviewer-call return contract to carry `duration_s` / `tool_calls` / `cost_usd` alongside the
  existing `(text, session_id)`.
- Threading that metadata through `_reviewer_single.run()` into each review backend's
  `result.reviews[...]` entry (`_review_discussion.py`, `_review_plan.py`, `_review_code.py`).
- Persisting the metadata into each review file's yaml header (new fields alongside
  `reviewer_model:`), via new `--stage finalize` CLI flags, following the existing
  `apply_actual_model_override()` / `--actual-model` precedent.
- The orchestrating skill (mill-start / mill-plan / mill-go, wherever a review round is dispatched)
  printing a one-line cost summary immediately after each round.
- Orchestrator-measured wall-clock duration for **agent-mode** dispatch (the configured default in
  this repo — see Decisions), since no in-process timer exists on that path today.
- A new dedicated command + skill, `millpy-review-summary.py` / `mill-review-summary`, printing a
  per-task table (round, scope, verdict, model, effort, duration, tool-calls) across
  `_mill/reviews/`.
- Updating the directly-affected unit tests (see Testing) and adding new coverage for the summary
  command.

**Out:**
- Tool-call counting under **psmux** dispatch mode — psmux bypasses stream-json parsing entirely
  today (`_llm_claude.py::_invoke()`'s psmux branch returns raw stdout without going through
  `_parse_stream_json()`); it reports `tool_calls: n/a`. Extending psmux's own output capture is a
  separate task.
- Cost/tool-call visibility for **implementer** or **fixer** dispatches (`run_implementer()`,
  `millpy-implement.py`, `millpy-fix.py`) — this task is reviewer-only, per the brief's framing.
- Probing Gemini's CLI schema for a native duration/tool-call/cost equivalent — `_llm_gemini.py`
  reports wall-clock `duration_s` only; `tool_calls`/`cost_usd` stay `None` until a future task
  confirms Gemini exposes something equivalent.
- A global, cross-task view in the summary command — per-task only for now (YAGNI; matches the
  user's own framing of "a table over all reviews" for the current task).
- Backfilling historical review files with the new yaml fields — the summary command reads them as
  missing/"n/a", nothing is rewritten retroactively.
- Any change to the `## Findings` / `## Verdict` body sections or the severity/class taxonomy —
  this task only touches the yaml metadata header.

## Decisions

### Agent-mode is in scope, with a reduced field set

- Decision: This task covers both `agent` and `subprocess`/`psmux` dispatch modes. Under `agent`
  mode (the configured default — `mill-config.yaml`'s `llm.claude.dispatch: agent`), the reviewer
  runs as a harness-dispatched subagent; `_llm_claude.py` is exercised only as a rare degraded
  fallback (two consecutive raw API errors — see `mill-go-base/SKILL.md` "## Agent-mode dispatch"
  step 4(a)). The documented `Agent` tool contract (`plugins/mill/docs/harness-tool-contracts.md`)
  carries only final message text + a `<status>` tag — no tool-call count or cost signal of any
  kind. So under agent-mode: `duration_s` is measured by the orchestrating skill itself (timestamp
  immediately before the `Agent()` dispatch call vs. timestamp when the completion
  `<task-notification>` arrives), and `model`/`effort` come from the prepare envelope (already
  known, e.g. `millpy-review-discussion.py`'s `--stage prepare` envelope). `tool_calls` and
  `cost_usd` render as `"n/a"` under agent-mode — there is no source for them today.
- Rationale: `agent` is the actual, default, and effectively exclusive dispatch mode in normal
  operation on this repo. Scoping the feature to subprocess/psmux only (where the brief's technical
  analysis of `_llm_claude.py`/stream-json applies most directly) would make it invisible in day-to-day
  use.
- Rejected: subprocess/psmux-only (dead-on-arrival for normal usage); agent-mode-only (throws away
  the fuller stream-json-derived data that subprocess/psmux calls do have available).

### Reviewer-call return contract becomes a small dataclass

- Decision: `run_bulk()` / `run_tool_use()` (and the internal `_invoke()` / `_parse_stream_json()`
  they call) stop returning a bare `(text, session_id)` tuple and instead return a small dataclass,
  e.g. `ReviewerCallResult(text, session_id, duration_s, tool_calls, cost_usd)`, with `tool_calls`
  and `cost_usd` `None` wherever a provider/mode can't supply them. `_reviewer_single.run()` and
  every one of `_llm_claude.py`, `_llm_gemini.py`, `_reviewer_test_stub.py` change in lockstep — all
  three are dispatched polymorphically by `provider` name (`_reviewer_single.run()` does
  `importlib.import_module(f"_llm_{provider}")`), so the return shape is a shared contract, not a
  per-module choice. `run_implementer()` (used by `millpy-implement.py`/`millpy-fix.py`, unrelated
  callers) is explicitly NOT touched — only `run_bulk`/`run_tool_use`. Callers of
  `run_bulk`/`run_tool_use`/`_reviewer_single.run` (re-enumerated including `integration_tests/`,
  which an earlier `scripts/`-only grep missed): the three review backends
  (`_review_discussion.py`, `_review_plan.py`, `_review_code.py`), **plus**
  `plugins/mill/integration_tests/bench-reviewers.py`, a benchmarking tool that calls
  `_reviewer_single.run()` directly and unpacks a bare `text, _sid = ...` 2-tuple. This file must be
  updated in lockstep with the dataclass change (unpack the new fields it doesn't otherwise need, or
  ignore them) — it is a real caller, not test fixture code exempt from the contract change, and
  breaking it silently would go unnoticed since it runs outside the unit-test suite (`run-all.py`
  doesn't cover `integration_tests/`).
- Rationale: a dataclass avoids an ever-growing positional tuple across 3 provider modules and 3
  review backends' call sites; optional fields degrade cleanly per-provider/per-mode.
- Rejected: growing the tuple arity (fragile positional unpacking at every call site); a plain dict
  (no type safety, easy to typo a key across 3 provider modules).

### Persistence: yaml-header injection + orchestrator print, both

- Decision: Follow the existing `apply_actual_model_override()` precedent
  (`_review_common.py`) exactly. Each review CLI's `--stage finalize` (`millpy-review-discussion.py`,
  `millpy-review-plan.py`, `millpy-review-code.py`) gains new optional flags — `--duration-s`,
  `--tool-calls`, `--cost-usd` — supplied by the orchestrating skill. `finalize()` /
  `finalize_scope()` inject/rewrite matching yaml-header lines (`duration_s:`, `tool_calls:`,
  `cost_usd:`) into the review file immediately after (or alongside) the existing
  `reviewer_model:` line, using the same fenced-yaml-block-anchor logic
  `apply_actual_model_override()` already implements (find the block carrying `verdict:`, fall back
  to the first ` ```yaml ` fence, no-op if no fence exists). In parallel, the orchestrating skill
  (mill-start/mill-plan/mill-go, at the same call sites that already read the finalize JSON
  envelope) prints one short line right after each round completes, e.g.
  `[review] code r2 (01-setup): REQUEST_CHANGES, sonnethigh, 4m12s, 37 tool-calls`.
- Rationale: persisting to the file is what makes the summary-table command possible without
  re-deriving anything from logs or re-running anything; the print is nearly free once the
  orchestrator has the numbers anyway, and gives instant round-by-round feedback without opening a
  file.
- Rejected: file-only (no immediate feedback during a live session); print-only (nothing persisted,
  so the summary-table command would have nothing to read for any round except the one that just
  ran in the current process).

### Tool-call counting: best-effort stream-json block count, subprocess mode only

- Decision: `_parse_stream_json()` gains a running counter of content blocks with
  `type == "tool_use"` across every `assistant` event it already iterates (today it only extracts
  `type == "text"` blocks into `final_text`). If the installed Claude CLI's terminal `"result"`
  event also carries a native `num_turns` field, prefer that value over the fallback block-count
  when both are present (implementation detail — verify against the actually-installed CLI version
  while implementing this batch; don't block discussion on it). `dt` (wall-clock, already computed
  in `_invoke()` via `time.monotonic()`) is always available regardless of what the CLI schema
  turns out to expose. psmux mode's `_invoke()` branch bypasses `_parse_stream_json()` entirely
  (returns raw `result.stdout.rstrip()`) — it reports `tool_calls: n/a`; wiring psmux's own capture
  format is out of scope (see Scope: Out).
- Rationale: no new instrumentation layer needed — `_parse_stream_json()` already iterates every
  stream-json line; counting `tool_use` blocks is additive to a loop that exists.
- Rejected: blocking this task on a live-probe spike of the CLI's exact `result`-event schema before
  any code is written; skipping tool-call counting entirely.

### `cost_usd` sourcing for Claude subprocess/psmux mode

- Decision: `_parse_stream_json()` opportunistically reads a `total_cost_usd` field from the
  terminal `"result"` event, mirroring exactly how the `tool-call-counting` Decision treats
  `num_turns` — extract it when present, leave `cost_usd: None` when the installed CLI's schema
  doesn't carry it. No live-probe of the CLI is required before plan-writing (same deferral as
  `num_turns`). The psmux branch (bypasses `_parse_stream_json()` entirely) always reports
  `cost_usd: None` — there is no equivalent field in its raw-stdout capture. This mirrors the
  `tool_calls` Decision's structure exactly, rather than leaving `cost_usd` a bare mention in
  Technical context with no actual Decision behind it.
- Rationale: `total_cost_usd` is documented as a field of the same `"result"` event `num_turns`
  comes from, so the same extraction pass and the same opportunistic/no-guarantee treatment apply
  without new mechanism.
- Rejected: always `None` regardless of what the CLI exposes (throws away real data the CLI likely
  already provides, same reasoning that made `num_turns` opportunistic rather than skipped);
  blocking discussion on a live-probe (same reasoning as the `num_turns` deferral).

### Duration for multi-call rounds: sum across every retry, at every layer

- Decision: `duration_s` sums the wall-clock cost of every attempt a round actually took, at both
  layers where a round can make more than one call:
  1. **Cross-`_invoke()`-call summation** (`_reviewer_single.run()`-level resume calls): the
     `NEED_CONTEXT` retry path in `_review_code.py::run()` / `_review_discussion.py` /
     `_review_plan.py`, which calls `_reviewer_single.run(..., resume=True)` a second time within
     the same round — the round's persisted `duration_s` is the sum of every such call's `dt`.
  2. **Intra-`_invoke()` fast-fail-retry summation**: `_invoke()`'s subprocess branch (~lines
     350-400) computes `dt = time.monotonic() - start` right after the *first* subprocess attempt,
     then may fast-fail-retry (non-zero exit, <2s, empty stdout, not resume) and re-run the
     subprocess — today `dt` is never recomputed after that retry, so a round hitting this path
     would undercount to just the failed first attempt's sub-2-second time. Fix: move the `dt`
     computation to after the fast-fail-retry block (i.e. compute `time.monotonic() - start` once,
     at the very end of `_invoke()`, after any retry has completed) — since `start` is captured
     once before the first attempt, this single end-of-function computation naturally sums both
     attempts without needing an explicit accumulator.
- Rationale: the true cost of reaching a round's verdict includes every call/attempt it took at
  every layer, not just the last one — dropping either layer's retry time (call-level or
  attempt-level) produces a silent undercount for exactly the rounds that had a rough edge (missing
  context, or a flaky first subprocess attempt).
- Rejected: reporting only the final call's/attempt's duration at either layer (undercounts exactly
  the rounds this Decision exists to handle correctly).

### Agent-mode duration across a transient re-dispatch

- Decision: Under agent-mode (see "Agent-mode is in scope" Decision above), `mill-go-base/SKILL.md`
  step 4(a) documents that a raw-API-error notification triggers one fresh re-dispatch (a brand-new
  `Agent()` call with a fresh brief/session) before falling back or escalating; step 4(c) documents
  that a stopped/interrupted notification can be *stale* — the orchestrator probes via `TaskOutput`
  and, if the agent is still running, keeps waiting for its eventual real completion notification
  without any new dispatch. These two cases are handled differently for `duration_s`:
  - **Transient re-dispatch (4a):** sum the wall-clock of every dispatch attempt for the round —
    the timer for the failed attempt (from its own `Agent()` call to the error notification) plus
    the timer for the fresh re-dispatch, exactly the same "sum every attempt" rationale as the
    subprocess/psmux Decision above.
  - **Stale stop/interrupt probe-and-wait (4c):** this is NOT a re-dispatch — there is only ever one
    `Agent()` call for that attempt. The orchestrator's single timer keeps running continuously
    from that one `Agent()` call until whichever notification is ultimately treated as terminal for
    it; no summation logic is needed because there is nothing to sum.
- Rationale: consistent with the "true round cost" rationale already established for
  `NEED_CONTEXT`/fast-fail-retry summation — a round that needed a fresh re-dispatch genuinely cost
  the wall-clock of both attempts. The stale-notification case needed calling out explicitly because
  it superficially resembles a retry (multiple notifications for one logical unit of work) but is
  actually a single dispatch whose notification arrived late.
- Rejected: measuring only the final successful dispatch's duration for the 4(a) case (undercounts,
  same reasoning as every other retry-summation Decision); treating the 4(c) probe-and-wait as a
  restart of the timer (would undercount by dropping the time already spent waiting before the
  probe).

### Summary command: new dedicated command, per-task scope

- Decision: New CLI `millpy-review-summary.py` + thin skill wrapper `mill-review-summary`, following
  `millpy-status.py`'s existing conventions (`--json`, `--no-color`; see `mill-status/SKILL.md`).
  Defaults to the current active task (matches the user's own framing — "a table over all reviews"
  for the task at hand); reads every file under that task's `_mill/reviews/` dir, parses each file's
  yaml header (round discoverable from the filename convention already documented in
  `review-output.schema.md`'s "Canonical filenames" table; `verdict`/`reviewer_model` already there;
  `duration_s`/`tool_calls`/`cost_usd` newly added by this task), and prints one row per review file:
  round, scope, verdict, model, effort, duration, tool-calls. Missing fields (older review files
  written before this change) render as `"n/a"` per-cell, never raise.
- Rationale: a dedicated command mirrors the existing `mill-status`/`mill-inspect` pattern of one
  script per concern rather than overloading `mill-inspect`'s existing status.md-focused dump; a
  new command is easy to keep out of `mill-inspect`'s unrelated concerns.
- Rejected: extending `mill-inspect` (conflates two different data sources — status.md timeline vs.
  review-file metadata); a global cross-task table by default (not what was asked for, adds scope).

## Technical context

- **4-layer review architecture** (see `_llm_claude.py`'s module docstring): Reviewer ->
  `_llm_claude.run_bulk()`/`run_tool_use()`/`run_implementer()` -> `subprocess: claude -p
  --output-format stream-json`. `_reviewer_single.run()` sits between the review backends and the
  provider modules, dispatching by `spec["provider"]` via `importlib.import_module`.
- **`_llm_claude.py::_invoke()`** (lines ~288-400) already computes `dt = time.monotonic() - start`
  for both the subprocess path and the psmux path, but discards it — never returned to any caller.
  Two branches: a `_get_via_psmux_flag()`-gated psmux branch (bypasses `_parse_stream_json()`
  entirely) and the default subprocess branch (calls `_parse_stream_json()`).
- **`_llm_claude.py::_parse_stream_json()`** (lines 228-285) iterates stream-json lines, extracting
  `session_id` (top-level on most events) and `final_text` (from `"result"` events' `result` field,
  or concatenated `text`-type blocks in `"assistant"` events' `message.content`). This is the
  function to extend with a `tool_use`-block counter and (opportunistically) `num_turns`/
  `total_cost_usd` extraction from the `"result"` event.
- **`_reviewer_single.run()`** (`_reviewer_single.py`) is the single dispatch point across
  providers — `provider == "test_stub"` short-circuits to `_reviewer_test_stub.run()`; otherwise
  `importlib.import_module(f"_llm_{provider}")` and calls `.run_tool_use` or `.run_bulk` depending
  on `spec.get("tooluse")`. Confirmed callers of `run_bulk`/`run_tool_use`/`_reviewer_single.run`,
  re-grepped across the whole repo (not just `plugins/mill/scripts/`): `_review_code.py`,
  `_review_discussion.py`, `_review_plan.py`, **and** `plugins/mill/integration_tests/bench-reviewers.py`
  (a benchmarking tool — calls `_reviewer_single.run()` directly and unpacks a bare 2-tuple; must be
  updated in lockstep, see the dataclass Decision above). `run_implementer` has different, unrelated
  callers (`millpy-implement.py`, `millpy-fix.py`) — not in scope.
- **Second provider — `_llm_gemini.py`** mirrors `_llm_claude.py`'s `(text, session_id)` contract
  with its own `_parse_gemini_stream_json()`/`_invoke()`. Any return-shape change to the
  `run_bulk`/`run_tool_use` contract must land in this file too, in lockstep, plus
  `_reviewer_test_stub.py` (the third `provider` value `_reviewer_single.run()` recognizes).
- **`_review_code.py::run()`** (lines 605-792) is representative of the three backends' legacy
  `run()` shape: calls `_reviewer_single.run(spec, prompt_text, timeout=timeout)` to get
  `(raw, session_id)`, later does `result.reviews[0]["session_id"] = session_id` after `finalize()`
  returns (finalize itself always sets `session_id: None` — the real value is patched in
  afterward, by the caller). The `NEED_CONTEXT` retry path (lines 720-782) calls
  `_reviewer_single.run(spec, retry_prompt, session_id=session_id, resume=True, ...)` a second time
  within the same round — this is the multi-call-per-round case the duration-summing decision
  covers.
- **Agent-mode CLI split** — `millpy-review-discussion.py` (and its plan/code siblings) split each
  backend's work into `--stage prepare` (render prompt, write brief, emit a JSON envelope with
  `model`/`effort`/`session_id: None`/`output_path`) and `--stage finalize` (read the reviewer's
  `--agent-output` file, call `finalize()`, print the `ReviewResult` JSON). Under agent-mode,
  `_reviewer_single.run()` / `_llm_claude.py` are never invoked for the primary review call — the
  Agent tool dispatch (documented in `mill-go-base/SKILL.md`'s "## Agent-mode dispatch") IS the
  review call. This is why agent-mode duration must be measured by the orchestrating skill around
  that dispatch, not inside `_llm_claude.py`.
- **`apply_actual_model_override()`** (`_review_common.py` ~lines 2290-2350) is the direct precedent
  for the yaml-header injection mechanism this task reuses: finds the fenced ` ```yaml ` block
  carrying `verdict:` (falling back to the first yaml fence, or no-op if none exists), and either
  rewrites an existing `reviewer_model:` line or injects a new one right after the opening fence.
  The new `duration_s:`/`tool_calls:`/`cost_usd:` fields should follow the identical
  find-or-inject pattern, extended to handle three new field names instead of one.
  `finalize_scope()` (`_review_common.py` ~line 2360) is where `apply_actual_model_override()` is
  currently invoked, in sequence before `parse_verdict()`/`extract_findings()` — the new fields'
  injection call belongs in the same sequence.
- **`review-output.schema.md`** (`plugins/mill/templates/`) is the canonical schema doc — the
  metadata-block fields table needs three new rows (`duration_s`, `tool_calls`, `cost_usd`, all
  optional/no) and a short note that `tool_calls`/`cost_usd` may be absent depending on dispatch
  mode/provider.
- **`ReviewResult.to_dict()`** (`_review_common.py` ~line 335-372) is the JSON envelope every
  review CLI prints on stdout, consumed by the orchestrating skill. It currently has no
  duration/tool-calls/cost fields at any level (top-level or per-`reviews[]`-entry) — these need to
  be added to `reviews[...]` entries (per-scope) at minimum, mirroring how `session_id` is already
  a per-entry field.
- **Command precedent** — `millpy-status.py` / `mill-status/SKILL.md` is the CLI-flag convention to
  copy (`--json`, `--no-color`, `--sort`); `millpy-inspect.py` / `mill-inspect/SKILL.md` is the
  closest existing per-task dump, deliberately NOT reused (see Decisions).
- **`_mill/reviews/` filename convention** (`review-output.schema.md`'s "Canonical filenames"
  table): `<ts>-<type>-review-r<N>.md` (discussion/code/plan-holistic) or
  `<ts>-plan-review-<batch-name>-r<N>.md` (plan per-batch) — the summary command parses round number
  and scope from these filenames as a fallback/cross-check alongside whatever the yaml header
  states.

## Constraints

_(none — no `CONSTRAINTS.md` present at hub root)_

## Testing

- **`_llm_claude.py`** (TDD candidate): unit-test `_parse_stream_json()`'s new `tool_use`-block
  counter directly against synthetic stream-json fixtures (no real CLI) — cases: zero tool calls,
  several `assistant` events each with mixed text/tool_use blocks, a `result` event carrying a
  native `num_turns` (should win over the fallback count), a `result` event without `num_turns`
  (fallback count should be used). Update `test-llm-claude.py` for the new
  `ReviewerCallResult`-shaped return from `run_bulk`/`run_tool_use`.
- **`_llm_gemini.py`**: update `test-llm-gemini.py` for the same return-shape change;
  `tool_calls`/`cost_usd` fixtures should assert `None`, `duration_s` should assert a real
  wall-clock value.
- **`_reviewer_test_stub.py` / `test-reviewers.py`**: update the stub's return shape to match;
  confirm `_reviewer_single.run()`'s polymorphic dispatch works unchanged for all three providers
  post-change.
- **`plugins/mill/integration_tests/bench-reviewers.py`**: update its `text, _sid = _reviewer_single.run(...)`
  unpack for the new dataclass return (see Technical context) — not a unit test, but a real caller
  outside `run-all.py`'s coverage, so this update has no automated safety net and must be checked by
  hand.
- **`_review_common.py`** (TDD candidate): unit-test the yaml-header injection for the three new
  fields the same way `apply_actual_model_override()` is presumably already tested — cases:
  no existing fields (inject after fence), fields already present (rewrite in place), no yaml fence
  at all (no-op, returns text unchanged). Also test the round-duration-summing logic for a
  `NEED_CONTEXT` retry round (two `_invoke()`-equivalent durations -> one summed `duration_s`).
- **`_review_discussion.py` / `_review_plan.py` / `_review_code.py`**: update
  `test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`,
  `test-review-finalize.py` for the new fields flowing into `result.reviews[...]` and
  `ReviewResult.to_dict()`.
- **Agent-mode dispatch**: update `test-agent-mode-dispatch.py` for the new finalize-stage flags
  (`--duration-s`, `--tool-calls`, `--cost-usd`) on the three review CLIs, including the
  agent-mode-specific case where `tool_calls`/`cost_usd` are omitted/`"n/a"` and only `duration_s`
  is supplied.
- **New: `millpy-review-summary.py`** (TDD candidate — new module, write tests alongside it):
  fixture a `_mill/reviews/` directory with a mix of old-format files (missing new fields) and
  new-format files; assert the table renders `"n/a"` for missing cells without raising, and that
  round/scope parsing from filenames matches the yaml header when both are present. Cover
  `--json` and `--no-color` the same way `mill-status`'s tests presumably do.
- **Orchestrator print line**: no dedicated unit test expected (it's a SKILL-level Bash/print
  action inside mill-start/mill-plan/mill-go, not a testable Python unit) — covered implicitly by
  whatever integration-level review of those SKILL.md edits mill-plan's own review performs.

## Q&A log

- **Q:** Given `mill-config.yaml` has `llm.claude.dispatch: agent` as the configured default, and
  agent-mode dispatch bypasses `_llm_claude.py`'s stream-json path entirely (confirmed via
  `mill-go-base/SKILL.md` and `harness-tool-contracts.md`, which document the `Agent` tool
  notification as carrying only final text + status, no cost/tool-call signal), should this task
  cover agent-mode, subprocess/psmux-only, or agent-mode-only? **A:** [auto-pick] Cover both:
  agent-mode gets orchestrator-measured `duration_s` + already-known `model`/`effort`, with
  `tool_calls`/`cost_usd` as `"n/a"`; subprocess/psmux gets the fuller stream-json-derived set.
  **Why:** agent-mode is the actual default and effectively exclusive mode in normal use here —
  scoping it out would make the feature invisible day-to-day.
- **Q:** `run_bulk`/`run_tool_use`/`_reviewer_single.run()` return a bare `(text, session_id)`
  tuple today, dispatched polymorphically across `_llm_claude.py`, `_llm_gemini.py`, and
  `_reviewer_test_stub.py`. How should the return contract grow to carry the new cost fields?
  **A:** [auto-pick] Replace the tuple with a small dataclass (`ReviewerCallResult`), optional
  fields `None` when unavailable, changed in lockstep across all three provider modules. **Why:**
  avoids an ever-growing positional tuple; the brief itself suggested this shape.
- **Q:** How should the new cost metadata reach disk/the user — baked into the review file's yaml
  header, printed by the orchestrator after each round, or both (the brief said "not mutually
  exclusive")? **A:** [auto-pick] Both — yaml-header injection via new finalize-stage flags
  (reusing the existing `apply_actual_model_override()` mechanism), plus a one-line orchestrator
  print right after each round. **Why:** persistence is what makes the summary-table command
  possible for past rounds; the print is nearly free once the numbers are already computed.
- **Q:** How should tool-call count be sourced for subprocess/psmux-dispatched reviews, given the
  CLI's exact `result`-event schema (whether it emits `num_turns`) is unverified? **A:** [auto-pick]
  Best-effort: count `tool_use`-type blocks across `assistant` events in `_parse_stream_json()`,
  preferring a native `num_turns` from the `result` event when present; psmux stays `"n/a"`
  (bypasses stream-json parsing entirely already). Schema verification against the installed CLI
  happens at implementation time, not as a discussion blocker. **Why:** additive to a loop that
  already exists; no new instrumentation layer required.
- **Q:** Should the new summary-table command be a wholly new command or an extension of
  `mill-inspect`, and should it default to per-task or global scope? **A:** [auto-pick] New
  dedicated command `millpy-review-summary.py` / `mill-review-summary`, mirroring `mill-status`'s
  `--json`/`--no-color` conventions, defaulting to the current active task. **Why:** keeps
  `mill-inspect`'s existing status.md-focused concern separate; matches the user's own framing of a
  per-task table; global scope is unrequested scope creep (YAGNI).
- **Q:** When a round makes more than one LLM call (the `NEED_CONTEXT` resume-retry path), should
  the persisted `duration_s` sum every call in that round or report only the last one? **A:**
  [auto-pick] Sum every call belonging to the round. **Why:** that's the true cost of reaching that
  round's verdict.
- **Q:** Gemini's CLI schema for duration/tool-calls/cost is unverified — should this task probe it
  before deciding, or ship a conservative default? **A:** [auto-pick] `_llm_gemini.py` always
  reports wall-clock `duration_s`; `tool_calls`/`cost_usd` stay `None` until a future task confirms
  Gemini exposes equivalents. **Why:** keeps the dataclass contract uniform across providers without
  over-scoping into a second, undocumented CLI's behavior.
- **Q:** How should the summary command handle historical review files written before this change
  (missing the new yaml fields) — render as "n/a", or require a backfill migration? **A:**
  [auto-pick] Render `"n/a"` per missing cell at read time; no backfill. **Why:** old review files
  must stay readable; this is a read-time default, not a schema requirement.
- **Q:** (Discussion review r1 gap) `_invoke()`'s fast-fail retry re-runs the subprocess but never
  recomputes `dt` — should the persisted `duration_s` sum both attempts, or accept the undercount?
  **A:** [auto-pick] Sum both attempts, by moving the `dt` computation to after the fast-fail-retry
  block completes (since `start` is captured once before the first attempt, this naturally
  accumulates without an explicit accumulator). **Why:** consistent with the "true round cost"
  rationale already used for `NEED_CONTEXT` summation — an undercounted retry is the same class of
  bug either way.
- **Q:** (Discussion review r1 gap) Agent-mode's `mill-go-base/SKILL.md` step 4(a) triggers a fresh
  re-dispatch on a raw-API-error notification, and step 4(c) can leave the orchestrator waiting
  unboundedly for a stale stop/interrupt notification — should `duration_s` sum across either case?
  **A:** [auto-pick] Sum across a 4(a) transient re-dispatch (two separate `Agent()` calls, same
  round); do NOT restart the timer for a 4(c) stale-notification wait (one `Agent()` call, one
  continuous timer — nothing to sum). **Why:** 4(a) is a genuine retry (same summation rationale as
  every other retry Decision); 4(c) only superficially resembles one — restarting the timer there
  would drop real elapsed time.
- **Q:** (Discussion review r1 gap) The caller-enumeration for `run_bulk`/`run_tool_use`/
  `_reviewer_single.run()` was grepped only under `plugins/mill/scripts/` — does a wider grep change
  the "only 3 backends" scoping for the dataclass-conversion Decision? **A:** [auto-pick] Yes —
  `plugins/mill/integration_tests/bench-reviewers.py` is a fourth caller (unpacks a bare 2-tuple
  directly); it must be updated in lockstep, added to Technical context and Testing. **Why:** the
  grep that produced "only 3" excluded `integration_tests/`; a real caller outside that scope would
  silently break with no unit-test coverage to catch it.
