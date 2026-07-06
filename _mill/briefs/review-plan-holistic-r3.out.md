MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-06
```

## Findings

### [NIT] Batch 1 verify skips its own _implementer_common edits
**Location:** Batch 1 (Cards 3, 4) / batch verify
**Issue:** Batch 1's `verify:` runs only `test-cleanliness.py`, which never imports `_implementer_common.py` or exercises the mill-go SKILL; a botched Card 3 call-site update (or the `git_root is None` flat path) passes green here and only surfaces in Batch 4, which is fine for final merge (DAG order) but lets Batch 1 be marked done with a latent break.
**Fix:** Consider adding `test-millpy-implement.py` (or `test-implementer-common.py`) to Batch 1's verify so the Card 3 signature-threading is gated within the batch that makes the edit.

### [NIT] Card 16 leaves the cwd:git_root relative derivation implicit
**Location:** Batch 4 / Card 16
**Issue:** The explicit `cwd_override_relative` derivation covers only `== project_root` and `is None`; the nested `cwd: git_root` case (module_wide_cwd_override == git_root != project_root) is addressed only in prose ("no git_root-resolved branch needed"), risking an implementer writing an errant `elif == git_root` that calls `relative_to` incorrectly.
**Fix:** State the intended one-liner form: `cwd_override_relative = project_root.relative_to(git_root) if module_wide_cwd_override == project_root else None` so git_root and None both collapse to the tmp_path default.

## Verdict

APPROVE
Plan is accurate, well-sequenced, and byte-identical-safe; only two minor coverage/clarity nits.
MILL_REVIEW_END