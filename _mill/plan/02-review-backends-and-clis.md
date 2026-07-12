# Batch: review-backends-and-clis

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
batch: review-backends-and-clis
number: 2
cards: 8
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-review-prepare-envelope.py test-review-discussion-flow.py test-review-plan-flow.py test-review-code-flow.py test-review-cli-error-envelope.py test-review-plan-finalize-round.py
depends-on: [1]
```

## Batch Scope

This batch **turns the contract on** for the three reviewer dispatch sites. Each backend's
`prepare()` gains an `agent_mode` flag (default `False`) that it forwards to batch 1's
`build_tool_rule`; each of the three CLIs sets that flag `True` in its `--stage prepare` branch
**only**, passes `output_contract=True` to `write_brief`, and adds `output_path` to its prepare
envelope. On the read side, all three CLIs gain a missing-file guard and lose their
`html.unescape` call.

**The flag must not be set inside `prepare()` itself.** `build_tool_rule` is called *from within*
`prepare()`, and `run()` — the `--stage full` fallback this task must not break — calls that
**same `prepare()`**. A default-on flag there would poison the exact path Shared Decision
`--stage full must keep working` protects. The flag is a parameter, defaulted `False`, set `True`
only by the CLIs' prepare branches.

**External interface consumed by batch 4:** each review prepare envelope gains an additive
`output_path` field (absolute, `.out.md`). `finalize`'s external contract — `--agent-output <path>`
and every JSON envelope it emits — is **unchanged**; mill-go, mill-start and mill-plan all parse
those, and this task must not move them.

## Cards

### Card 6: thread `agent_mode` through `_review_discussion.prepare`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a keyword-only parameter `agent_mode: bool = False` to `prepare` in
  `plugins/mill/scripts/_review_discussion.py` (`:44`) and pass it to the `build_tool_rule(mode)`
  call at `:82`, which becomes `build_tool_rule(mode, agent_mode)`. Change nothing else: `run()`
  (`:181`) calls this same `prepare()` and must keep receiving the non-agent rule by relying on
  the default. Do not add the flag to `run()` or to `finalize()`.
- **Commit:** `feat(review): thread agent_mode through discussion review prepare`

### Card 7: thread `agent_mode` through `_review_code.prepare`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a keyword-only parameter `agent_mode: bool = False` to `prepare` in
  `plugins/mill/scripts/_review_code.py` (`:194`) and pass it to the `build_tool_rule(mode)` call
  at `:335`. Do not add the flag to `run()` (`:588`) or `finalize()` (`:508`); `run()` calls this
  same `prepare()` and must keep the non-agent rule via the default. Leave the
  `worktree_snapshot_guard` at `:607` untouched (Shared Decision
  `worktree_snapshot_guard is not affected`).
- **Commit:** `feat(review): thread agent_mode through code review prepare`

### Card 8: thread `agent_mode` through `_review_plan.prepare` — both callsites, and only those

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a keyword-only parameter `agent_mode: bool = False` to `prepare` in
  `plugins/mill/scripts/_review_plan.py` (`:313`) and pass it to **both** `build_tool_rule` calls
  inside that function: the batch-scope call at `:401` and the holistic-scope call at `:490`.
  **Do NOT thread the flag into `_review_one_batch` (`:196`) or into `run()` (`:836`).** Both are
  `--stage full`-only: `_review_one_batch` is not an entry point, it is submitted to a
  `ThreadPoolExecutor` from `run()` (`:752`). They must keep the non-agent rule.
  Note for the implementer: of the two calls you *do* change, only `:490` has a live agent-mode
  caller — `millpy-review-plan.py:148-151` hardcodes `scope=None` in its `--stage prepare` branch
  ("Agent mode uses holistic scope only"), so `:401` is currently dead on the agent path. Thread it
  anyway (it is harmless and correct if batch-scope prepare is ever wired up), but **do not write a
  test asserting `:401`'s agent-mode behaviour** — there is no live path to exercise it.
- **Commit:** `feat(review): thread agent_mode through plan review prepare (both scopes)`

### Card 9: `millpy-review-discussion.py` — envelope, guard, unescape removal

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Four changes to `plugins/mill/scripts/millpy-review-discussion.py`:
  (a) In the `--stage prepare` branch (`:101-128`), pass `agent_mode=True` to `prepare(...)` and
  `output_contract=True` to `_agent_dispatch.write_brief(...)`.
  (b) Add an `"output_path"` key to the prepare `envelope` dict (`:114-123`), set to
  `str(_agent_dispatch.output_path_for(brief_path))`. This is **additive**; every existing key
  keeps its current name and value.
  (c) In the `--stage finalize` branch, replace the read at `:146` with a **missing-file guard**:
  when `agent_output_path` does not exist, use `""` as the raw text rather than calling
  `read_text`. Today that line raises an uncaught `FileNotFoundError` — the surrounding
  `except ReviewError` does not catch it — so an absent file exits with a traceback and prints no
  envelope at all. An empty string flows into `parse_verdict`, which raises `ReviewError`, which
  produces the **existing** `verdict: ERROR` envelope that mill-start's ERROR-only-aggregate retry
  already handles. Do not invent a new envelope shape or a synthetic `stuck_type`.
  (d) Delete the `html.unescape(...)` call at `:146` and the now-unused `import html` at `:23`,
  along with the three-line `#605` comment above the read. Once the reviewer writes the file
  itself the content is never HTML-escaped, and unescaping it anyway **corrupts** any literal
  `&lt;`, `&gt;` or `&amp;` quoted inside a finding's source snippet.
