MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-12
```

## Findings

### [BLOCKING] Card 21's static-surface sweep is unsatisfiable
**Location:** batch 5, card 21 (vs batch 3, card 14)
**Issue:** Card 21 requires asserting that "no file under `plugins/mill/agents/` states a tool permission or an output destination", but card 14 requires `mill-reviewer.md` to state exactly that (Write inventory, briefs-scoped Write guardrail, report destination), and `mill-implementer.md:4,11-18` already lists `Read, Edit, Write, Bash, Grep, Glob, Skill` — a file the reviewers-only Shared Decision forbids touching. The test as specified can only be made green by violating the plan.
**Fix:** Scope the static assertion to `templates/` only, and for `agents/` assert the narrower invariant card 14 actually produces (no `<OUTPUT_FILE>` token; no "sole output is your final message"; no blanket Write prohibition on `mill-reviewer.md`).

### [BLOCKING] Cards 12/13 mock the modules whose real behaviour is under test
**Location:** batch 2, cards 12(b), 12(c), 13
**Issue:** `test-review-finalize.py`'s existing style (`:110-137`) replaces `_review_common`, `_review_cli` and `_agent_dispatch` with bare `MagicMock`s. Under that style: `print_error_envelope` is a mock, so no `verdict: ERROR` envelope reaches stdout (12b is unobservable); `except ReviewError` catches a MagicMock, which raises `TypeError` if anything does throw; `write_brief` is a mock, so it unlinks nothing (12c's stale-`.out.md` guard proves nothing); and `output_path_for` returns a MagicMock, so card 13's "`output_path` equals brief with `.md` -> `.out.md`" assertion cannot hold.
**Fix:** Require these three cards to use the **real** `_agent_dispatch`, `_review_cli` and `_review_common` (mock only `_paths`, `_reviewers`, and the review backend, with `finalize` given a `side_effect` that delegates to the real `parse_verdict`).

### [NIT] `mill-reviewer.md` frontmatter description goes stale
**Location:** batch 3, card 14
**Issue:** `mill-reviewer.md:3` — *"Read-only sub-agent … without modifying files or running commands"* — is the description the harness surfaces, and card 14 changes `tools:` and the body but never the description.
**Fix:** Add the description line to card 14's edit list (e.g. "writes its report to the file named in its brief; makes no other change").

### [NIT] Cards 9–12 cite `parse_verdict` / `ReviewError` without `_review_common.py` in Context
**Location:** batch 2, cards 9, 10, 11, 12
**Issue:** The missing-file-guard rationale and card 12's ERROR-envelope assertions depend on `parse_verdict` and `ReviewError`, both in `_review_common.py`, which is absent from all four cards' `Context:`/`Edits:`.
**Fix:** Add `plugins/mill/scripts/_review_common.py` to those cards' `Context:` (and `_review_cli.py` to card 12's).

### [NIT] Agent-mode prompt still says "wrap your entire output"
**Location:** batch 3, card 15(d) + batch 1, card 2(b)
**Issue:** Templates keep *"Wrap your entire output in `MILL_REVIEW_BEGIN`/`MILL_REVIEW_END`"* while the footer tells the agent its final message is a one-line `WROTE` ack — an agent can satisfy both by dumping the block into chat as well, silently forfeiting the context saving the task exists for.
**Fix:** Require card 2's footer to say explicitly that the `MILL_REVIEW`-wrapped report is the *content of the file*, and the chat message is the ack only.

### [NIT] Batch 4 `depends-on: [2]` omits the batch-3 Write grant
**Location:** `00-overview.md` batch index, batch 4
**Issue:** Card 18(c) makes mill-go stop capturing `.out.md` for reviewers, which is only correct once card 14 grants `mill-reviewer` the `Write` tool (batch 3). The DAG lets batch 4 land while batch 3 has not.
**Fix:** Set batch 4 `depends-on: [2, 3]`, or state in Batch Scope why the intermediate state is acceptable.

## Verdict

REQUEST_CHANGES
Two contract-level test specs are unsatisfiable as written; the design itself is sound.
MILL_REVIEW_END
