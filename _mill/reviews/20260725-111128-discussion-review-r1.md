MILL_REVIEW_BEGIN
# Review: Skill doc/table accuracy gaps across mill-groom, mill-start/mill-plan, and implementer-brief

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] step 4b fix has two edit sites, only one is scoped
**Section:** Scope / Decision `mill-start-discussion-fix-handoff-gap` / Testing
**Issue:** The `discussed`-append fix targets "step 4b," but mill-start/SKILL.md describes the 4b sequence twice — the interactive path (line 220) and the `--auto` subsection restatement (line 37, "append `discussion-fix-r{N}` to the status timeline, single commit"). Scope/Testing name only the singular step 4b; a plan writer following line 37's explicit enumeration could leave the auto path appending only `discussion-fix-r{N}`, keeping the resume window open in exactly the autonomous runs where interruptions matter most.
**Fix:** State whether line 37's `--auto` restatement must also gain the `discussed` append (or be trimmed to rely on its "take the interactive 4b path verbatim" delegation), so both sites are covered.

### [NOTE] mill-groom replacement message string is ambiguous
**Section:** Scope (bullet 1) / Decision `mill-groom-junction-check`
**Issue:** Scope says report "the same 'Run `/mill-setup` first' message on failure," but the current message (SKILL.md line 18) names the junction and must change; the Decision specifies a new string yet contains a garbled artifact ("to report `.millhouse/wiki/` — er, report: 'wiki path could not be resolved. Run `/mill-setup` first.'"), leaving the exact target text unclear.
**Fix:** Pin the single replacement message string explicitly and drop the "same message" wording, since the junction-referencing text is being removed.

## Verdict

GAPS_FOUND
One scope gap on the step-4b edit sites; otherwise claims verify cleanly against source.
MILL_REVIEW_END
