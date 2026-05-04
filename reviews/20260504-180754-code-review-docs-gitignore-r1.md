# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo — docs-gitignore

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: docs-gitignore
date: 2026-05-04
```

## Findings

All three cards are correctly implemented. No blocking issues found.

**Card 13 — CLAUDE.md:** The second bullet in `## Conventions worth carrying` is correctly placed (after the `${CLAUDE_PLUGIN_ROOT}` bullet), paired with a ` ```bash` WRONG/RIGHT fence showing `uv run --project plugins/mill plugins/mill/scripts/millpy-spawn.py` vs the cache form. The `.wiki` invariant note appears as the final bullet in `## Path invariants`. No other section was modified.

**Card 14 — SKILL.md verify pass:** `mill-add/SKILL.md` adds a WRONG/RIGHT pair in "How to call the script"; all downstream examples (`--proposal-body`, file-based) already use `${CLAUDE_PLUGIN_ROOT}`. `mill-setup/SKILL.md` adds a WRONG/RIGHT pair in "How to invoke the helpers" and correctly documents the inline-PYTHONPATH-prefix exception as mill-setup-specific. Verify pass over the remaining skills: `mill-resume` line 127 is descriptive prose (references source path in a `see X for canonical implementation` clause — kept); `mill-skills-index` line 20 is descriptive prose, line 23 operational invocation already uses `${CLAUDE_PLUGIN_ROOT}`; all other operational invocations in `mill-start`, `mill-plan`, `mill-go`, `mill-merge`, `mill-resume` Phase 10 use `${CLAUDE_PLUGIN_ROOT}` correctly. No unreported operational source-tree invocation was found, so the scope gate was not triggered.

**Card 15 — gitignore + test:** `"**/plugins/*/uv.lock"` is appended to `GLOB_ENTRIES` after `"**/portals/"` in `_gitignore.py`. The `.gitignore` mill-managed block contains the entry in the same relative position. The test asserts both membership and placement between `START` and `END` via `block.index()` ordering — correct and unambiguous since neither marker contains the pattern string. The new test integrates with the existing script-style harness. The stale `plugins/mill/uv.lock` file is not deleted, per plan scope.

## Verdict

APPROVE — all three cards fully satisfy their requirements with no defects.