- **Commit:** `feat(review): add output_path and missing-file guard to discussion review CLI`

### Card 10: `millpy-review-plan.py` — envelope, guard, unescape removal

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** The same four changes as card 9, applied to
  `plugins/mill/scripts/millpy-review-plan.py`:
  (a) In the `--stage prepare` branch, pass `agent_mode=True` to `prepare(...)` (`:148-151`) and
  `output_contract=True` to `write_brief(...)` (`:153-156`). Keep the hardcoded `scope=None`.
  (b) Add `"output_path": str(_agent_dispatch.output_path_for(brief_path))` to the prepare envelope
  (`:157-166`).
  (c) Missing-file guard at the finalize read (`:185`), exactly as card 9.
  (d) Delete `html.unescape` at `:185`, the `#605` comment, and `import html` at `:24`.
  **Carve-out — do not add `output_path` to the validator-failure envelope.** The `--stage prepare`
  branch also emits `{"errors": [...], "summary": ...}` at `:142-147` and exits 1 **before any
  brief is rendered**, so it has no brief and no output path. That envelope keeps its exact current
  shape; mill-plan's step 1.5 discriminates on the presence of the `errors` key. The same applies
  to `print_error_envelope`.
- **Commit:** `feat(review): add output_path and missing-file guard to plan review CLI`

### Card 11: `millpy-review-code.py` — envelope, guard, unescape removal

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_cli.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** The same four changes as card 9, applied to
  `plugins/mill/scripts/millpy-review-code.py`:
  (a) `agent_mode=True` on the `prepare(...)` call in the `--stage prepare` branch (`:146-150`) and
  `output_contract=True` on `write_brief(...)` (`:152-155`).
  (b) Add `"output_path": str(_agent_dispatch.output_path_for(brief_path))` to the prepare envelope
  (`:156-165`).
  (c) Missing-file guard at the finalize read (`:183`), exactly as card 9.
  (d) Delete `html.unescape` at `:183`, the `#605` comment, and `import html` at `:26`.
  Code review is the only one of the three with a live batch scope (`--batch`), so both the batch
  and holistic prepare paths must carry `agent_mode=True` — they share the single `prepare(...)`
  call in this branch, so one edit covers both.
- **Commit:** `feat(review): add output_path and missing-file guard to code review CLI`

