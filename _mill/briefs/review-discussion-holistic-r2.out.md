MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-12
```

## Findings

### [GAP] Missing `.out.md` crashes finalize, not "no new machinery"
**Section:** Decision `missing-out-md-defers-to-git-state` / Testing
**Issue:** The claim that an absent file "is treated as empty agent text" and that review CLIs "produce the existing `verdict: ERROR` envelope" is false against source: `_implementer_common.py:892` does `Path(agent_output_path).read_text(...)` with no existence guard and `millpy-implement.py:402` calls it with no `try`, so an absent file raises an uncaught `FileNotFoundError`; the three review CLIs (`millpy-review-discussion.py:146`, `millpy-review-plan.py:185`, `millpy-review-code.py:183`) wrap the read in `except ReviewError` only, which `FileNotFoundError` does not satisfy — no envelope is printed and the CLI exits with a traceback. Empty/whitespace files do behave as described (no-JSON inference / `parse_verdict` -&gt; `ReviewError` -&gt; ERROR envelope); *missing* does not.
**Fix:** State explicitly that the four read sites gain a missing-file guard (read -&gt; `""` when absent) so a missing file degrades to the empty-text path, and scope that guard as part of the change rather than asserting existing machinery already covers it.

### [GAP] Who substitutes `&lt;OUTPUT_FILE&gt;` is unspecified and as written impossible
**Section:** Decision `output-path-in-prepare-envelope` / Scope C
**Issue:** "The orchestrator passes it verbatim to `--agent-output` and to the brief's `&lt;OUTPUT_FILE&gt;` token" cannot work: the brief is fully rendered and written by `--stage prepare` via `_agent_dispatch.write_brief()` (`_agent_dispatch.py:96-120`) before the orchestrator ever sees the envelope, and the brief path — hence the `.out.md` path — is only computed *inside* `write_brief`, after template rendering. The orchestrator has no mechanism to inject a token into an already-written file.
**Fix:** Name the substitution owner: `write_brief` (which knows `brief_path`) resolves `&lt;OUTPUT_FILE&gt;` / appends the output-contract footer, and the envelope's `output_path` is merely a read-only echo of the same helper's result.

### [GAP] Warm-`SendMessage` resume still mandates the old JSON-in-chat contract
**Section:** Decision `ack-is-the-completion-discriminator` — "Affected edits"
**Issue:** The affected-edits list covers steps 4(a), 4(b), 5, 6 and `:135`, but not step 6.5's `SendMessage` payload at `mill-go/SKILL.md:161`, which literally instructs the warm-resumed implementer to "emit the required JSON report as your final line" (and `:163` tells the orchestrator to write that message to `.out.md`). Left unchanged, a warm-resumed implementer returns a full JSON report in chat — re-bloating the Builder and returning a payload the new ack classifier does not recognise.
**Fix:** Add step 6.5 / `:161` to the affected-edits list, specifying the new `SendMessage` wording ("finish remaining cards, run verify, rewrite `&lt;OUTPUT_FILE&gt;`, reply with the ack") and the deletion of the re-capture instruction at `:163`.

### [NOTE] Sweep file count stated three ways (seven / twelve / +2)
**Section:** Scope C vs. Technical context
**Issue:** Scope C says "sweep **all seven** files" but then enumerates twelve (agent def + `mill-go/SKILL.md` + 5 review templates + 5 brief templates), matching Technical context's "twelve files"; separately, `mill-start/SKILL.md:152` and `mill-plan/SKILL.md:111` (stale rationale) and `mill-start/SKILL.md:117-125` (item A) must also be edited but appear in neither list — the real edit set is ~15 files. All cited line numbers verified correct.
**Fix:** Correct "seven" to twelve and give one authoritative edit-set list that the conformance test enumerates.

### [NOTE] Step 4(a)'s transient heuristic now matches a successful ack
**Section:** Decision `ack-is-the-completion-discriminator`
**Issue:** 4(a) currently keys on "raw API error ... roughly 0 tokens, no `MILL_REVIEW` block and no `status` JSON" (`mill-go/SKILL.md:129`). Post-change, *every successful* payload is ~0 tokens with no review block and no JSON; only the error-marker clause separates them, so the heuristic's negative signals become misleading noise.
**Fix:** State that 4(a) is reworded to key solely on the error marker, and that the ack test is evaluated first.

### [NOTE] Duplicate testing bullets
**Section:** Testing
**Issue:** "`write_brief` output-contract footer" and "the `.md` -&gt; `.out.md` helper — TDD candidate" each appear twice (bullets 2 and 8, bullets 1 and 6), suggesting an unmerged edit.
**Fix:** Deduplicate so the plan writer does not create two batches for one test.

## Verdict

GAPS_FOUND
Three source-verified gaps: missing-file crash, unowned `&lt;OUTPUT_FILE&gt;` substitution, unswept warm-resume path.
MILL_REVIEW_END
