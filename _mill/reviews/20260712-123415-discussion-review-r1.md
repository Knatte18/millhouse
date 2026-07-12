MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-12
```

## Findings

### [GAP] missing-out-md=transient collides with `incomplete` recovery
**Section:** Decisions § missing-out-md-is-transient
**Issue:** `mill-go/SKILL.md:135` (clean mid-work stop) deliberately routes a turn-exhausted implementer *through* finalize so `_forward_output`'s no-JSON git-state inference (`_implementer_common.py:999`, `_batch_completeness_stuck`) can reclassify it as `stuck_type: incomplete`; under the new contract that agent writes no `.out.md` at all, so a blanket "missing/empty → transient" short-circuits the inference and drops a partial batch onto the transient retry path — the exact `commits_made > 0` skip-to-cleanliness route `:137` calls the #574 false-success bug.
**Fix:** State the rule per role — for implementer/fixer finalize, a missing `.out.md` must still run the completeness recount (empty text already flows into the inference path) and may only be `transient` when there is no commit evidence; reserve the unconditional `transient` rule for the review CLIs.

### [GAP] Non-review brief templates contradict the one-line ack
**Section:** Scope C / Technical context § "Conflicting instructions that must be swept"
**Issue:** The sweep list names only `mill-reviewer.md`, `mill-go/SKILL.md` and the five review templates, but `implementer-brief.md:102/:127`, `fixer-batch-brief.md:70/:95`, `fixer-holistic-brief.md:76/:101`, `merge-in-conflict-brief.md:56` and `merge-in-verify-brief.md:45` all mandate "your last line of output MUST be a single JSON object" and call anything else a protocol violation — directly contradicting `WROTE <path>`.
**Fix:** Add those five templates to the sweep, and state explicitly what an implementer/fixer/merge-in `.out.md` must contain (the full report including the status JSON, since `_extract_status_json` parses it out of that file).

### [GAP] mill-go's notification classifiers key on payload content that disappears
**Section:** Decisions § one-line-ack-as-final-message
**Issue:** `mill-go/SKILL.md:129` and `:132` classify notifications by inspecting the payload ("no `MILL_REVIEW` block and no `status` JSON" → transient; "non-error, non-JSON message" → clean turn-exhaustion). Under the ack contract a **successful** implementer's payload is exactly "non-error, non-JSON", so every clean success matches the turn-exhaustion trigger; the discussion only proposes rewording the capture steps, not the classifiers.
**Fix:** Define the new discriminator (e.g. presence of the `WROTE <path>` ack = normal completion; classification otherwise defers to `finalize`) and list steps 4(a)/4(b) among the mill-go edits.

### [GAP] `output_path` in the prepare envelope left undecided
**Section:** Technical context § "Single choke point"
**Issue:** "Adding `output_path` to the prepare envelope is worth considering" and Testing hedges "**If** `output_path` is added…" — a plan writer cannot tell whether the envelope schema changes, which also determines whether mill-go/mill-start/mill-plan still string-munge `.md` → `.out.md`.
**Fix:** Decide yes/no and record it as a Decision; if yes, name it as an additive envelope field so the finalize contract constraint still holds.

### [NOTE] Reviewer Write grant is advisory, not enforced
**Section:** Decisions § reviewer-write-grant-scoped-to-briefs / Constraints
**Issue:** `agents/mill-reviewer.md` frontmatter grants tools wholesale (`tools: Read, Grep, Glob`); adding `Write` grants it repo-wide, so "the reviewer must remain unable to touch source code" degrades from a construction-level invariant to a prompt instruction — the rationale's "survives fully intact" overstates it.
**Fix:** Say so plainly, and note whether a permission deny-rule / hook was considered and rejected.

### [NOTE] mill-start has no existing Explore sub-agent dispatch
**Section:** Scope A / Decisions § fork-adopted-in-mill-start-explore
**Issue:** `mill-start/SKILL.md:117-125` (Phase: Explore, Step 3) tells the orchestrator to explore directly with Grep/Glob/git log; there is no Agent dispatch there, so "keep fresh `Explore` agents for broad mechanical sweeps" contrasts against something that does not exist today.
**Fix:** Reframe A as *introducing* sub-investigation dispatch guidance, and say where the guidance text lands.

### [NOTE] Scope E names no target file
**Section:** Scope E / Decisions § decision-note-for-fork-rejection
**Issue:** "Record the fork rejection durably in the repo" specifies no location (codeguide? a doc under `plugins/mill/`? mill-go SKILL.md?), so the plan writer must invent one.
**Fix:** Name the file and roughly the six lines it holds.

## Verdict

GAPS_FOUND
Contract change is sound, but four resolution gaps block plan writing.
MILL_REVIEW_END
