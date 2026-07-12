# Batch: contract-helpers

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
batch: contract-helpers
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-review-common.py test-agent-mode-dispatch.py test-implementer-common.py test-millpy-implement.py test-millpy-fix.py test-millpy-merge-in-subagent.py
depends-on: []
```

## Batch Scope

This batch builds the two contract primitives every later batch consumes, and turns neither
of them on. `_agent_dispatch.py` gains an `output_path_for()` helper (the single home of the
`.md` -> `.out.md` rule), and `write_brief` gains an optional `output_contract` flag that
appends the output-contract footer; it also learns to unlink a stale `.out.md`
unconditionally. `_review_common.py`'s `build_tool_rule` becomes dispatch-aware across all
four cells (`bulk` / `tool-use` x non-agent / agent-mode).

Both new flags default to `False`, so **this batch changes no observable behaviour**: every
existing caller keeps today's output byte-for-byte. That is the point — the flags are dead
until batch 2 flips them, which is what makes the descope provable rather than asserted.

**External interface consumed by later batches:**
`output_path_for(brief_path: Path) -> Path`; `write_brief(..., output_contract: bool = False)`;
`build_tool_rule(mode: str, agent_mode: bool = False) -> str`.

The one unconditional behaviour change is the stale-`.out.md` unlink in `write_brief` (card 2),
which applies to **all roles including the implementer**. That is deliberate and safe: the
orchestrator overwrites the implementer's `.out.md` immediately before its finalize anyway, so
deleting a stale one at brief-write time is a no-op for that path.

## Cards

### Card 1: `output_path_for` helper — the single home of the `.md` -> `.out.md` rule

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `output_path_for(brief_path: Path) -> Path` to
  `plugins/mill/scripts/_agent_dispatch.py`. It returns the brief path with a trailing `.md`
  replaced by `.out.md` (e.g. `review-code-holistic-r1.md` -> `review-code-holistic-r1.out.md`),
  using `Path.with_suffix(".out.md")` or equivalent, and returns an absolute path when given an
  absolute path. Add `"output_path_for"` to the module's `__all__` list and document it in the
  module docstring's `Exports` section alongside the existing `write_brief` entry. This rule is
  currently restated as prose in four places across the SKILL.md files; this function becomes its
  only definition.
  `_paths.py` is in `Context:` for one reason: `write_brief` already routes the brief filename
  through `_paths.sanitize_filename_component` (`_agent_dispatch.py:117`), and `output_path_for`
  must stay consistent with the filename that helper produces. `output_path_for` itself is pure
  `pathlib` and adds no `_paths` dependency.
- **Commit:** `feat(dispatch): add output_path_for helper for .md -> .out.md`

### Card 2: `write_brief` — output-contract footer and stale-`.out.md` truncation

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extend `write_brief` in `plugins/mill/scripts/_agent_dispatch.py` with a new
  keyword parameter `output_contract: bool = False`, appended after `prompt_text`. Two behaviour
  changes:
  (a) **Unconditional stale-output truncation.** Before writing the brief, call
  `output_path_for(brief_path).unlink(missing_ok=True)`. This runs for **every** role regardless
  of the flag. Without it, the transient retry in `mill-go/SKILL.md:129` re-dispatches with the
  same role/scope/round — hence the same `.out.md` path — so an attempt-1 file could be read as
  attempt-2's result; for a reviewer that means a stale `APPROVE` no live reviewer produced.
  (b) **Output-contract footer, gated on the flag.** When `output_contract` is `True`, append a
  footer to `prompt_text` before writing. The footer must state, as **literal text**, the
  absolute path returned by `output_path_for(brief_path)`; instruct the agent to write its full
  report to that file; and instruct it to make its final chat message a single-line ack of the
  form `WROTE <that same absolute path>`. The footer must NOT contain any `<UPPERCASE>` token
  (see Shared Decision `no <OUTPUT_FILE> token anywhere`).
  **The footer must resolve the ambiguity it would otherwise create.** The review templates keep
  their instruction to *"Wrap your entire output in `MILL_REVIEW_BEGIN` / `MILL_REVIEW_END`"* — and
  they must, because that is the format `finalize` parses. Read alongside the ack instruction, an
  agent can satisfy **both** by writing the file *and* dumping the whole block into chat, which
  forfeits exactly the context saving this task exists to win. The footer must therefore say
  explicitly that the `MILL_REVIEW`-wrapped report is the **content of the file**, and that the chat
  message is the ack **and nothing else**.
  **`write_brief`'s return shape is unchanged** — still the brief `Path`, never a tuple. Callers
  that need the output path call `output_path_for` themselves. Update the parameter list in the
  module docstring's `Exports` section. Do not touch `_implementer_common.py`; its call at `:775`
  passes five positional arguments and must keep rendering byte-identical briefs.
- **Commit:** `feat(dispatch): add output_contract footer and stale .out.md truncation to write_brief`

### Card 3: `build_tool_rule` — dispatch-aware across all four cells

- **Context:**
  - `plugins/mill/scripts/_reviewers.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Make `build_tool_rule` in `plugins/mill/scripts/_review_common.py` (`:1231`)
  dispatch-aware: change its signature to `build_tool_rule(mode: str, agent_mode: bool = False)
  -> str`. Keep the existing `ValueError` for an unknown `mode`. Keep the module-docstring entry
  at `:28` accurate.
  **The two non-agent cells must stay byte-identical to today's strings.** Leave `_TOOL_RULE_BULK`
  (`:1216-1221`) and `_TOOL_RULE_TOOL_USE` (`:1223-1228`) exactly as they are, and return them
  unchanged when `agent_mode` is `False`.
  Add two new agent-mode constants, returned when `agent_mode` is `True`:
  - **`bulk` x agent** — this is the trap cell, and it is reachable: `mode` derives from the
    reviewer spec's `tooluse` flag, which **defaults to `False`** (`_reviewers.py:386`), and the
    registry ships selectable `*_bulk` variants. Today's bulk text opens with a bare *"Do NOT
    request tool calls"*, which under agent mode would contradict the Write instruction and yield
    **no `.out.md` and an `ERROR` envelope every round**. The agent-mode bulk cell must instead
    forbid tool calls **for gathering content** ("everything you need is in this prompt") while
    carving out **exactly one** `Write` — the report to the file named in the brief.
  - **`tool-use` x agent** — retains `You MAY use Read, Grep, and Glob to verify claims`, and adds
    a `Write` permitted **only** for writing the report to the file named in the brief.
  Both agent-mode cells must: name the report file **by description, never by a `<TOKEN>` and
  never by a literal path** (the path comes from `write_brief`'s footer); still forbid `Edit`; still
  forbid git and bash; and retain the existing `Review-only. Do NOT suggest modifications. Findings
  only.` and `Do NOT read` reviews/`. Evaluate fresh each round.` clauses verbatim.
  Because the templates' static READ-ONLY header is deleted in batch 3, the agent-mode cells are
  also the **sole remaining statement of the read-only posture** — they must carry it.
  Update `build_tool_rule`'s docstring: the current claim that *"Write, Edit, and shell access are
  forbidden in both modes -- the backend owns file writes and git"* stops being true for agent mode.
- **Commit:** `feat(review): make build_tool_rule dispatch-aware across all four cells`

### Card 4: tests — `output_path_for`, footer, default-off, truncation

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-agent-mode-dispatch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extend `plugins/mill/unit_tests/test-agent-dispatch.py` with four new test
  functions, registered in its `main()` list:
  (a) `output_path_for` maps `foo-r1.md` -> `foo-r1.out.md` and preserves the parent directory
  and absoluteness.
  (b) **Footer present when `output_contract=True`:** the written brief starts with `prompt_text`
  and ends with a footer that contains the **literal absolute** `output_path_for(brief_path)`
  string and an instruction to reply with a one-line `WROTE` ack.
  (c) **Default-off byte-identity — the descope guarantee:** calling `write_brief` **without**
  `output_contract` writes a file whose content is **exactly equal** to `prompt_text`, with no
  footer appended. Assert equality, not `startswith`.
  (d) **Stale-`.out.md` truncation:** pre-create an `.out.md` next to the brief containing
  `verdict: APPROVE`, call `write_brief` for the same role/scope/round, and assert the `.out.md`
  **no longer exists**. Assert this for both `output_contract=True` and the default, since the
  unlink is unconditional.
  Existing tests in this file must keep passing untouched — `write_brief`'s return type is still
  a single `Path`.
- **Commit:** `test(dispatch): cover output_path_for, footer, default-off, and stale truncation`

### Card 5: tests — `build_tool_rule` four-cell matrix

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a four-cell matrix test for `build_tool_rule` to
  `plugins/mill/unit_tests/test-review-common.py`, registered in its runner. Assert:
  (a) **`bulk` x non-agent** and **`tool-use` x non-agent** return strings **byte-identical** to
  today's `_TOOL_RULE_BULK` / `_TOOL_RULE_TOOL_USE`. Pin the exact current text as a literal in
  the test — this assertion is what stops the reviewer's `--stage full` API-error fallback from
  being collaterally broken by a future edit.
  (b) **`bulk` x agent** does **not** contain a bare `Do NOT request tool calls` (the clause that
  would contradict the Write instruction), and **does** grant exactly one `Write` for the report.
  (c) **`tool-use` x agent** still grants `Read, Grep, and Glob` and grants `Write` for the report.
  (d) **Both agent cells** still forbid `Edit`, git, and bash.
  (e) The `agent_mode` parameter **defaults to `False`**: `build_tool_rule("bulk")` called with a
  single positional argument equals the `bulk` x non-agent cell. This pins the default that keeps
  the file's seven existing positional callsites (`:615`, `:652`, `:690`, `:691`, `:695`, `:2828`,
  `:2880`) green.
  (f) An unknown `mode` still raises `ValueError` in both `agent_mode` states.
