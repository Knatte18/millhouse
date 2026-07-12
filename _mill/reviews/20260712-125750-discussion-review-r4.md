MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-12
```

## Findings

### [GAP] Edit set omits the three `_review_*.py` backends
**Section:** Technical context → "Authoritative edit set" (Group 5), and Decision `output-contract-is-agent-mode-only`
**Issue:** `build_tool_rule` is called only from `_review_discussion.py:82`, `_review_code.py:335`, and `_review_plan.py:196,401,490,836` — none of those three files appear in the enumerated 9-file Python group (which the conformance test is told to assert against), yet every one of them must change to pass the new dispatch-aware argument.
**Fix:** Add `_review_code.py`, `_review_discussion.py`, `_review_plan.py` to the edit set and correct the file count.

### [GAP] Shared `prepare()` makes the agent-mode flag un-threadable as stated
**Section:** Decision `output-contract-is-agent-mode-only` → "How the split is enforced, mechanically"
**Issue:** The decision says `build_tool_rule` "takes the existing `mode` plus a flag for agent-mode dispatch" but never says who sets the flag; the obvious site is wrong — `_review_discussion.run():215` and `_review_code.run():629` (the `--stage full` fallback path) both call the *same* `prepare()` that builds the tool_rule, so setting agent-mode inside `prepare()` would poison the exact path this decision exists to protect. `_review_plan.py` is asymmetric: its `prepare()` (401/490) is separate from `run()`/`_review_one_batch` (836/196).
**Fix:** State that the flag is a parameter on each backend's `prepare()` (defaulting to non-agent), set true only by the CLI `--stage prepare` branches, and call out the plan/code/discussion asymmetry — mirroring the "who substitutes what" precision already given for `write_brief`.

### [GAP] `output_path` in "every prepare envelope" has an unhandled exception
**Section:** Scope item D + Decision `output-path-in-prepare-envelope` + Testing → "Prepare-envelope shape"
**Issue:** `_implementer_common.emit_prepare_no_dispatch` (`:796`) emits a prepare envelope with `dispatch_needed: false` for the merge-in verify-fix pass case — no brief is written, so there is no `.out.md` path to echo. The stated invariant ("`output_path` present for every prepare-emitting CLI") is false as written and the shape test would fail on `millpy-merge-in-subagent.py --mode verify-fix`.
**Fix:** Carve out `dispatch_needed: false` envelopes explicitly in both the decision and the test description.

### [NOTE] Group 5's description of the three implementer-family CLIs is inaccurate
**Section:** Technical context → Group 5
**Issue:** `millpy-implement.py:46`, `millpy-fix.py:44`, and `millpy-merge-in-subagent.py:52` all import and call `_implementer_common.emit_prepare`, which constructs the envelope itself — they "forward" nothing and likely need zero edits, so the 26-file count is inflated here even as it is short by three elsewhere.
**Fix:** Recheck those three entries when correcting the edit set.

### [NOTE] `mill-implementer.md` not in the edit set despite an ambiguous output clause
**Section:** Technical context → Group 1 (agent definition, 1 file)
**Issue:** `plugins/mill/agents/mill-implementer.md:20` says "report structured status when done" with no channel named; under the new contract that reads as "in your final message", the same contradiction being swept out of the reviewer definition.
**Fix:** Either add it to Group 1 with an explicit `<OUTPUT_FILE>` wording, or state why the brief-level fix is considered sufficient.

## Verdict

GAPS_FOUND
Edit set is incomplete and the tool-rule flag has no stated threading path.
MILL_REVIEW_END
