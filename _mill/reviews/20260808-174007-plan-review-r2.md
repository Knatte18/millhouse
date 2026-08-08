MILL_REVIEW_BEGIN
# Review: Unit test suite: hangs, unmocked-path errors, and stuck/success envelope bug found in piecewise sweep — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-08
```

## Verification notes

Cross-checked every card's cited line numbers, function names, and technical claims against the actual source files (`millpy-claude-sub.py`, `test-claude-sub.py`, `millpy-claim.py`, `test-millpy-claim.py`, `millpy-spawn.py`, `test-millpy-spawn.py`, `wiki/_client.py`, `_implementer_common.py`, `test-bg-json-contract.py`, `test-agent-mode-dispatch.py`, `test-millpy-merge-in-subagent.py`). All line-number citations resolve correctly (several to the exact line, e.g. `_implementer_common.py:1790-1809`, `test-millpy-spawn.py:1301-1339`, `test-agent-mode-dispatch.py:196-198,298,314`). The `test-millpy-spawn.py` "_wiki" stub-key inventory (7 sites: 1 shared helper, 4 standalone-needing-fix, 1 already-correct exemplar, 1 real-filesystem helper not on the failing path) matches Card 3/4's card split exactly (5+4=9 failing tests). The `_forward_output` bug mechanics (unconditional tail block at `:1790-1809` running for any non-`incomplete` status, including already-classified `stuck/*`) is confirmed as a real latent defect in current code, and Card 5's `if status == "success": ... else: print(parsed)` gating correctly implements the `## Shared Decisions` entry without disturbing any earlier early-return path.

Decision alignment, Batch Index DAG (no cycles, all batch files present, `depends-on` accurate), global card numbering (1-9, no gaps), `All Files Touched` scope, Context/Edits completeness, and Requirements specificity are all satisfied. No `Moves:` entries exist in any batch (all `none`), so no Rename mechanic section is required. No forward dependencies; batches 1-3 touch disjoint files and correctly have no cross-dependency; batch 4 correctly depends on all three.

No findings.

## Verdict

APPROVE
Plan is technically sound; every card's claims verified directly against source, decisions faithfully implemented, no structural or sequencing defects found.
MILL_REVIEW_END
