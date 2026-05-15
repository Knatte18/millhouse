I have all the source verification I need. Writing the review now.

# Review: 55 (A) — Fix hardcoded _mill/ paths and mill-setup junction/config bugs

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-15
```

## Findings

### [GAP] Cleanliness snapshot must not follow the "replace all" rule

**Section:** Scope → mill-go; Decisions → Path setup block pattern

**Issue:** The discussion instructs "replace ALL hardcoded `_mill/` path strings," but mill-go SKILL.md line 136 references `<worktree>/_mill/.cleanliness-snapshot-<batch_name>.txt`. `millpy-implement.py` (explicitly out of scope) hardcodes the same path at lines 131 and 261 (`project_root / "_mill" / f".cleanliness-snapshot-{batch_name}.txt"`). If a plan writer applies the "replace all" rule and changes the SKILL.md reference to `task_dir / ".cleanliness-snapshot-..."` on a legacy `task/` worktree, mill-go reads from `task/` but the file was written to `_mill/` → `compute_new_dirt` silently treats pre-batch as empty → the cleanliness gate produces false negatives. `_cleanliness.compute_new_dirt` is verified to only warn on missing snapshot, not fail, so the error is invisible.

**Fix:** Add an explicit carve-out in Scope or Path setup: the cleanliness snapshot path in mill-go SKILL.md must keep its `_mill/` literal (not replaced with `task_dir`), because `millpy-implement.py` writes there unconditionally and that script is out of scope.

### [NOTE] overview_path hardcode not listed in path variables

**Section:** Decisions → Path setup block pattern

**Issue:** mill-go SKILL.md line 62 contains a separate hardcoded `overview_path = Path("_mill/plan/00-overview.md").resolve()` — independent of `plan_dir`. The path setup block lists `plan_dir` but not `overview_path`. The "all subsequent path references use these variables" clause covers it implicitly, but a plan writer enumerating explicit variable definitions may miss this specific site.

**Fix:** Add `overview_path = plan_dir / "00-overview.md"` to the path setup variable list, or call it out as an example of the implicit derivation rule.

## Verdict

GAPS_FOUND

The cleanliness snapshot carve-out is a must-resolve: without it, the plan writer is likely to break the cleanliness gate silently on legacy worktrees.