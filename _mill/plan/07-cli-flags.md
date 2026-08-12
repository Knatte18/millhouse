# Batch: cli-flags

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "cli-flags"
number: 7
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-agent-mode-dispatch.py
depends-on: [4, 5, 6]
```

## Batch Scope

Exposes the backend threading to the orchestrator: each of the three review CLIs gains
`--duration-s`, `--tool-calls` and `--cost-usd` on its `--stage finalize` path, forwarded to the
backend `finalize()` exactly as `--actual-model` already is. This is the interface batches 9 and 10
call: agent-mode dispatch supplies `--duration-s` only, because the Agent tool contract carries no
tool-call or cost signal.

## Cards

### Card 27: three new finalize-stage flags on each review CLI

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In each CLI's `main`, add three `parser.add_argument` calls directly after the existing
  `--actual-model` one: `--duration-s` (`type=float`, `default=None`), `--tool-calls`
  (`type=int`, `default=None`), `--cost-usd` (`type=float`, `default=None`). Help text states each
  is finalize-stage-only, orchestrator-supplied, written into the review file's yaml header and the
  JSON envelope, and omitted when the dispatch mode cannot supply it (agent-mode supplies duration
  only).
  Forward all three to the `finalize(...)` call in the `--stage finalize` branch as
  `duration_s=args.duration_s`, `tool_calls=args.tool_calls`, `cost_usd=args.cost_usd`.
  For `millpy-review-plan.py`, whose finalize branch builds `result_dict` by hand from the returned
  `review_entry`, no extra work is needed beyond the forward — the entry dict already carries the
  three keys and is embedded verbatim under `reviews`.
  Update each module docstring's Flags section with the three new flags.
  The `prepare` and `full` stages are untouched: neither accepts these flags nor forwards them.
- **Commit:** `feat(review-cli): add --duration-s/--tool-calls/--cost-usd finalize flags`

### Card 28: finalize-stage CLI coverage

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Following the existing `_actual_model_case` helper's shape, add a `_cost_flags_case` helper
  parameterised by CLI relpath that runs the finalize stage with `--duration-s`, `--tool-calls` and
  `--cost-usd` set, and asserts (a) the printed JSON envelope's `reviews[0]` carries the three values
  and (b) the written review file's yaml header carries the matching `duration_s:`, `tool_calls:`
  and `cost_usd:` lines.
  Add a second case per CLI running finalize with `--duration-s` only (the agent-mode shape),
  asserting `tool_calls` and `cost_usd` are `null` in the envelope and absent from the file header.
  Add a third case per CLI running finalize with none of the three flags, asserting the envelope
  keys are `null` and the file header gains no new lines — the no-regression guard for every
  pre-existing caller.
  Register all nine cases in `main`'s runner exactly as the existing actual-model cases are.
- **Commit:** `test(review-cli): cover cost flags on the finalize stage of all three CLIs`

### Card 29: agent-mode parity coverage

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/_review_discussion.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the reviewer-class parity test, extend the finalize-stage invocation to pass `--duration-s`
  with a known value and assert the resulting envelope carries it while `tool_calls` and `cost_usd`
  stay `null` — the exact field set agent-mode dispatch can supply.
  Keep the existing prepare/finalize byte-parity assertions intact: the prepare envelope is
  unchanged by this task, so any parity comparison against the full path must still hold once the
  cost flags are omitted.
- **Commit:** `test(agent-mode): assert duration-only cost fields on the reviewer finalize stage`

## Batch Tests

`verify:` runs `test-review-finalize.py` (CLI finalize-stage coverage for all three review CLIs) and
`test-agent-mode-dispatch.py` (prepare/finalize parity), the two test files this batch edits and the
only automated coverage of the CLI surface it changes.