- **Commit:** `test(review): cover build_tool_rule four-cell dispatch matrix`

## Batch Tests

`verify:` runs `test-agent-dispatch.py` (cards 1, 2, 4) and `test-review-common.py` (cards 3, 5),
plus five suites that no card edits but that are this batch's real regression net:

- **`test-agent-mode-dispatch.py`** calls `write_brief(...)` at `:370` and asserts the written brief
  equals `prompt_text` — the independent witness that the `output_contract` default-off path stayed
  byte-identical.
- **`test-implementer-common.py`, `test-millpy-implement.py`, `test-millpy-fix.py`,
  `test-millpy-merge-in-subagent.py`** exercise `_implementer_common.py:775`, the **only other**
  `write_brief` caller. They matter because card 2's `.out.md` unlink is **unconditional** — it fires
  for the implementer path too — so these are the only automated check that the descope's
  "implementer comes out byte-identical" guarantee actually holds. They should stay green (the
  implementer suites never populate a `<brief>.out.md`), but "should" is exactly what a verify gate is
  for.

The scope is deliberately bounded to these seven rather than the full ~100-file suite, and the
overview sets no module-wide `verify:`. Note this is a **scoping** choice, not a claim that nothing
else touches these helpers: an earlier draft of this paragraph asserted "nothing else imports
`build_tool_rule` or `write_brief`", which is false.
