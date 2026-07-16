MILL_REVIEW_BEGIN
# Review: mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-16
```

## Findings

### [NIT] Phase-gate slug check uses strict parser without a guard
**Location:** `plugins/mill/skills/mill-merge/SKILL.md:48` (Entry Step 5)
**Issue:** The mismatch check calls `_status.read_full(status_path)["yaml"].get("slug")`, which raises `ValueError` if the foreign/corrupted file's ``` ```text ``` ``` timeline fence is missing or malformed — unlike `_parent_branch.py`'s tolerant hand-parsing, this path has no exception guard, so a genuinely malformed (not just mismatched-slug) status.md would crash rather than fall through to the wiki lookup this whole task is meant to make robust.
**Fix:** Wrap the raw-slug read in a try/except (or note explicitly why it's out of scope), mirroring `_parent_branch._read_parent_from_status`'s tolerance for malformed input.
Note: this exact unguarded pattern already exists at lines 63-64/105 for `cached_task`/`cached_task_description` reads, so this is a pre-existing codebase convention, not a new deviation introduced by this batch — kept as NIT rather than BLOCKING for that reason.

### [NIT] Stale step-number reference beside the edited section
**Location:** `plugins/mill/skills/mill-merge/SKILL.md:33`
**Issue:** Entry Step 1's in-place-mode note says "omit the `-C <parent-path>` flag" for "Step 4 (Direct path)", but the actual squash logic Card 8 just edited lives in "### 5. Direct squash" — the numbering is already stale (pre-existing, not touched by this batch's cards) and sits right beside the section this plan modified.
**Fix:** Update the cross-reference to "Step 5" while in the area (out of this plan's card scope, but worth a follow-up note).

## Verdict

APPROVE
Implementation matches all four batches' cards and shared decisions; only two non-blocking NITs found.
MILL_REVIEW_END
