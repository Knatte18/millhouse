# Batch: prompt-surfaces

```yaml
task: Explore and adopt Claude Code fork-agents in mill orchestration
batch: prompt-surfaces
number: 3
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agents-defs.py test-review-templates.py
depends-on: [1]
```

## Batch Scope

This batch removes every statement in the **static** prompt surfaces — the `mill-reviewer` agent
definition and the five review templates — that contradicts the new contract, and grants the
reviewer the `Write` tool it now needs.

The organising principle is Shared Decision `all tool statements live in build_tool_rule and
nowhere else`. The five templates are **shared** between agent mode and the `--stage full`
fallback, and static prose cannot be made dispatch-aware — so any tool statement left in a template
is necessarily wrong on one of the two channels. Batch 1 already made `build_tool_rule` the
channel-aware owner of the read-only clause; this batch is the other half of that move, and it
**deletes** rather than rewords.

**The temptation to reword is the trap.** Rewording *"Your sole output is the review file in the
format below"* to point at "the file named in the brief" would leak agent-mode prose onto the
shared channel: a `--stage full` reviewer has no brief, is granted at most `Read,Grep,Glob`
(`_llm_claude.py:80`), and is told by its own non-agent `<TOOL_RULE>` to *"Return review as text"*
— so it would be instructed to `Write` a file it cannot write. The destination and the ack are
stated in exactly **two** agent-mode-only places: `build_tool_rule`'s two agent cells and
`write_brief`'s footer. Nowhere else.

## Cards

### Card 14: `mill-reviewer` agent definition — grant `Write`, guardrail it, drop the stale contract

- **Context:**
  - `plugins/mill/agents/mill-implementer.md`
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/agents/mill-reviewer.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Four changes to `plugins/mill/agents/mill-reviewer.md`:
  (a) Frontmatter `tools:` (`:4`) becomes `Read, Grep, Glob, Write`.
  (a2) Frontmatter `description:` (`:3`) — currently *"Read-only sub-agent for code review —
  validates findings without modifying files or running commands"* — goes stale the moment `Write`
  is granted. This is the string the harness surfaces in the agent picker, so it must be corrected:
  the reviewer still runs no commands and modifies no existing file, but it now **writes its report
  to the file named in its brief** and makes no other change.
  (b) The body's tool inventory (`:11-16`) gains `Write`, and the `You MUST NOT use:` line (`:16`)
  drops `Write` while **keeping** `Edit`, `Bash`, and `NotebookEdit`.
  (c) **Delete** the sentence at `:18` — *"Your sole output is your final message. Do not create
  intermediate files, run commands, or attempt to apply changes."* — and replace it with the
  guardrail: the reviewer's report goes to the output file **named in its brief**, and its final
  chat message is a one-line ack. State the `Write` restriction as prose: `Write` may be used
  **only** to create that one report file under `_mill/briefs/`, and for nothing else — never to
  modify source, tests, or any file it was asked to review. Keep "Generate findings, severity
  levels, and rationale only."
  Name the report file **by description only** — no `<OUTPUT_FILE>` token and no literal path.
  Agent definitions are static text never passed through `_render`, so a token here would reach the
  model raw (Shared Decision `no <OUTPUT_FILE> token anywhere`); the literal absolute path arrives
  in `write_brief`'s footer.
  **Record the honest limitation in the file:** `tools:` frontmatter grants capabilities wholesale,
  with **no path scoping**. Adding `Write` grants it repo-wide, so "the reviewer cannot touch source
  code" degrades from a construction-level invariant to a prompt instruction. It still holds no
  `Bash` and no `Edit`, so it cannot commit, run commands, or modify existing files — only create or
  overwrite by full path. A `PreToolUse` hook denying `Write` outside `_mill/briefs/` is the correct
  follow-up if this proves insufficient; do not build it here.
- **Commit:** `feat(agents): grant mill-reviewer a briefs-scoped Write and drop the final-message contract`

### Card 15: five review templates — delete the tool prohibitions and the sole-output sentence

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Edits:**
  - `plugins/mill/templates/review-discussion.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** All five templates open with the same four-line header at `:1-4` (verified
  identical in all five):
  *"You are a READ-ONLY reviewer. You MUST NOT call Edit, Write, Bash, or any tool that modifies
  files or runs commands. You MUST NOT make git commits. Your sole output is the review file in the
  format below. If you find issues, REPORT them -- do NOT fix them."*
  In each of the five:
  (a) **Delete the tool prohibitions** — the `MUST NOT call Edit, Write, Bash...` clause and the
  `MUST NOT make git commits` clause. `build_tool_rule` now owns the entire read-only clause and
  injects it, channel-aware, at the `<TOOL_RULE>` line that already sits a few lines below.
  (b) **Delete the sentence "Your sole output is the review file in the format below."** Do **not**
  reword it — see the Batch Scope above for why rewording breaks `--stage full`.
  (c) **Keep** the channel-neutral half: the reviewer is independent, and it REPORTS issues rather
  than fixing them.
  (d) **Keep the `MILL_REVIEW_BEGIN` / `MILL_REVIEW_END` wrapper and the whole `## Output format`
  section untouched.** That is not a delivery instruction — it is the *content format of the
  `.out.md` file*, which `finalize` parses with `parse_verdict`. Removing or loosening it breaks
  every review.
  Introduce no new `<UPPERCASE>` token in any template: `_render.render` raises `KeyError` on any
  token absent from the caller's `values` dict, which would hard-fail rendering.
- **Commit:** `refactor(templates): delete tool prohibitions and sole-output sentence from review headers`

