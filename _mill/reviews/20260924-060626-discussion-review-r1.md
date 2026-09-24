MILL_REVIEW_BEGIN
# Review: Auto-name task sessions <slug>:<phase>

```yaml
duration_s: 36.6
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-24
```

## Findings

### [NIT:decision] Config change after spawn leaves tasks.json stale
**Demoted-from:** BLOCKING
**Section:** Config shape / tasks.json ownership **Issue:** model/effort are baked into tasks.json at spawn time (and at mill-setup for the hub), but "easy to change" and the per-worktree `config.local.yaml` override are stated with no way to re-render an existing worktree's tasks.json. **Fix:** State the disposition: a re-render path (e.g. a helper or setup re-run), or explicitly accept and document that edits only affect newly spawned worktrees.

### [NIT:design] Conflict detection method for JSONC keybindings unspecified
**Section:** Keybindings are global **Issue:** The block is inserted textually, but detecting an existing `alt+shift+N` binding outside the block needs comment-tolerant parsing, and the discussion does not say how (strip comments and parse vs regex). **Fix:** Name the approach and what happens when the file cannot be parsed (skip all and warn).

### [NIT:design] Hub session name and unverified launch assumptions
**Section:** Slug source / Technical context **Issue:** The hub gets `<repo-name>:<phase>` names, which is fine, but the `/mill-x` initial prompt executing as a slash command and the `commandsToSkipShell` need are load-bearing and both deferred to plan. **Fix:** Add a fallback if the slash-prompt does not execute (e.g. the prompt is passed as plain text).

## Verdict

APPROVE
Stale baked config after spawn has no stated disposition; the rest is sound and source-consistent.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
