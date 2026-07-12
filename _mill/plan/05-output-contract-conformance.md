# Batch: output-contract-conformance

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
batch: output-contract-conformance
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-output-contract.py
depends-on: [2, 3]
```

## Batch Scope

This batch is the join node of the DAG and the integration guard for the whole task. Batches 2 and 3
each removed half of the old contract — the Python half (`build_tool_rule`, the CLIs) and the static
half (templates, agent definition). Neither can prove on its own that the two halves now agree, and
neither can prove that agent-mode prose did not leak onto the shared `--stage full` channel.

**Assert against the *rendered* `prompt_text`, never by grepping directories.** The `<TOOL_RULE>`
block is injected from `_review_common.py`, not from a template, so a sweep over `templates/` and
`agents/` **provably cannot see it** — it would pass while the contradiction ships. Rendering is what
makes both directions catchable regardless of which file the text came from.

**Both directions matter, and the second is the one that was nearly missed.** The agent-mode
direction (no prompt still forbids `Write` or claims its final message is its output) is the obvious
one. The `--stage full` direction is the converse: the rendered **non-agent** prompt must contain
**no** `Write` instruction, no `.out.md` destination and no ack instruction. Without that assertion,
agent-mode prose can silently leak onto the shared channel and break the reviewer's API-error
fallback — the one thing that rescues a review round when the Agent API is down.

**Interpretation note for the reviewer.** discussion.md says the conformance test "asserts against"
the 19-file edit set. That is implemented here as a **behavioural** sweep over the prompt surfaces
those files produce — not as a hardcoded file count. A literal `assert len(files) == 19` would
contradict the discussion's own Testing section, which states that new test files are "additive and
not bounded by that list", and would go stale on the first follow-up task.

## Cards

### Card 21: rendered-prompt conformance sweep — both channels, both directions

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/templates/review-discussion.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/agents/mill-reviewer.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-output-contract.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-review-output-contract.py`. Build the
  **rendered `prompt_text`** for each of the five review templates in **both** channels and **both**
  reviewer modes, then assert in both directions.
  Render via `_review_common.render_prompt(<template_name>, tool_rule=build_tool_rule(mode,
  agent_mode), artefact_section=<stub>, ...)`, supplying every token the template needs. This
  reproduces exactly what each backend's `prepare()` builds — `prepare()` renders the same template
  with the same `tool_rule` — without standing up git, wiki or LLM fixtures, which the repo's
  unit-test convention forbids. The `artefact_section` stub can be any placeholder: it carries no
  tool statements.
  **Agent-mode direction** — for every template x mode with `agent_mode=True`, assert the rendered
  prompt:
  (a) contains no instruction forbidding `Write`;
  (b) does not claim the reviewer's sole output is its final message, or its review file, in a way
  that contradicts writing the report to a file;
  (c) does grant exactly one `Write` for the report;
  (d) still forbids `Edit`, git and bash.
  **`--stage full` direction (the converse)** — for every template x mode with `agent_mode=False`,
  assert the rendered prompt contains **no** `Write` instruction, **no** `.out.md` destination, and
  **no** ack instruction. A `--stage full` reviewer has no brief and is granted at most
  `Read,Grep,Glob` (`_llm_claude.py:80`); instructing it to write a file it cannot write breaks the
  API-error fallback.
  Also assert the **static** surfaces directly — but note the two directories carry **different**
  invariants, and conflating them produces an unsatisfiable test:
  - **`plugins/mill/templates/`** — assert no review template states a tool permission or an output
    destination. Those live only in `build_tool_rule`'s two agent cells and `write_brief`'s footer
    (Shared Decision `all tool statements live in build_tool_rule and nowhere else`).
  - **`plugins/mill/agents/`** — the same assertion **cannot** hold here and must not be written.
    An agent definition's `tools:` frontmatter *is* the tool-grant mechanism, so it necessarily
    states a permission: card 14 deliberately makes `mill-reviewer.md` name `Write` and describe its
    report destination, and `mill-implementer.md` already lists `Read, Edit, Write, Bash, Grep,
    Glob, Skill` — a file the reviewers-only Shared Decision forbids touching. Assert instead the
    narrower invariant card 14 actually produces, scoped to `mill-reviewer.md`: it contains no
    `<OUTPUT_FILE>` token, no claim that its sole output is its final message, and no blanket `Write`
    prohibition — while still forbidding `Edit`, `Bash` and `NotebookEdit`.
  Plain `test_*` functions plus a `main()` runner; ASCII-only output.
- **Commit:** `test(review): sweep rendered review prompts for output-contract conformance`

### Card 22: no-token regression — pin the `_render` constraint that killed the first design

- **Context:**
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/agents/mill-reviewer.md`
  - `plugins/mill/agents/mill-implementer.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-output-contract.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add two tests to `plugins/mill/unit_tests/test-review-output-contract.py`,
  registered in its `main()`:
  (a) **No `<OUTPUT_FILE>` token anywhere.** Assert no file under `plugins/mill/templates/` and no
  file under `plugins/mill/agents/` contains the literal string `<OUTPUT_FILE>`.
  (b) **Every template still renders.** Assert `_render.render` succeeds on each of the five review
  templates with its normal `values` dict — i.e. no card introduced an `<UPPERCASE>` token that no
  caller supplies.
  This pins the constraint that made the first design of this task **unbuildable**: `_render.render`
  (`_render.py:35`) matches `<[A-Z][A-Z0-9_]*>` and raises `KeyError: Unresolved template tokens` for
  any such token missing from the caller's `values` dict. A literal `<OUTPUT_FILE>` in a template
  would hard-fail rendering **before** `write_brief` ever runs, and is unsuppliable on `--stage full`
  anyway; agent definitions are static text never passed through `_render`, so a token there would
  reach the model raw. Test (a) is the guard against someone re-introducing the token design without
  reading the discussion.
- **Commit:** `test(review): pin the no-OUTPUT_FILE-token constraint and template renderability`

## Batch Tests

`verify:` runs the single new file, `test-review-output-contract.py`. It is scoped deliberately:
every other suite touched by this task was already pinned at the batch that changed it (batch 1
pinned `build_tool_rule` and `write_brief`; batch 2 pinned the envelopes and the finalize read sites;
batch 3 pinned the reviewer tool invariant). This batch adds the one assertion none of them can make
on its own — that the Python half and the static half of the prompt now agree, in both channels.

Not covered by any unit test, and accepted: **that the orchestrator's context actually shrinks.**
Verify that manually on the first real review round after this lands, by observing that the
`<task-notification>` payload is a one-line `WROTE <path>` ack instead of a full findings dump. Note
that this cannot be observed from inside this task — operational mill runs use the plugin cache, not
this worktree (Shared Decision `editing the source tree does not change the mill running this task`).
