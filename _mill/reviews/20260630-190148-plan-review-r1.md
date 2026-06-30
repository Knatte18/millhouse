All claims verified against source. The plan is tightly grounded: every code anchor cited (parse_batch_refs sub-bullet body at lines 538-542, Check 8 messages at 1191-1205, Check 6 guards at 1073/1095-1107, test blocks, SKILL anchors) exists and matches verbatim. DAG is acyclic with all three files present, global numbering is sequential 1-7, and the file-disjointness claim holds exactly. The existing test assertion at test-plan-validate.py:667 checks only the `"All Files Touched"` substring, which both of Card 3's rewritten messages preserve, so the Card 3 message edit is regression-safe as claimed.

MILL_REVIEW_BEGIN
# Review: Fix plan validator Moves-target gap, code-review backtick parser, and mill-start encoding crash -- holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-30
```

## Verdict

APPROVE
Source-grounded, DAG-clean, numbering sequential, file-disjoint; every cited anchor verified verbatim.
MILL_REVIEW_END