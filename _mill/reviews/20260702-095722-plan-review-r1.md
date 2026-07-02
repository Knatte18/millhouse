I have verified the plan thoroughly against the source files. All line references (across `_status.py`, `_implementer_common.py`, `millpy-implement.py`, `millpy-fix.py`, `millpy-merge-in-subagent.py`, the two fixer templates, and the four SKILL.md files) check out precisely, the batch DAG is acyclic with accurate `depends-on` and existing `file:` targets, global card numbering is sequential 1-19 with no gaps, `--only` accepts multiple test files (`nargs="+"`), and every card is complete with grounded Context. Here is my review.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-02
```

## Findings

### [NIT] Contradictory placement wording for new gate param
**Location:** Batch 2 / Card 3, step 1
**Issue:** Instruction says add `module_verify_baseline` "as a new keyword-only parameter... placed after the existing `module_wide_verify_cmd` parameter," but `module_wide_verify_cmd` sits before the `*` in `_run_verify_gates` (`_implementer_common.py:642-648`), so "after it" is a positional slot while "keyword-only" requires placement after `*`. Harmless in practice (all four call sites and the two forwarders pass it by keyword), but the two clauses conflict literally.
**Fix:** State it goes after the `*` (alongside `git_root`); "keyword-only" is the binding constraint.

## Verdict

APPROVE
Plan is accurate, well-sequenced, and faithful to every discussion Decision; one cosmetic wording nit only.
MILL_REVIEW_END