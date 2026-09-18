# Discussion: mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation

```yaml
task: mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation
slug: mill-start-explore-fork-dispatch-failure
status: discussing
parent: main
```

## Problem

`mill-start/SKILL.md`'s Phase: Explore "Sub-investigation guidance" recommends `Agent(subagent_type: "fork")` for scoped research that needs the parent's already-in-context reasoning, and its "Fork echo caution" paragraph already anticipates one failure mode: a fork echoing the parent's just-produced scope-digest text on its first turn, with a documented mitigation (send the same fork one corrective directive).

GitHub issue #993 reports a worse failure that the current text doesn't cover. During a real Explore-phase run with a well-specified 5-bug investigation prompt, two consecutive fork dispatches both produced zero grounded findings:

- **Attempt 1** — a detailed investigation prompt (5 numbered file/line targets, instructions to write findings to a `.scratch/` file) returned a `result` discussing unrelated `ScheduleWakeup` scheduling semantics — content matching nothing in the prompt. `tool_uses: 2`, `duration_ms: 14617`. The target output file was never created.
- **Attempt 2** — the documented corrective-directive retry (per "Fork echo caution") returned in 1.3s with `tool_uses: 0`, and its `result` field verbatim-echoed the orchestrator's own immediately-preceding chat turn ("Retry investigation fork launched. Waiting for it to complete before continuing.") — not a response to the investigation prompt at all.

So the single corrective retry the SKILL currently prescribes is not a reliable recovery step — it can itself fail, more severely (0 tool_uses, echoing the wrong content) than the case it was designed to catch. The SKILL currently gives no further guidance once the corrective retry also fails; an orchestrator following it as written has no next step other than trusting a non-answer or manually giving up on forking, which is exactly what the issue reporter did ("abandoned forking entirely for this investigation and performed the reads directly").

**Why now:** this is a real dispatch reliability gap discovered in production use (2026-09-04, branch `hanf/mill-merge-finalize-codeguide-bugs`), not a hypothetical — the reporter had to invent an ad hoc workaround mid-task because the SKILL's own guidance ran out.

## Scope

