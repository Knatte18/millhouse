MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based fixer (NIT-fix) dispatch

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: /home/knatte/Code/millhouse/wts/mill-go2-fork-fixer/_mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Cold-fallback retry vs. Override point A re-consultation unresolved
**Section:** Decisions `cold-fallback-on-first-terminal-failure` / `fallback-consumes-existing-retry-budget`. **Issue:** the "cold retry" is base step 4(a)/(c)'s own built-in "re-dispatch once immediately" action, not a fresh trip through steps 1-3 — the four dispatch-site instructions explicitly say "follow the Agent-mode dispatch pattern above," but 4(a)/(c)'s retry text does not, so it's undefined whether that retry re-consults Override point A (which is role-scoped only, per its own quoted text — "the role for the current dispatch is the one named by the calling subsection" — with no attempt-number signal) and therefore forks again instead of going cold. **Fix:** state explicitly in Decisions how the `### fixer` override text distinguishes "first dispatch this round" from "step-4's automatic retry" (e.g., a local first-attempt/retry flag the Builder tracks per round), since neither the envelope nor Override point A structurally carries that distinction the way it structurally carries role.

### [BLOCKING:design] `_check_fork_override`'s section-extraction rule breaks on `mill-go`'s own unedited file
**Section:** Testing, TDD candidate 2. **Issue:** the stated extraction algorithm ("from that header line to the next line beginning `## ` or end of file") captures everything under `## Dispatch overrides` through EOF — for both variant files today that includes the trailing "Load the `mill:mill-go-base` skill..." boilerplate paragraph, which sits directly under `## Dispatch overrides` with no separating header (verified: `mill-go/SKILL.md` and `mill-go2/SKILL.md` both place that paragraph immediately after `(none)`, before EOF). The prescribed assertion "mill-go's section body is exactly `(none)` after stripping" therefore fails against the file's actual current structure, not just a future regression. **Fix:** specify a stopping rule that excludes the shared "Load the `mill:mill-go-base` skill" boilerplate (e.g. stop at the first blank line after the override content, or strip a known boilerplate suffix) before asserting body equality.

## Verdict

REQUEST_CHANGES
Two design gaps: fork-vs-cold-retry dispatch-shape ambiguity and a section-extraction rule that fails on the current file.
MILL_REVIEW_END
