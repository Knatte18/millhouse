I have enough information to write the review.

# Review: 57 (A) — Move config.yaml and agents.yaml from wiki to hub worktree

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-16
```

## Findings

### [GAP] `_reviewers.load` signature and 9 callsite migrations missing from scope
**Section:** Scope > In / Technical Context — Current agents load path
**Issue:** The discussion defines the two-layer overlay for `_reviewers.load` but never states the new function signature or that the 9 existing callers (`millpy-implement.py`, `millpy-implement-holistic.py`, `millpy-review-*.py`, `_review_discussion.py`, `_review_code.py`, `_review_plan.py`, `millpy-merge-in-subagent.py`) need updating. The current `load(wiki_root)` must change to accept `hub_dir` for the `.millhouse/agents.local.yaml` overlay; none of those callers currently have `hub_dir` in scope.
**Fix:** State the new `_reviewers.load(hub_dir: Path)` signature and add "update N callsites of `_reviewers.load` to pass `hub_dir` instead of `wiki_root`" to Scope > In, parallel to the `load_config` callsite migration item.

### [GAP] Phase 3.1 halt condition is ambiguous
**Section:** Technical Context — mill-setup phases
**Issue:** "Phase 3.1 also halts on operator-error if `wiki/config.yaml` still exists" is unconditional as written. Applied literally — before Phase 3.2b has run — it would halt every pre-migration hub the moment mill-setup starts, preventing Phase 3.2b from ever executing. The intended condition appears to be: halt only when BOTH `mill-config.yaml` and `wiki/config.yaml` exist simultaneously (interrupted-migration state after Phase 3.2b copied but failed to delete the wiki file).
**Fix:** Rewrite as "Phase 3.1 halts with an operator-error message if `mill-config.yaml` already exists at the hub root AND `wiki/config.yaml` still exists in the wiki (interrupted migration — Phase 3.2b copied the file but the wiki delete did not complete)."

## Verdict

GAPS_FOUND
Two plan-blocking gaps: `_reviewers.load` API change unscoped, and Phase 3.1 halt condition as written would block migration of any pre-migration hub.