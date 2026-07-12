MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: C:\Code\millhouse\wts\explore-fork-agent-opportunities\_mill\discussion.md
date: 2026-07-12
```

## Findings

### [GAP] Template header rewrite leaks agent-mode prose to `--stage full`
**Section:** Technical context → Authoritative edit set → *Group 2*, bullet 3
**Issue:** The edit set says the header sentence *"Your sole output is the review file in the format below"* **changes, to say the report is written to the file named in the brief and the final message is the ack** — but that is static template prose on the **shared** channel (verified: `review-discussion.md:1-4`, same in the other four), so a `--stage full` reviewer — which has no brief, gets at most `Read,Grep,Glob` (`_llm_claude.py:80`), and whose `_TOOL_RULE_TOOL_USE` still says *"Return review as text"* (`_review_common.py:1223-1228`) — would be told to `Write` a file it cannot write; this is precisely the contradiction `output-contract-is-agent-mode-only` exists to prevent, and it contradicts that Decision's own rule that `build_tool_rule` is "the only channel-aware injection point… all tool permissions must live there and nowhere else". No planned test catches it: the four-cell test only pins `build_tool_rule`, and the conformance sweep only asserts the *agent-mode* direction.
**Fix:** State that the sentence is **deleted** from all five templates (destination + ack live solely in `build_tool_rule`'s two agent cells and `write_brief`'s footer), and add the converse assertion — the rendered `--stage full` `prompt_text` contains no Write/ack instruction — to the conformance sweep.

### [NOTE] Ack-detection predicate is unspecified
**Section:** Decisions → `one-line-ack-as-final-message`, step 4(a) bullet
**Issue:** 4(a) is "reworded to key **solely** on the error marker, with the ack test evaluated **first**" — but no ack predicate is given (prefix match on `WROTE `? regex?), and since 4(a) now keys solely on the error marker and both ack and non-ack clean payloads fall through to `finalize`, the ack test has no stated effect.
**Fix:** Either name the predicate and its branch, or drop the "ack test first" clause and keep the error-marker-only rewording.

### [NOTE] Zombie-writer race on the shared `.out.md` path
**Section:** Decisions → `write-brief-truncates-stale-out-md`
**Issue:** Truncation covers "attempt 1 wrote, attempt 2 died", but not the converse: `mill-go/SKILL.md:129` re-dispatches on a raw API error *without* a liveness probe ("there is no live agent to probe"), and a re-dispatch reuses the same role/scope/round and therefore the same `.out.md`; a still-alive attempt-1 reviewer could now overwrite attempt-2's file (impossible under today's orchestrator-writes contract). 4(c)'s probe closes the stopped/interrupted variant only.
**Fix:** Note the residual window and either accept it explicitly or make the retry's output path attempt-unique.

### [NOTE] Plan batch-scope `prepare()` is not actually reachable
**Section:** Decisions → `output-contract-is-agent-mode-only`, "Who sets the flag"
**Issue:** The claim "`prepare()` takes `scope: str | None`, so batch-scope is reachable even though the hub disables plan batch review (`rounds: 0`)" is wrong: `millpy-review-plan.py:148-151` hardcodes `scope=None` in the `--stage prepare` branch ("Agent mode uses holistic scope only") and `run()` reaches batches via `_review_one_batch`, so `_review_plan.py:401` has no live caller. The instruction (thread the flag into both `:401` and `:490`) is still harmless and correct.
**Fix:** Correct the reachability rationale so the plan does not build a test against a dead path.

## Verdict

GAPS_FOUND
One shared-channel contradiction remains in the template-header edit; everything else verified sound.
MILL_REVIEW_END