### Card 12: invert the three unescape tests; add missing / empty / stale finalize cases

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two changes to `plugins/mill/unit_tests/test-review-finalize.py`:
  (a) **Invert, do not delete, the three round-trip tests.**
  `test_review_code_finalize_unescapes_html_entities` (`:92`),
  `test_review_plan_finalize_unescapes_html_entities` (`:294`), and
  `test_review_discussion_finalize_unescapes_html_entities` (`:514`) currently write
  `"Q&amp;A send &lt;guid&gt;"` to the agent-output file and assert the backend's `finalize`
  received the **unescaped** `"Q&A send <guid>"` as its third positional argument. Invert each
  assertion: the backend must now receive the text **byte-identically**, entities and all
  (`"Q&amp;A send &lt;guid&gt;"`). Rename each test and rewrite its docstring to state the new
  contract — the reviewer writes the file itself, so its content is never HTML-escaped, and
  unescaping would corrupt a finding that legitimately quotes `&lt;` in a source snippet. The
  `#605` concern is real but has moved to the implementer path, which is untouched. Update the
  three `PASS`/`FAIL` message strings in `main()` (`:681-684`, `:711-714`, `:741-744`).
  (b) **Add missing / empty / whitespace-only cases for each of the three CLIs** (nine tests, or
  three parameterised over the CLIs), registered in `main()`. For each: invoke the CLI's `main()`
  with `--stage finalize --agent-output <path>` where the path **does not exist**, is an **empty**
  file, and is **whitespace-only**. Assert a `verdict: ERROR` envelope is produced and **no
  traceback escapes** — the missing case fails on today's code with an uncaught
  `FileNotFoundError`, which is precisely the bug card 9-11's guard fixes.
  (c) **Add the stale-`.out.md` regression guard** — the single most important test in this batch.
  Write an `.out.md` containing a valid `MILL_REVIEW` block with `verdict: APPROVE`; call
  `write_brief` for the **same role/scope/round**; then run `finalize` against that same
  `--agent-output` path. Assert the pre-existing file **did not survive** and the reviewer does
  **not** report `APPROVE`. Without batch 1's unconditional truncation, a killed-then-retried
  reviewer's stale green verdict is silently reused, and reviewers have no git-state backstop to
  catch it. This test is the only thing that would.
  Follow the file's existing style: mock the backend module and inspect
  `finalize.call_args.args[2]` rather than standing up real git or LLM fixtures.
- **Commit:** `test(review): invert unescape round-trip and add missing/empty/stale finalize cases`

### Card 13: prepare-envelope shape test, including both carve-outs

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-prepare-envelope.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-review-prepare-envelope.py` asserting the
  prepare-envelope invariant: **`output_path` is present on every brief-emitting success envelope,
  and absent from every envelope that writes no brief.**
  (a) For each of the three review CLIs, run `--stage prepare` with the backend mocked, capture the
  JSON printed to stdout, and assert `output_path` is present, is **absolute**, and equals
  `brief_path` with the trailing `.md` replaced by `.out.md`. Also assert every pre-existing
  envelope key (`stage`, `brief_path`, `subagent_type`, `model`, `session_id`, `role`, `scope`,
  `round`) is still present and unchanged — the field is additive.
  (b) **Assert the converse for both carve-outs.** The plan-validator failure envelope
  (`millpy-review-plan.py:142-147`, `{"errors": [...], "summary": ...}`, exit 1) and
  `print_error_envelope` from all three CLIs' `--stage prepare` branch must carry **no**
  `output_path` key. Both fire before any brief exists, so a plan that demanded `output_path`
  universally would be unsatisfiable.
  Mock the backends and `_paths` the way `test-review-finalize.py` already does; import each CLI via
  `importlib.util.spec_from_file_location` (the filenames contain hyphens and are not importable as
  modules). Plain `test_*` functions plus a `main()` runner; ASCII-only output.
- **Commit:** `test(review): assert output_path envelope shape and both carve-outs`

## Batch Tests

`verify:` covers the two test files this batch touches (`test-review-finalize.py`,
`test-review-prepare-envelope.py`) plus the four existing suites that exercise the same CLIs and
backends end-to-end and are the regression net for the `prepare()` signature change:
`test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`,
`test-review-cli-error-envelope.py`, and `test-review-plan-finalize-round.py`. The scope is
deliberately bounded to these — `build_tool_rule` and `write_brief` were already pinned by batch 1,
and no other suite imports the three review CLIs.
