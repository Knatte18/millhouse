# Review: 26 (A) — auto-report-auto-submit

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: discussion.md
date: 2026-05-07
```

## Findings

### [GAP] Section 2 "Invocation modes" missing from scope

**Section:** Technical context / Scope → In

**Issue:** `mill-self-report/SKILL.md` Section 2 explicitly says "The skill receives no argument in this mode" for auto-fire invocations (line 21). After this change, auto-fire passes `--auto`. The discussion's scope and technical context list the frontmatter argument-hint, Step 4 skip logic, and the two call-site changes, but do not call out updating Section 2. A plan writer following the technical context literally will leave Section 2 contradicting the new behavior, and also loses the natural location where `--auto` detection logic should be documented for the LLM.

**Fix:** Add "update Section 2 to replace 'The skill receives no argument in this mode' with the `--auto` invocation description and the skip-Step-4 behavior" to the Scope → In list for `mill-self-report/SKILL.md`.

## Verdict

GAPS_FOUND
Section 2 "Invocation modes" will be left with a direct contradiction unless it is added to scope.