All key technical claims verified. Now composing the review.

# Review: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-11
```

## Findings

### [NOTE] wiki-path-guard Decision self-contradicts on equality timing
**Section:** `### wiki-path-guard`
**Issue:** Decision requires path-equality against the "resolved wiki path" *before any config reading*, but resolving the wiki path IS config reading — those two constraints can't coexist inside `resolve_wiki_path`.
**Fix:** Clarify that `resolve_wiki_path` uses the name check only; the full belt-and-suspenders (name + path equality) lives in `resolve_git_root`, which already calls `resolve_wiki_path` externally.

### [NOTE] Gotchas mixes two test-allowlist approaches with a misleading label
**Section:** `## Technical context` → Gotchas (unit test paragraph)
**Issue:** "OR (preferred) the regex matches `cd .wiki/ && git`" labels the narrow-regex approach as preferred, but the very next sentence explains it still matches and concludes with "use an explicit file allowlist" — making the "(preferred)" label contradictory and potentially confusing a plan writer.
**Fix:** Remove the "(preferred)" qualifier; keep only the final instruction: use the name-check regex from the Decision section plus an allowlist of CLAUDE.md and the eight SKILL.md files.

## Verdict

APPROVE
Discussion is complete; both NOTEs are resolvable in-plan without further alignment.