### Card 16: `review-discussion.md` source-grounding — remove the false mode claim

- **Context:**
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/templates/review-discussion.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `plugins/mill/templates/review-discussion.md:21` (the `## Source-grounding rule`
  paragraph) statically asserts *"You are in tool-use mode -- if you need a file to verify a claim
  in the discussion, open it with Read/Grep/Glob."* That is a tool statement living outside
  `build_tool_rule`, and it is **already wrong today** for a `bulk` reviewer — which is told the
  exact opposite two paragraphs earlier by `_TOOL_RULE_BULK`. Delete the mode-specific clause,
  leaving the paragraph with only its channel-neutral half: never fabricate file contents or code
  behaviour you have not actually read; do not infer from filenames or positions. The Read/Grep/Glob
  grant is stated by `build_tool_rule`'s two `tool-use` cells, which is the only place that knows
  the mode.
  **Scope check for the implementer — this card touches one file, not five.** All five templates do
  have a `## Source-grounding rule` heading, but the other four
  (`review-code-batch.md:25`, `review-code-holistic.md:25`, `review-plan-batch.md:17`,
  `review-plan-holistic.md:17`) contain a *different*, channel-neutral paragraph about the
  `## Files included` manifest and the `NEED_CONTEXT` verdict. It states no tool permission. **Leave
  those four paragraphs exactly as they are.** (discussion.md says "and counterparts"; there are
  none — this was verified against source while planning.)
- **Commit:** `fix(templates): drop the false tool-use mode claim from discussion source-grounding`

### Card 17: `test-agents-defs.py` — re-pin the reviewer safety invariant

- **Context:**
  - `plugins/mill/agents/mill-reviewer.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-agents-defs.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `test_reviewer_agent_definition` in
  `plugins/mill/unit_tests/test-agents-defs.py` currently asserts `mill-reviewer`'s tools are
  **exactly** `{Read, Grep, Glob}` (`:60-63`) and that none of `{Edit, Write, Bash, NotebookEdit}`
  is present (`:66-70`). Card 14 makes both assertions fail. Update them:
  `expected_tools` becomes exactly `{"Read", "Grep", "Glob", "Write"}`, and the `mutating` forbidden
  set becomes `{"Edit", "Bash", "NotebookEdit"}` — `Write` moves out of it.
  **Keep this an exact-set assertion. Do NOT weaken it to a subset check.** This test *is* the
  reviewer safety invariant — it is what stops a future edit from quietly handing the reviewer
  `Bash` — and now that the path-scoping guarantee has degraded to a prompt guardrail (card 14),
  it is the strongest construction-level check remaining. Update the module docstring (`:4`) and the
  test's own docstring to describe the new invariant: the reviewer may write, but only its report,
  and it still cannot edit, run commands, or commit.
  `test_implementer_agent_definition` must stay **untouched** — the implementer is out of scope.
- **Commit:** `test(agents): re-pin mill-reviewer tool invariant with Write granted`

### Card 18: template test — the five templates still render, and the deleted prose stays deleted

- **Context:**
  - `plugins/mill/scripts/_render.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/templates/review-discussion.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-review-templates.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-review-templates.py`. **Without this card,
  cards 15 and 16 ship with zero automated coverage** — `test-render.py` renders only `tempfile`
  fixtures (`test-render.py:16-96`) and never opens `plugins/mill/templates/`, so it cannot see a
  broken template. Assert, for each of the five review templates:
  (a) **It still renders.** `_review_common.render_prompt(<name>, **tokens)` succeeds with the full
  token set that template's backend supplies. This is the guard against an accidentally-introduced
  `<UPPERCASE>` token: `_render.render` (`_render.py:35`) raises `KeyError: Unresolved template
  tokens` for any token missing from the caller's `values` dict — a failure that surfaces at render
  time, i.e. in production, not at edit time.
  (b) **The deleted prose stays deleted** (cards 15, 16): the template source contains no
  `You are a READ-ONLY reviewer` header, no `MUST NOT call Edit, Write, Bash`, no `MUST NOT make git
  commits`, no `Your sole output is the review file`, and — for `review-discussion.md` — no
  `You are in tool-use mode`.
  (c) **The kept prose stays kept** (card 15(c), 15(d)): every template still contains
  `MILL_REVIEW_BEGIN` and `MILL_REVIEW_END`, and still tells the reviewer to REPORT rather than fix.
  (d) **No `<OUTPUT_FILE>` token** appears in any template.
  Plain `test_*` functions plus a `main()` runner; ASCII-only output.
- **Commit:** `test(templates): assert review templates render and the tool prohibitions are gone`

## Batch Tests

`verify:` runs `test-agents-defs.py` and the new `test-review-templates.py` — together they are the
batch's real gate. `test-agents-defs.py` (card 17) covers the agent definition that card 14 changes;
`test-review-templates.py` (card 18) covers the five templates that cards 15 and 16 change.

**`test-render.py` is deliberately NOT in the verify set.** It would have looked like the natural
regression net for the template edits, but it renders only `tempfile` fixtures and never reads
`plugins/mill/templates/` — so it stays green on a template that no longer renders. Card 18 exists
precisely because that gap would otherwise defer all detection of a broken template to batch 5.

What card 18 cannot assert — that the **rendered prompt** is coherent across both dispatch channels
once `<TOOL_RULE>` is injected — is asserted in batch 5. That split is deliberate: the `<TOOL_RULE>`
text comes from `_review_common.py`, not from a template, so a template-only test provably cannot
see it.
