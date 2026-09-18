# Batch: fork-echo-fallback

```yaml
task: 'mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation'
batch: fork-echo-fallback
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Single-card batch: extend `plugins/mill/skills/mill-start/SKILL.md`'s "Fork echo caution" paragraph (Phase: Explore) with a documented fallback for when the paragraph's existing single corrective-retry mitigation also fails to produce grounded findings. No external interface — this is a prose-only change to one skill file, consumed only by a future mill-start session reading its own instructions.

## Cards

### Card 1: Add corrective-retry-failure fallback to Fork echo caution

- **Context:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-start/SKILL.md`, Phase: Explore, the `**Fork echo caution.**` paragraph (the four sentences immediately following the `**Fork scope guardrail.**` paragraph and immediately preceding the `### Phase: Discuss` heading) currently reads:

  ```
**Fork echo caution.**
A fork dispatched via `Agent(subagent_type: "fork")` shortly after the parent has just produced a similarly-shaped text block (e.g. the Step 2 scope digest) may, on its first turn, echo/restate that block instead of executing the assigned investigation directive.
Check the fork's first response for grounded findings (specific file:line citations, quoted code) before trusting it as complete.
If the response is a restatement rather than grounded findings, `SendMessage` the same fork an explicit corrective directive (e.g. telling it to stop restating context and perform the investigation) rather than accepting the echoed response.
  ```

  Append the following two sentences immediately after that last sentence, in the same paragraph (no new heading), each on its own line per this repo's semantic-line-break convention:

  ```
  If the corrective retry's response also fails this same grounded-findings check -- whether by restating/echoing again (potentially echoing different context than the first failure, e.g. the orchestrator's own prior chat text rather than the scope digest) or by any other non-grounded response (near-zero tool use, content unrelated to the assigned investigation) -- abandon forking for this investigation and dispatch a cold agent instead: a cold `Explore` agent for a read-only investigation (per the "Sub-investigation guidance" bullets above), or `general-purpose` when the investigation needs a tool beyond `Explore`'s read-only grant (mirroring `plugins/mill/skills/mill-plan/SKILL.md`'s "Fork scope guardrail" precedent for the identical cold-agent choice).
  Do not send the fork a second corrective directive -- one corrective retry is the limit before switching dispatch mechanisms entirely.
  ```

  Read `plugins/mill/skills/mill-plan/SKILL.md`'s "Fork scope guardrail" paragraph (Phase: Plan) first and adapt its `general-purpose` phrasing ("`general-purpose` when the research needs a tool beyond Explore's read-only grant") to the appended sentence above (which reads "investigation" in place of "research", matching mill-start's own Explore-phase vocabulary) so the two skills describe the same cold-agent choice, in each skill's own consistent terminology.

  Leave the `**Fork scope guardrail.**` paragraph, the "Sub-investigation guidance" bullet list, and every other section of `plugins/mill/skills/mill-start/SKILL.md` unchanged -- this card is scoped to the `**Fork echo caution.**` paragraph only.
- **Commit:** `docs(mill-start): add fork-retry-failure fallback to Fork echo caution`

## Batch Tests

Pure documentation change to `plugins/mill/skills/mill-start/SKILL.md`'s prose guidance -- no runnable surface, hence `verify: null`. Verification is a manual read-through: confirm the appended text (a) reads correctly in place as a continuation of the existing paragraph, (b) does not contradict the Fork scope guardrail paragraph or mill-go-base/SKILL.md's "Why not fork?" paragraph, and (c) uses the same `general-purpose`/`Explore` vocabulary as mill-plan's "Fork scope guardrail" precedent.
