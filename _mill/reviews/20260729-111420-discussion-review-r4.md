MILL_REVIEW_BEGIN
# Review: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetxhigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Fix 2 self-run call omits two hub-configurable kwargs
**Section:** Decision — Fix 2 (self-run `_plan_validate.run(...)` call shape)
**Issue:** The specified call mirrors `root`/`git_root`/`wiki_root`/`parent_branch` but drops `max_cards_per_batch`/`max_batch_context_tokens`. The real gate (`millpy-review-plan.py:161-162`) derives both from `cfg.get("pipeline", {})...`; `mill-config.yaml`'s own template documents them as the "batch-oversized validator gate" knobs. Omitting them makes the self-run's `batch-oversized` check silently fall back to hardcoded defaults (10/120000) whenever a hub overrides either value — the same "silently narrows what self-run validates" defect round 3 fixed for the other four kwargs, just for two it missed.
**Fix:** Add `max_cards_per_batch=cfg.get("pipeline", {}).get("max_cards_per_batch", 10)` and the analogous `max_batch_context_tokens` read to the specified call shape.

### [GAP] Fix 4 candidate/root pairing description is wrong when `root` is unset
**Section:** Decision — Fix 4 (`git check-ignore` candidate iteration)
**Issue:** The Decision states resolve_ref_paths's candidates are always 3, "the first and last candidates come from git_root, the middle one from project_root." Verified against `_review_common.py:893-909`: the list is variable-length (1-3 items). When `root` is `None` — the case `_load_root_from_overview`'s own docstring calls "typically empty" for a mill-v2 worktree — only 2 candidates are built, `[project_root/raw, git_root/raw]`; the first comes from `project_root`, not `git_root`, contradicting the stated rule.
**Fix:** Describe the pairing generically — track `(candidate, source_root)` as each candidate is appended, for any list length 1-3 — instead of the fixed 3-slot worked example, so an implementer doesn't hardcode a positional mapping that misattributes roots (running `check-ignore -C` against the wrong repo) in the common root-unset case, which is exactly this self-hosted repo's own layout.

### [GAP] Fix 3's `Edits: ∪ Creates:` union — the `Creates:` half can never match
**Section:** Decision — Fix 3 (Go integration-tag validator check, steps 2-3)
**Issue:** Step 2 collects `Edits: ∪ Creates:` `_test.go` tokens; step 3 gates on `resolve_existing_paths`, which (verified at `_review_common.py:926-990`) silently drops any path not already on disk with no `creates_union` awareness. A `Creates:` target, by this codebase's own established convention, does not exist on disk at plan-validation time (mirrors `resolve_ref_paths`'s creates_union-suppression rationale). So the `Creates:` half of the union can never produce a finding — a batch that creates a brand-new integration-tagged test file with a missing `-tags integration` flag is silently never checked, despite step 2 implying it is covered. (The check's own key, `verify-excludes-edited-tagged-test`, already says "edited," consistent with the real behavior but inconsistent with step 2's stated scope.)
**Fix:** Either drop `Creates:` from the step-2 union to match the check's own name and real coverage, or explicitly document the gap as an accepted, unavoidable limitation (a not-yet-written file's content is unknowable at validation time) rather than implying coverage that cannot occur.

### [NOTE] "No real git" testing-convention claim is inaccurate for `test-plan-validate.py`
**Section:** Technical context (unit test files) / Fix 4 Testing scenario (a)
**Issue:** Technical context claims all three touched test files follow a "no real git" fixture convention "per each file's own docstring." `test-plan-validate.py`'s docstring does say this, but the file already contradicts it: `test_check_verify_unrelated_test_files_flagged_non_main_parent` builds a real on-disk repo via `_test_helpers.init_minimal_git_repo`/`checkout_new_branch` to exercise a real `git diff` subprocess call — exactly the kind of fixture Fix 4's own scenario (a) says it needs for `git check-ignore` but doesn't cite.
**Fix:** Point Fix 4's real-git-repo fixture at the existing `_test_helpers.init_minimal_git_repo` helper instead of re-deriving fixture setup from scratch.

## Verdict

GAPS_FOUND
Three source-verified GAPs: incomplete self-run kwargs, an inaccurate candidate/root pairing description, and dead `Creates:` coverage in Fix 3.
MILL_REVIEW_END
