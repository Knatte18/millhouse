MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based fixer (NIT-fix) dispatch — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (per environment metadata; own confidence moderate)
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [BLOCKING:scope] Card 4 Context omits _status.py despite naming its exact signatures
**Location:** batch 2 / Card 4. **Issue:** Requirements verbatim-quote `_status.append_fork_fallback_log(status_path, scope, N, _timestamp.now_utc_iso())` and `_status.read_fork_fallback_log(status_path)` with a specific argument order, but Card 4's `Context:` lists only `mill-go/SKILL.md`, `mill-go-base/SKILL.md`, `test-mill-go-variants.py` — never `plugins/mill/scripts/_status.py` or `unit_tests/test-status.py`, the files that finalize those two signatures in batch 1. **Fix:** Add `plugins/mill/scripts/_status.py` (or `unit_tests/test-status.py`) to Card 4's `Context:` so the implementer can confirm the verbatim block's call signatures against the finalized batch-1 API rather than trusting the cross-batch scope-note alone.

### [BLOCKING:consistency] mill-go2 frontmatter description becomes false after this batch
**Location:** batch 2 / Card 4, `plugins/mill/skills/mill-go2/SKILL.md` frontmatter. **Issue:** The file's `description:` reads "Behaviourally identical to /mill-go today" — true before this plan, false the moment Card 4 lands the `### fixer` fork-dispatch override (mill-go2 now dispatches the fixer differently from mill-go). Card 4's Requirements say what to leave untouched (`## Driver preamble`, `## Variant binding`, the shared closing paragraph) but never mention the frontmatter, so a literal reading leaves a now-inaccurate claim in place. **Fix:** Either add an explicit Card 4 requirement to update the `description:` line to reflect the fork experiment, or explicitly state it is intentionally left stale and why.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps: Card 4's Context omits the file that defines the exact helper signatures it quotes, and the mill-go2 frontmatter goes stale.
MILL_REVIEW_END
