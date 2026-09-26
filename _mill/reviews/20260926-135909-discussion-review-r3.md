MILL_REVIEW_BEGIN
# Review: mill-merge: run the deterministic path as one script

```yaml
duration_s: 276.7
verdict: APPROVE
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:design] In-place mode skips the fetch that squash-landed-detection assumes
**Section:** Decision `squash-landed-detection`, last bullet ("In-place mode applies the same checks...")
**Issue:** Checks 1–2 compare against `origin/<parent_branch>`, but the only step that fetches it (`git -C <parent-path> fetch origin`) is the pre-squash ff-only step, which Entry's "In-place mode bypass" explicitly skips for `mode == 'inplace'`. In-place runs can evaluate "landed"/"unpushed" against a stale remote-tracking ref.
**Fix:** State explicitly whether in-place mode fetches `origin/<parent_branch>` before running squash-landed-detection, or note that a stale ref only causes a redundant (self-healing, "nothing to commit") re-squash attempt, never a false "landed" positive.

## Verdict

APPROVE
One low-impact NIT; no blocking gaps found on this pass.
MILL_REVIEW_END
