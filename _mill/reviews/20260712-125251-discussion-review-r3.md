MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-12
```

## Findings

### [GAP] Edit set misses the TOOL_RULE injected from Python
**Section:** Technical context → "Authoritative edit set" (Group 5); Testing → conformance test
**Issue:** `_review_common.py:1216-1228` (`_TOOL_RULE_BULK` / `_TOOL_RULE_TOOL_USE`, fed into every review prompt via `build_tool_rule`, called from `_review_discussion.py:82`, `_review_plan.py:196/401/490/836`, `_review_code.py:335`) hardcodes `**CRITICAL: Do NOT use Write, Edit, or run git/bash. Return review as text.**` — a direct contradiction of the new contract; `_review_common.py` is absent from the 8-file Python group, and the conformance test is scoped to `templates/` and `agents/` only, so it cannot catch this.
**Fix:** Add `_review_common.py` to the edit set (making the count 23), state the new `<TOOL_RULE>` wording, and extend the conformance test's search root to `scripts/` (or to the rendered `prompt_text`) rather than the two doc directories.

### [GAP] Output contract is not mode-conditional; non-agent reviewer paths still return text
**Section:** Decisions → `subagent-writes-its-own-out-md`, `output-path-in-prepare-envelope`; Scope Out ("subprocess/psmux are dead")
**Issue:** The five review templates (Group 2) and the TOOL_RULE are shared with the `--stage full` LLM-provider path, which mill-go/SKILL.md:129 explicitly retains as the reviewer's fallback after two consecutive API errors — that path never calls `write_brief` (so `<OUTPUT_FILE>` is never substituted), the provider grants `Read,Grep,Glob` at most (`_llm_claude.py:80`), and a `tooluse: false` reviewer spec (`mill-agents.yaml` `_bulk` variants, selectable per role) renders "Do NOT request tool calls" while agent-mode dispatch still expects the agent to `Write` its own `.out.md`.
**Fix:** State explicitly which prompt text is agent-mode-only (appended by `write_brief`) versus shared, and what a bulk-mode / `--stage full` reviewer is told, so the two channels do not receive contradictory instructions.

### [GAP] Existing tests pin the behaviour being changed; none are in the edit set
**Section:** Testing; Technical context → "Authoritative edit set"
**Issue:** `test-implementer-common.py:3131-3172` (case 63) and three tests in `test-review-finalize.py` (code/plan/discussion `..._unescapes_html_entities`) assert the `html.unescape()` behaviour that decision `remove-html-unescape` deletes, and `test-agent-dispatch.py:86-164` asserts `write_brief` returns a single `Path` (the decision has it "return both paths") — the 22-file edit set enumerates no test files, so verify goes red on files the plan never mentions.
**Fix:** Name the affected existing tests as part of the change (deleted or inverted) alongside the new TDD candidates.

### [NOTE] Edit-set file count is stated three ways
**Section:** Scope C ("15 files") vs Technical context ("22 files (1 + 5 + 5 + 3 + 8)") vs Q&A ("the sweep covers twelve files, not seven")
**Issue:** Groups sum to 22 and the conformance test is asserted against this list, so the two other counts are stale and invite a wrong test assertion.
**Fix:** Reconcile to one number in all three places.

### [NOTE] Ack-less-but-clean payload is undefined for reviewer/fixer
**Section:** Decisions → `ack-is-the-completion-discriminator`
**Issue:** The "payload contains neither" bullet routes to "the existing step-4(b) split", but `mill-go/SKILL.md:131` scopes 4(b) to *implementer* dispatches; a reviewer/fixer notification that is clean, non-error and non-ack has no named branch (today step 5 captured whatever text arrived).
**Fix:** State that such payloads fall through to `finalize`, which emits the existing `ERROR` envelope (reviewers) / git-state inference (fixers).

## Verdict

GAPS_FOUND
Three resolvable gaps: missing Python prompt source, non-agent path contract, and unlisted test churn.
MILL_REVIEW_END
