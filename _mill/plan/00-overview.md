# Plan: Surface reviewer time/tool-call cost + a review-summary command

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
slug: "reviewer-cost-summary"
approved: false
started: "20260812-062111"
parent: "main"
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: provider-contract
    file: 01-provider-contract.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-llm-claude.py test-llm-gemini.py test-reviewers.py
  - number: 2
    name: dispatcher-flip
    file: 02-dispatcher-flip.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-review-plan-flow.py
  - number: 3
    name: yaml-injection
    file: 03-yaml-injection.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
  - number: 4
    name: discussion-metadata
    file: 04-discussion-metadata.md
    depends-on: [2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-discussion-flow.py
  - number: 5
    name: code-metadata
    file: 05-code-metadata.md
    depends-on: [2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py
  - number: 6
    name: plan-metadata
    file: 06-plan-metadata.md
    depends-on: [2, 3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py
  - number: 7
    name: cli-flags
    file: 07-cli-flags.md
    depends-on: [4, 5, 6]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-agent-mode-dispatch.py
  - number: 8
    name: summary-command
    file: 08-summary-command.md
    depends-on: [3]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-summary.py
  - number: 9
    name: orchestrator-shared
    file: 09-orchestrator-shared.md
    depends-on: [7]
    verify: null
  - number: 10
    name: orchestrator-callers
    file: 10-orchestrator-callers.md
    depends-on: [9]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits._

### Decision: ReviewerCallResult lives in `_llm_common.py`

- **Decision:** The new reviewer-call return dataclass `ReviewerCallResult(text, session_id, duration_s, tool_calls, cost_usd)` is defined in `_llm_common.py`, not in a new module and not in either provider module. `_llm_common.py` is already the shared module every provider re-exports its exception hierarchy from, so both `_llm_claude.py` and `_llm_gemini.py` (and `_reviewer_test_stub.py`) can import it without a new import edge.
- **Rationale:** No new file, no new import direction, and the module's existing docstring already frames it as "the shared provider contract" module.
- **Applies to:** all batches

### Decision: two-step contract flip via a temporary adapter in `_reviewer_single.run`

- **Decision:** Batch 1 flips the provider-side public functions (`run_bulk` / `run_tool_use` on both providers, plus `_reviewer_test_stub.run`) to return `ReviewerCallResult`, and adds a deliberately temporary two-line unwrap in `_reviewer_single.run` so that function keeps returning today's `(text, session_id)` 2-tuple. Batch 2 removes that adapter and updates the three review backends (plus `bench-reviewers.py` and the two test call sites) to consume `ReviewerCallResult` directly.
- **Rationale:** The alternative — flipping providers, dispatcher, all three backends, and every test in one batch — measures ~107k context tokens, essentially the configured `max_batch_context_tokens` ceiling. The adapter keeps every batch's tree green (no knowingly-red intermediate state) at the cost of two lines written in batch 1 and deleted in batch 2. `test-reviewers.py` and `_reviewer_single.py` are consequently edited in both batches, on disjoint lines: batch 1 updates the provider-level fakes, batch 2 updates the `_reviewer_single.run` unpack sites.
- **Applies to:** 01-provider-contract, 02-dispatcher-flip

### Decision: all three metrics sum across every call in a round

- **Decision:** When a round makes more than one reviewer call (the `NEED_CONTEXT` resume-retry path), `duration_s`, `tool_calls`, and `cost_usd` are each summed across every call in the round, not just `duration_s`. Summation treats `None` as "absent": `None + x == x`, `None + None == None`, `x + y == x + y`.
- **Rationale:** discussion.md's "Duration for multi-call rounds" Decision establishes summation as the semantics for the true cost of reaching a round's verdict; a round's tool-call count and dollar cost are the same class of value and would otherwise silently report only the retry's share. The `None`-absorbing rule keeps a provider that supplies nothing (gemini, psmux) reporting `n/a` rather than a misleading `0`.
- **Applies to:** 04-discussion-metadata, 05-code-metadata, 06-plan-metadata

### Decision: yaml-header injection is one private helper, three public fields

- **Decision:** The fence-finding/inject-or-rewrite mechanism inside `apply_actual_model_override()` is extracted into a private `_inject_or_rewrite_yaml_field(raw_text, field, value)` helper in `_review_common.py`. `apply_actual_model_override()` is rewritten to delegate to it (behaviour byte-identical), and the new `apply_cost_metadata()` calls it once per non-`None` field. Fields are applied in the order `cost_usd`, `tool_calls`, `duration_s`, because each injection lands immediately after the opening fence, so applying them in reverse produces a file that reads `duration_s:`, `tool_calls:`, `cost_usd:` top-to-bottom.
- **Rationale:** discussion.md names `apply_actual_model_override()` as the precedent to follow "extended to handle three new field names instead of one"; extracting the shared mechanism is the way to do that without a fourth copy of the fence walk.
- **Applies to:** 03-yaml-injection

### Decision: `effort` in the summary table is derived from the reviewer alias, never persisted

- **Decision:** This task persists exactly three new yaml fields (`duration_s`, `tool_calls`, `cost_usd`), per discussion.md's Scope. The summary table's `EFFORT` column is derived at read time by resolving the review file's `reviewer_model:` value against the reviewer registry (`_reviewers.load` + `_reviewers.resolve`) and reading the resolved spec's `effort` key; an alias that does not resolve (e.g. a bare Agent-tool tier such as `sonnet`, which `--actual-model` can write) renders `n/a`.
- **Rationale:** discussion.md's Scope lists effort as a table column but never as a persisted field, and `reviewer_model` already carries the alias that determines effort. Adding a fourth persisted field would exceed the stated scope; leaving the column permanently `n/a` would make it useless.
- **Applies to:** 08-summary-command

### Decision: `_review_plan.py`'s file/no-file `ReviewError` inconsistency is preserved as-is

- **Decision:** Six of the seven `except ReviewError` sites this plan touches across the three backends (`_review_discussion.finalize`, `_review_code.finalize`, `_review_code.run`'s two sites, `_review_plan.finalize`, and `_review_plan.run`'s holistic block) call `write_review_file()` and get `duration_s`/`tool_calls`/`cost_usd` injected into that raw file's yaml header. `_review_plan._review_one_batch`'s outer `except ReviewError` site (which sets `"file": None`) stays file-less: it carries the metrics in its `reviews[...]` entry only. No batch may "fix" that site by making it write a file. (discussion.md's own "four of five" phrasing counted a narrower set of sites; the seven enumerated here are the ones cards 17, 20, 21, 23, 24 and 25 actually specify.)
- **Rationale:** discussion.md's "Duration on the exception/error path" Decision flags this as a pre-existing inconsistency explicitly out of this task's scope, and warns against unifying it as an incidental side effect of adding injection code.
- **Applies to:** 06-plan-metadata

### Decision: injection into a raw parse-failure file must tolerate a missing/malformed fence

- **Decision:** `apply_cost_metadata()` returns its input unchanged when there is no ` ```yaml ` fence to anchor on (same terminal fallback `apply_actual_model_override()` already has). Parse-failure branches call it on unparsed reviewer text and must not guard the call — a no-op return is the defined outcome for text with no fence.
- **Rationale:** The raw text these branches persist failed `parse_verdict()`, so a well-formed header block is exactly what is not guaranteed.
- **Applies to:** 03-yaml-injection, 04-discussion-metadata, 05-code-metadata, 06-plan-metadata

### Decision: agent-mode measures duration in the orchestrator; `tool_calls`/`cost_usd` stay absent

- **Decision:** Under agent-mode dispatch the orchestrating SKILL brackets the `Agent()` call with `date +%s` reads and passes the elapsed seconds as `--duration-s` at the finalize stage. It never passes `--tool-calls` or `--cost-usd` — the Agent tool contract carries no such signal — so those cells render `n/a`. Under a 4(a) transient re-dispatch, or a 4(c) probe that resolves to "no longer running / probe errored" (a real second `Agent()` call), the elapsed times of every attempt are summed; a 4(c) probe that reports "still running" is one continuous timer with nothing to sum.
- **Rationale:** discussion.md's "Agent-mode is in scope, with a reduced field set" and "Agent-mode duration across a transient re-dispatch" Decisions.
- **Applies to:** 09-orchestrator-shared, 10-orchestrator-callers

### Decision: batch verify lists name only test files the batch itself edits

- **Decision:** Every batch's `verify:` `--only` list contains only test files that appear in that batch's own `Edits:`/`Creates:`. Cross-checking a backend against a flow test it does not edit is deferred to the batch that does edit that flow test.
- **Rationale:** `_plan_validate`'s `verify-unrelated-test-file` check flags any `--only` token that is neither touched by the batch nor already changed versus the parent branch, and the fix table's only remedy is dropping the token.
- **Applies to:** all batches

## All Files Touched

- `SKILLS.md`
- `plugins/mill/integration_tests/bench-reviewers.py`
- `plugins/mill/integration_tests/smoke-llm-claude.py`
- `plugins/mill/integration_tests/smoke-llm-gemini.py`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/_llm_common.py`
- `plugins/mill/scripts/_llm_gemini.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/_reviewer_single.py`
- `plugins/mill/scripts/_reviewer_test_stub.py`
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-review-summary.py`
- `plugins/mill/skills/mill-go-base/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-review-summary/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- `plugins/mill/unit_tests/test-llm-claude.py`
- `plugins/mill/unit_tests/test-llm-gemini.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-review-summary.py`
- `plugins/mill/unit_tests/test-reviewers.py`
