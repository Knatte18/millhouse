MILL_REVIEW_BEGIN
# Review: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-15
```

## Findings

### [NIT] Decision text contradicts batch-2 dependency
**Location:** 00-overview.md / Decision: six-independent-fixes
**Issue:** The decision states "no inter-batch dependencies (all `depends-on: []`)", but batch 2 declares `depends-on: [1]` because Card 1 and Card 2 both edit `_review_common.py` (verified: both list it in Edits) — the same overlap rationale used for the #469/#462 merge, but not reflected in the decision narrative.
**Fix:** Amend the decision to note that config-repo-layer chains after review-warning-ascii for the same shared-file (`_review_common.py`) reason it cites for the wiki merge.

### [NIT] Card 12 sets env flag implemented only in later Card 13
**Location:** 05 / Cards 12, 13
**Issue:** Card 12 (mill-finalize) sets `MILL_FINALIZE_PR_CLEANUP=1` expecting git-pr to skip its guard, but the guard-skip reader is added in Card 13 which is sequenced after — so the integration is incomplete at Card 12's commit point.
**Fix:** Reorder so the git-pr guard-skip (Card 13) lands before the mill-finalize change that depends on it (Card 12), or note they ship together.

### [NIT] git-pr config-resolution invocation underspecified
**Location:** 05 / Card 13
**Issue:** git-pr/SKILL.md is a pure bash + git skill; Card 13 asks it to "resolve via `_config.load_config` + `_paths.resolve_task_path`" without specifying the cache-form Python invocation (`PYTHONPATH=... "$MILL_PYTHON" ...`) the implementer must emit.
**Fix:** State the script-invocation form inline, or scope Card 13 to the env-flag skip plus literal-path fallback (which needs no Python) and defer config resolution.

## Verdict

APPROVE
Plan is well-grounded against source; only minor decision-text and ordering nits.
MILL_REVIEW_END