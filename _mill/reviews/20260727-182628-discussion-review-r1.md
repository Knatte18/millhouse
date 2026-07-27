MILL_REVIEW_BEGIN
# Review: Merge-in conflict handling: silent marker-verification gaps, mill-config.yaml chicken-and-egg crash, and undocumented dirty-worktree squash failure

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: /home/knatte/Code/millhouse/wts/mill-merge-conflict-robustness-gaps/_mill/discussion.md
date: 2026-07-27
```

## Findings

### [GAP] Second unguarded YAML parse missed by #706 fix
**Section:** Decisions / config-yaml-crash-fallback (#706)
**Issue:** `_config.load_config`'s cache-lag template-augmentation loop (`_config.py:229`, `yaml.safe_load(_candidate.read_text(...))` reading `worktree_root|hub_root / plugins/mill/templates/mill-config.yaml`) is unguarded and git-tracked for the self-hosted millhouse repo, exposed to the identical crash shape as the line-239 parse the Decision fixes. This contradicts the Rationale's claim that the repo-layer file is "the only git-tracked config source" that can carry merge markers.
**Fix:** State whether line 229's parse is also in scope for the same try/except, or give an explicit reason it's excluded.

### [GAP] Discarded-field wording mismatch for kept-both case (#718)
**Section:** Decisions / merge-in-semantic-duplication (#718)
**Issue:** `mill-merge-in/SKILL.md`'s existing row tells the operator to "verify nothing load-bearing was lost" for a `discarded` entry — accurate for a genuine drop, but inaccurate for a "kept both sides" entry where nothing was lost and the real risk is duplication/self-contradiction. "No new branch needed" is true for control flow but doesn't address message accuracy.
**Fix:** Decide whether the SKILL.md operator-facing text needs a wording addition for the kept-both sub-case, or accept the mismatch explicitly.

### [GAP] Strictness check already correct -- no code fix needed
**Section:** Decisions / config-yaml-crash-fallback (#706), Follow-on; Scope/In
**Issue:** `_review_common.load_config`'s missing-source check (lines 2001-2007) already keys strictly off `resolve_repo_config_path(...) is None` (file existence), never parse success — a present-but-broken repo-layer file cannot trigger a spurious `ReviewError` today, before or after the #706 fix. Scope/In and the Follow-on both frame this as a code change.
**Fix:** Reclassify this item as regression-test-only (matches the Testing section's own phrasing); state no production edit to `_review_common.py` is expected.

### [GAP] Wrong test file named for #713 marker-gate tests
**Section:** Testing / conflict marker gate
**Issue:** `test-merge-in-subagent.py`'s docstring and every case ("Unit tests for millpy-merge-in-subagent.py verify-fix success gating") are verify-fix-mode only; all existing conflicts-mode coverage (`test_1_conflicts_success`, `test_15_stage_finalize_conflicts`, etc.) lives in `test-millpy-merge-in-subagent.py`. Listing both with "/" risks new marker-gate fixtures landing in the wrong file.
**Fix:** Name `test-millpy-merge-in-subagent.py` as the sole target for the new conflicts-mode marker-gate tests.

## Verdict

GAPS_FOUND
Two source-verified scope gaps (residual crash path, discarded-field wording) plus two lower-cost clarifications.
MILL_REVIEW_END