**In:**
- Extend `mill-start/SKILL.md`'s "Fork echo caution" paragraph (Phase: Explore) with a documented fallback: when the corrective retry (the existing single-`SendMessage` mitigation) *also* fails to produce grounded findings — whether by restating/echoing again, or by any other non-grounded response (near-zero `tool_uses`, content unrelated to the assigned investigation) — abandon forking for that investigation and dispatch a cold agent instead, per the options already listed in the same phase's "Sub-investigation guidance" bullet (`Explore` for read-only sweeps, `general-purpose` when the investigation needs a tool beyond `Explore`'s read-only grant).
- Keep the fallback text co-located with "Fork echo caution" (same paragraph/heading) rather than introducing a new heading, since it's a direct extension of that paragraph's existing recovery guidance.

**Out:**
- No change to the "Fork scope guardrail" paragraph (incident #919's mitigation) — that addresses a different failure mode (a fork acting on inherited pipeline instructions instead of its narrow directive) and is unaffected by this fix.
- No change to `mill-go-base/SKILL.md`'s "Why not fork?" paragraph or to mill-plan's own "Fork scope guardrail" — both already default to cold agents and are not the site of the reported failure.
- No change to the Agent tool's own dispatch mechanics, retry/timeout behavior, or any millhouse Python script — the observed failure (a fork returning unrelated/echoed content) is a property of fork dispatch fidelity itself, which this repo cannot fix in code; only prompting-level guidance (when to stop trusting a fork and switch tools) is actionable here.
- No change to how non-Explore-phase forks are handled (mill-plan's Phase: Plan research dispatch, mill-go2's implementer override) — issue #993 is specific to mill-start's Explore phase, and mill-plan already defaults to cold agents by preference (its "Fork scope guardrail" already says "prefer a cold, non-fork agent … whenever the research does not genuinely need the parent's already-in-context reasoning"), so it isn't exposed to the same gap.

## Decisions

### Fallback trigger: broaden beyond "still an echo"

- Decision: The fallback fires whenever the corrective retry's response fails the same grounded-findings check the SKILL already applies to the first response (specific file:line citations, quoted code) — regardless of *how* it fails. Attempt 2 in the issue wasn't a second echo of the parent's scope digest; it was a verbatim echo of a *different* piece of context (the orchestrator's own prior chat line) with `tool_uses: 0`. A trigger worded narrowly as "still echoing the scope digest" would not have caught it.
- Rationale: the SKILL cannot enumerate every way a fork dispatch can misfire (unrelated content, wrong-context echo, zero tool use, timeout-shaped fast return). Defining the trigger by the existing grounded-findings check's failure — not by the failure's shape — keeps the guidance general and matches how the SKILL already frames the *first* check.
- Rejected: enumerating specific failure signatures (e.g. "if `tool_uses == 0`" or "if the response echoes recent chat text") — too narrow, would need updating every time a new failure shape surfaces, and the issue itself shows two different shapes in one incident.

### Fallback destination: reuse existing cold-agent options, don't invent a new path

- Decision: On fallback, dispatch a cold agent using the same choice already documented one paragraph earlier in "Sub-investigation guidance" — `Explore` for a read-only investigation, `general-purpose` if the investigation needs a tool beyond `Explore`'s read-only grant. No new agent type or dispatch mechanism.
- Rationale: `mill-go-base/SKILL.md`'s "Why not fork?" paragraph already documents that a fresh `Agent()` call is the reliable default nearly everywhere else in mill; mill-plan's own "Fork scope guardrail" already prefers cold agents by default for the identical reason (fork's inherited tool access, ignored `model` override). Reusing the same two options keeps this fix consistent with the rest of the codebase instead of adding a third fork-adjacent pattern that would need its own justification.
- Rejected: "do the reads inline" (the issue reporter's own workaround) as the *documented* fallback — inlining is always implicitly available (per the existing "Small question … just explore inline" guidance) and doesn't need restating; documenting a *delegated* fallback (cold agent) is the more useful addition because it's the option that wasn't previously available once forking was ruled out.

### Placement: extend in place, not a new heading

- Decision: Add the fallback sentence(s) directly to the existing "Fork echo caution" paragraph in `mill-start/SKILL.md`, immediately after its existing corrective-retry sentence.
- Rationale: it is a continuation of the same recovery sequence (first check → corrective retry → this fix's new "retry also failed" branch), not a separate concern; a new heading would fragment one coherent piece of guidance across two locations.
- Rejected: a new top-level "Fork retry fallback" heading — would separate the trigger condition from its mitigation, forcing a reader to cross-reference two headings to follow one recovery flow.

## Technical context

- File to edit: `plugins/mill/skills/mill-start/SKILL.md`, Phase: Explore, the "Fork echo caution" paragraph (currently 4 sentences, immediately following the "Fork scope guardrail" paragraph and immediately preceding `### Phase: Discuss`).
- Current text ends with: "If the response is a restatement rather than grounded findings, `SendMessage` the same fork an explicit corrective directive (e.g. telling it to stop restating context and perform the investigation) rather than accepting the echoed response." The new sentence(s) append after this, describing the fallback when that corrective directive's response *also* fails the grounded-findings check.
- Reuse the exact cold-agent vocabulary already present two paragraphs earlier in the same phase's "Sub-investigation guidance" bullet ("use a cold `Explore` agent instead", "`general-purpose` when the research needs a tool beyond Explore's read-only grant" — the latter phrase is mill-plan's wording per `mill-plan/SKILL.md`'s "Fork scope guardrail"; mill-start's own bullet currently only names `Explore` for the "broad mechanical sweep" case, not `general-purpose` — mill-plan is the precedent to follow for the `general-purpose` fallback option since mill-start doesn't currently mention it as a cold-agent choice at all).
- No script, template, or config file is affected — this is a single-file, single-paragraph prose change to a skill's instructions. `mill-skills-index` regeneration is not needed (SKILL.md body content, not frontmatter).
- Related paragraphs to stay consistent with, but not edit: "Fork scope guardrail" (same phase, incident #919 mitigation) and `mill-go-base/SKILL.md`'s "Why not fork?" (lists mill-start's Explore phase as one of only three fork-usage sites in the repo — this fix doesn't add a fourth site or remove this one, it only refines the recovery path at the existing site).

## Testing

- This is a natural-language SKILL.md instruction, not executable code — no unit test applies (`plugins/mill/unit_tests/` covers `_*.py` helpers, not skill prose).
- Verification is read-through: confirm the new fallback sentence(s) (a) don't contradict "Fork scope guardrail" or `mill-go-base/SKILL.md`'s "Why not fork?" paragraph, (b) use the same cold-agent vocabulary as the "Sub-investigation guidance" bullet in the same phase, and (c) read correctly in place — a fresh reader following "Fork echo caution" top-to-bottom reaches an actionable next step even when the corrective retry itself fails, instead of running out of guidance as the current text does.
- No `verify:` command is meaningful for this change (plan's batch, if any, should mark verification as a manual read-through rather than a `PYTHONPATH=` test invocation).

## Q&A log

- **Q:** Should this fix change dispatch code/mechanics, or only the SKILL.md guidance text? 1) Doc-only fix to `mill-start/SKILL.md`'s "Fork echo caution" paragraph (Recommended) 2) Add code-level retry/validation logic around fork dispatch 3) Change the Agent tool's fork semantics itself **A:** [auto-pick] Doc-only fix to `mill-start/SKILL.md`'s "Fork echo caution" paragraph. **Why:** the observed failure (fork returning unrelated/echoed content) is a property of fork dispatch fidelity that this repo has no code-level lever over; only prompting-level guidance on when to stop trusting a fork is actionable, and that's exactly what the issue's own suggested fix proposes.
- **Q:** How should the fallback trigger be worded — narrowly (only "still echoing the same scope-digest text") or broadly (any non-grounded response on the corrective retry)? 1) Broadly: any response that fails the same grounded-findings check as the first attempt (Recommended) 2) Narrowly: only a second echo of the identical scope-digest content **A:** [auto-pick] Broadly. **Why:** the issue's own attempt 2 was a different failure shape (echoing unrelated chat text, `tool_uses: 0`) than attempt 1 (unrelated topic drift) — a narrow trigger keyed to "still echoing the scope digest" would not have caught either actual attempt.
- **Q:** What should the fallback dispatch to — a cold `Explore`/`general-purpose` agent (reusing the SKILL's existing cold-agent options), or something new? 1) Reuse the existing `Explore`/`general-purpose` options from "Sub-investigation guidance" (Recommended) 2) Introduce a new dedicated fallback agent type or dispatch pattern **A:** [auto-pick] Reuse the existing options. **Why:** consistent with mill-plan's own "Fork scope guardrail" (already prefers cold agents by default) and `mill-go-base/SKILL.md`'s "Why not fork?" rationale; avoids adding a third fork-adjacent pattern needing its own justification.
- **Q:** Should the new guidance live in a new heading, or extend "Fork echo caution" in place? 1) Extend "Fork echo caution" in place (Recommended) 2) Add a new "Fork retry fallback" heading **A:** [auto-pick] Extend in place. **Why:** it's a continuation of the same recovery sequence (check → corrective retry → this fix's new branch); a new heading would fragment one coherent recovery flow across two locations.
