MILL_REVIEW_BEGIN
# Review: _plan_validate.py context-completeness check: misses bare symbol/identifier references entirely, only matches path tokens

```yaml
duration_s: 215.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] Resolvability-gate root union has no precedence for overlapping roots
**Section:** Decisions > Resolvability gate; Decisions > Reverse path-canonicalization for symbol matches
**Issue:** The walk explicitly *unions* matches from up to three roots (`git_root/root`, `project_root/root`-or-`project_root`, bare `git_root`) rather than trying them in first-match-wins order the way `resolve_existing_paths` does (verified `_review_common.py:1023` docstring: "Resolution order (first match wins)"). When two of these roots nest or coincide — the common case verified from source: `millpy-validate-plan.py:51` never passes `git_root` at all (defaults `None`, collapsing to one root), and `_paths.py:474`'s `hub_relative_path` default `"."` means `project_root == git_root` for in-place/consumer-repo usage (the loomyard/Models repos this task is motivated by) — the same on-disk file is reachable via more than one root simultaneously. The paired canonicalization decision then asks to `.relative_to()` "whichever single root actually produced the match," but with a union search there can be more than one producing root, and `.relative_to()` against different roots yields different relative-path strings for the same file (e.g. `internal/state.go` vs a longer git-root-relative form). Nothing states which root wins, so the canonical string the "Clean, symbol in own Context" test depends on is underdetermined by the decision as written.
**Fix:** Change the resolvability-gate search from "union of matches" to "first-match-wins by the same root ordering `resolve_existing_paths` uses" (stop after the first root that yields any match, only union *within* that one root's walk), so canonicalization always has exactly one unambiguous producing root and its output stays consistent with how `own_refs` tokens are themselves resolved.

## Verdict

REQUEST_CHANGES
Resolvability-gate's root union vs. canonicalization's single-root assumption is unreconciled when roots overlap.
MILL_REVIEW_END
