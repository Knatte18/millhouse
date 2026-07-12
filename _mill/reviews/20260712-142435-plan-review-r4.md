MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-12
```

## Findings

### [NIT] `mill-reviewer.md:9` blanket no-modify claim survives card 14
**Location:** batch 3 / card 14
**Issue:** Card 14 lists `:3`, `:4`, `:11-16`, `:18` but not line 9 — *"you MUST NOT modify any files or run commands that change state"* — which still reads as a blanket file-write prohibition after `Write` is granted, and card 22's agents/ assertions (no `<OUTPUT_FILE>`, no sole-output claim, no blanket `Write` prohibition) would not catch it.
**Fix:** Add `:9` to card 14's edit list, rewording it to "modifies no existing file and runs no commands; writes only its report".

### [NIT] Card 15's deletion list vs card 18(b)'s assertion
**Location:** batch 3 / cards 15, 18
**Issue:** Card 15 enumerates only the tool-prohibition clauses and the sole-output sentence as deletions, but the leading `You are a READ-ONLY reviewer.` sentence is named in neither (a) nor (b) — while card 18(b) asserts no template contains `You are a READ-ONLY reviewer`. A literal reading of card 15 keeps it and fails card 18's test; the implementer may then weaken the test instead of deleting the sentence.
**Fix:** Name the `You are a READ-ONLY reviewer.` sentence explicitly in card 15(a)'s deletion list (card 3 already assigns the read-only posture to `build_tool_rule`'s agent cells).

### [NIT] "Nothing else imports it" claims in Batch Tests are false
**Location:** batch 1 / Batch Tests; batch 2 / Batch Tests
**Issue:** Batch 1 says "nothing else imports `build_tool_rule` or `write_brief`", but `_implementer_common.py:775` calls `write_brief` and is exercised by `test-implementer-common.py`, `test-millpy-implement.py`, `test-millpy-fix.py`, `test-millpy-merge-in-subagent.py` — the only regression net for card 2's *unconditional* `.out.md` unlink, and none are in verify. Batch 2 says "no other suite imports the three review CLIs", but `test-review-cli.py:337`, `:436`, `:542` load all three CLIs and run their `--stage prepare` branch. (Both should stay green — the implementer suites don't use `<brief>.out.md`, and `test-review-cli.py` mocks the backends and asserts only `brief_path` — so this is scoping rationale, not a break. `00-overview.md` has `verify: null`, so no full-suite gate exists anywhere in the task.)
**Fix:** Add `test-review-cli.py` to batch 2's verify and `test-implementer-common.py` to batch 1's, and correct both rationale paragraphs.

### [NIT] Line-number drift in several citations
**Location:** batch 2 / Batch Scope; batch 4 / cards 19
**Issue:** Sampled anchors are mostly exact, but a few drift: `ThreadPoolExecutor` is `_review_plan.py:749` (not `:752`); `_MODE_BY_ALLOWED_TOOLS` is `_llm_claude.py:80` (not `:79`); mill-go's "Builder does not act on findings" bullets are `:376` and `:816` (not `:820`); step 6.5 starts at `:157` (not `:159`).
**Fix:** No action required if the implementer greps by symbol; correct on next touch.

## Verdict

APPROVE
Claims verified against source; only cosmetic and scoping nits remain.
MILL_REVIEW_END
