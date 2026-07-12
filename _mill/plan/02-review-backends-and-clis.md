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
`prepare()`, and for discussion and code review the `--stage full` fallback — the path this task must
not break — reaches that **same `prepare()`** (`_review_discussion.py:215`, `_review_code.py:629`). A
default-on flag there would poison the exact path Shared Decision `--stage full must keep working`
protects. The flag is a parameter, defaulted `False`, set `True` only by the CLIs' prepare branches.

**`_review_plan` is the exception, and knowing it saves the implementer a hunt.** Its `run()`
(`:594`) does **not** call `prepare()` — it re-renders the prompt inline and has its **own**
`build_tool_rule` call at `:836`, and reaches batch scope through `_review_one_batch` (`:196`), which
`run()` submits to a `ThreadPoolExecutor` (`:752`). So for plan review the two paths are genuinely
separate code, and the `--stage full` side is protected by leaving `:196` and `:836` alone rather
than by a default.

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
  **Do NOT thread the flag into `_review_one_batch`'s `build_tool_rule` call (`:196`) or into the one
  inside `run()` (`:836`).** Both are `--stage full`-only. Note that `run()` is defined at `:594` and
  does **not** call `prepare()` at all — it renders inline, which is why `:836` exists as a separate
  `build_tool_rule` callsite; and `_review_one_batch` (whose call is at `:196`) is not an entry point,
  it is submitted to a `ThreadPoolExecutor` from `run()` (`:752`). Both must keep the non-agent rule.
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
  - `plugins/mill/scripts/_review_common.py`
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
  envelope at all. The guard collapses *missing* into *empty*, after which **existing behaviour
  takes over**.
  **Be precise about what that existing behaviour is** — the obvious description is wrong, and
  card 12 depends on getting it right. An empty `raw_text` does **not** escape as a `ReviewError`
  and does **not** reach `print_error_envelope`. It flows into the backend's `finalize`, whose
  `finalize_scope` call raises `ReviewError` **internally**; the backend **catches it itself**
  (`_review_discussion.py:146-164`) and **returns** a `ReviewResult` with `verdict: "ERROR"`. The
  CLI then prints that result via `result.to_dict()` and exits **0**. The `verdict: ERROR` envelope
  that mill-start's ERROR-only-aggregate retry consumes is therefore produced by the **backend's own
  ERROR result on a zero exit code** — not by the CLI's error path. Do not invent a new envelope
  shape or a synthetic `stuck_type`; the guard's whole job is to stop the traceback so this existing
  path can run.
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
  - `plugins/mill/scripts/_review_common.py`
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
  (c) Missing-file guard at the finalize read (`:185`), exactly as card 9 — including its note on
  what the existing ERROR behaviour actually is (the backend catches `ReviewError` at
  `_review_plan.py:568-575` and returns an ERROR entry; exit code 0).
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
  - `plugins/mill/scripts/_review_common.py`
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
  (c) Missing-file guard at the finalize read (`:183`), exactly as card 9 — including its note on
  what the existing ERROR behaviour actually is (the backend catches `ReviewError` at
  `_review_code.py:547-559` and returns an ERROR result; exit code 0).
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
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_plan.py`
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
  file, and is **whitespace-only**. Assert the printed JSON carries `verdict: "ERROR"`, that the CLI
  returns **0**, and that **no traceback escapes** — the missing case fails on today's code with an
  uncaught `FileNotFoundError`, which is precisely the bug cards 9-11's guard fixes.
  **Assert exit 0, not exit 1, and do not force the error with a raising mock.** The ERROR envelope
  is produced by the **backend's own** `except ReviewError` -> `return ReviewResult(verdict="ERROR")`
  path (`_review_discussion.py:146-164`, `_review_code.py:547-559`, `_review_plan.py:568-575`),
  which the CLI prints via `result.to_dict()` on a **zero** exit. `print_error_envelope` is never
  reached. A test that stubs `finalize` with a `side_effect` raising `ReviewError`, or that asserts
  a return code of 1, pins behaviour the real system does not have.
  (c) **Add the stale-`.out.md` regression guard** — the single most important test in this batch.
  Write an `.out.md` containing a valid `MILL_REVIEW` block with `verdict: APPROVE`; call
  `write_brief` for the **same role/scope/round**; then run `finalize` against that same
  `--agent-output` path. Assert the pre-existing file **did not survive** and the reviewer does
  **not** report `APPROVE`. Without batch 1's unconditional truncation, a killed-then-retried
  reviewer's stale green verdict is silently reused, and reviewers have no git-state backstop to
  catch it. This test is the only thing that would.
  **Mocking discipline — the existing style does not work for (b) and (c), and copying it blindly
  produces tests that pass while asserting nothing.** The file's current pattern (`:110-137`)
  replaces `_review_common`, `_review_cli` and `_agent_dispatch` with bare `MagicMock`s. Under that
  pattern: `print_error_envelope` is a mock, so **no `ERROR` envelope ever reaches stdout** and (b)
  is unobservable; `except ReviewError` binds a `MagicMock` rather than an exception class, which
  raises `TypeError` the moment anything does throw; and `write_brief` is a mock, so it unlinks
  nothing and (c) proves nothing.
  Therefore: for the **existing** round-trip tests in (a), keep the current style — it only inspects
  `finalize.call_args.args[2]` and is sound. For the **new** tests in (b) and (c), use the **real**
  `_agent_dispatch`, `_review_cli`, `_review_common`, **and the real review backend** — the ERROR
  result is exactly the backend behaviour under test, so stubbing it out would assert nothing.
  **But "real `_review_common`" cannot mean "untouched `_review_common`".** Left alone, the CLI calls
  `find_active_slug` (raises `ReviewError` in a tempdir with no marker or branch) and `resolve_path`,
  which reaches through to the **real** `_paths.resolve_git_root()` / `resolve_active_hub`
  (`_review_common.py:353-375`) — environment-dependent, and against the repo convention that unit
  tests use no real git. Instead:
  - pass `--slug <slug>` explicitly, so `find_active_slug` is never called;
  - patch `load_config` and `resolve_path` **as attributes on the real `_review_common` module**
    (pointing `reviews_dir` at a `tempfile` directory), leaving `ReviewError`, `parse_verdict` and
    the backend's exception handling genuinely real;
  - mock only `_paths` and `_reviewers`.
  This works because each CLI performs its `from _review_common import ...` **inside `main()`**, so
  attributes patched before the call are picked up.
  Capture stdout with `contextlib.redirect_stdout` and assert on the parsed JSON envelope plus the
  return code — never on a mock's call args, which would re-introduce the same blind spot.
- **Commit:** `test(review): invert unescape round-trip and add missing/empty/stale finalize cases`

### Card 13: prepare-envelope shape test, including both carve-outs

- **Context:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_review_cli.py`
  - `plugins/mill/scripts/_review_common.py`
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
  **Mocking discipline — `_agent_dispatch` must be the real module here.** If it is replaced by a
  `MagicMock` (as `test-review-finalize.py:110-137` does), then `write_brief` and `output_path_for`
  return `MagicMock`s, `str(output_path_for(...))` is junk, and the `.md` -> `.out.md` equality
  assertion — the entire point of this card — cannot hold. Use the **real** `_agent_dispatch`,
  `_review_cli` and `_review_common`, with `briefs_dir` pointed at a `tempfile` directory (via the
  mocked `_paths.resolve_task_path`); mock `_paths` and `_reviewers`, and mock the review **backend**
  only — its `prepare` returns a static dict carrying `prompt_text`, `model` (a real model id such as
  `claude-opus-4-8`, so the real `model_to_tier` resolves), `round` and `scope`. This keeps the real
  `write_brief` and the real `output_path_for` in the path, which is what makes the `.md` -> `.out.md`
  assertion meaningful.
  Apply card 12's `--slug` rule here too: pass `--slug <slug>` and patch `load_config` /
  `resolve_path` as attributes on the real `_review_common`, so no test touches real git.
  Capture stdout with `contextlib.redirect_stdout` and assert on the parsed JSON envelope, never on a
  mock's call args.
  Import each CLI via `importlib.util.spec_from_file_location` (the filenames contain hyphens and are
  not importable as modules). Plain `test_*` functions plus a `main()` runner; ASCII-only output.
- **Commit:** `test(review): assert output_path envelope shape and both carve-outs`

## Batch Tests

`verify:` covers the two test files this batch touches (`test-review-finalize.py`,
`test-review-prepare-envelope.py`) plus the four existing suites that exercise the same CLIs and
backends end-to-end and are the regression net for the `prepare()` signature change:
`test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-review-code-flow.py`,
`test-review-cli-error-envelope.py`, and `test-review-plan-finalize-round.py`. The scope is
deliberately bounded to these — `build_tool_rule` and `write_brief` were already pinned by batch 1,
and no other suite imports the three review CLIs.
