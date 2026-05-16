I have what I need. Let me write the review.

# Review: 57 (A) — Move config.yaml and agents.yaml from wiki to hub worktree

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-16
```

## Findings

### [GAP] mill-plan has undocumented autonomous_mode callsites
**Section:** Technical Context — `autonomous_mode callsites and intermediate state`
**Issue:** The discussion claims only two live callsites (`mill-autofix/SKILL.md:124`, `mill-go/SKILL.md:232`). Source-verified: `mill-plan/SKILL.md:153` and `:155` also read `pipeline.autonomous_mode` to gate non-progress and max-rounds blocked behaviour. The follow-up task scope names only mill-autofix and mill-go for the flag-file migration; after that lands, mill-autofix will write the flag file instead of the config key, so mill-plan's autonomous_mode gate silently stops working.
**Fix:** Add mill-plan's two callsites to the callsite list; extend the follow-up task scope to include mill-plan alongside mill-autofix and mill-go.

### [NOTE] load_config callsite count understated
**Section:** Technical Context — `Current config load path`
**Issue:** Discussion states "nine lenient callsites and eight strict callsites" (17 total). Grep of `load_config\(` across `plugins/mill/scripts/` returns 29 occurrences across 19 files; subtracting function definitions and docstring mentions yields roughly 24 actual callsites, not 17.
**Fix:** Recount and update the figure; the implementation plan should derive the list from a fresh grep rather than trusting the stated number.

## Verdict

GAPS_FOUND
Mill-plan's autonomous_mode callsites are omitted, making the follow-up task scope incomplete and causing a silent regression after the follow-up lands.