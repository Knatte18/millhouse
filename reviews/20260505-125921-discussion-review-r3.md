Now I have everything I need. Let me write the review.

# Review: 3 (A) — codeguide improvements: sibling placement + --branch flag

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md (codeguide-improvements)
date: 2026-05-05
```

## Findings

### [GAP] Step 9 rule omits how agent resolves the sibling anchor

**Section:** Technical Context → codeguide-generate SKILL.md

**Issue:** The discussion adds a placement rule to Step 9 ("in sibling mode, create `<anchor>/<rel>/_codeguide/`"), but the agent executing Step 9 has no way to obtain `<anchor>` — Step 1 of codeguide-generate runs `resolve.py` without `--json`, which returns only the `cg_root` path, not `sibling_anchor` or `mode`. Computing `<rel>` also requires `git_toplevel`, which codeguide-generate does not fetch. The plan writer cannot write complete Step 9 prose without knowing the intended derivation mechanism.

**Fix:** Specify one of: (a) update Step 1 of codeguide-generate to use `resolve.py --json` so Step 9 can use `sibling_anchor` and `mode` fields; (b) add a sub-step inside Step 9 that runs `_sibling.py codeguide <git-toplevel>` (matching the pattern codeguide-setup Step 4 already uses); or (c) explicitly state that the agent should infer anchor as `cg_root.parent` when `cg_root` is outside the git toplevel. The scope currently says only Step 9 is touched — clarify whether Step 1 is also in scope.

## Verdict

GAPS_FOUND  
Step 9 placement rule is correct but lacks the anchor-derivation mechanism the plan writer needs to write actionable SKILL.md prose.