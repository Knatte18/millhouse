# Review: 27 (A) — Prune unused skills and scripts

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: discussion.md
date: 2026-05-07
```

## Findings

### [NOTE] SCRIPTS.md regen command uses source-tree path
**Section:** Technical context — SCRIPTS.md regeneration
**Issue:** The example command uses `uv run --project plugins/mill plugins/mill/scripts/millpy-<name>.py --help`, which violates the CLAUDE.md agent-level convention against source-tree paths (only unit-test invocations are exempt).
**Fix:** Replace with `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-<name>.py" --help` so the plan writer doesn't copy a non-compliant form verbatim.

### [NOTE] No explicit sweep for cross-references to deleted entities
**Section:** Scope — Edit items
**Issue:** The scope identifies one cross-reference (mill-setup/SKILL.md:463), but does not state that a search across all SKILL.md and script files for `mill-list`, `mill-fetch-issues`, and `mill-worktree` was performed and found nothing else.
**Fix:** Add a one-line confirmation ("searched all SKILL.md and millpy-*.py files; no other references found") so the plan writer knows the single edit is exhaustive.

## Verdict

APPROVE
Discussion is complete and well-reasoned; two minor notes, no gaps blocking plan writing.