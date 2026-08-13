MILL_REVIEW_BEGIN
# Review: mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-13
```

## Findings

No findings. Verified all five batches against their cards:

- Batch 1 (#833): `_paths.resolve_hub_path` terminal fallback changed `return main_root` -> `return git_root` exactly as specified; docstring updated to match. Regression test in `test-paths.py` reproduces the exact scenario via a real `git worktree add` fixture with no `.millhouse/` in the linked worktree, asserting `got == linked_worktree`.
- Batch 2 (#834): `millpy-spawn.py` adds the unconditional defensive self-heal write for `dest_hub/.millhouse/config.local.yaml` immediately after `copy_millhouse`, using the already-bound `dest_hub`/`hub_subpath`, unrelated to the existing gated worktree-root stub block. Both new regression tests (`test_spawn_self_heals_missing_config_local_yaml_standard_layout` / `_subfolder_layout`) exercise `omit_source_config=True` and assert exact YAML content for both layout variants; registered in `tests = [...]`.
- Batch 3 (#825): `_in_scope_dirty_stuck` re-scoped to `git diff --name-only start_sha` ∩ `git status --porcelain`, guard extended to include `start_sha is None`, docstring explains the deliberate scope narrowing vs. `compute_terminal_dirt`, call site updated to pass `start_sha`. Cases 73-75 correctly respect the no-content-commit gate ordering (intervening non-"mill-go: start batch" commits before capturing dirt) and cover the negative, never-committed-positive, and disable-guard scenarios.
- Batch 4 (#818): `_parent_diff_names`/`compute_terminal_dirt`/`revert_out_of_scope_drift` all propagate `None` on unresolvable parent diff, matching the exact code shown in cards. `handoff.md` and `SKILL.md` step 2b both gained explicit `is None` halt/blocked branches, worded per the cards, with `_implementer_common._in_scope_dirty_stuck` correctly left out of this propagation (consistent with batch 3's independent `start_sha` scope). `test-cleanliness.py` updates PDN-1 to assert `None`, adds CTD-6 between CTD-5 and PDN-1, and adds the new unresolvable-parent-diff ROOD case — the implementer correctly numbered it ROOD-7 (not literally "ROOD-5" as the card's prose suggested) since pre-existing ROOD-5/ROOD-6 blocks (#640 nested-hub-layout regressions) already occupied those slots; functionally it is inserted after all existing ROOD-* blocks per the card's actual intent.
- Batch 5 (#812): `review-discussion.md` Criteria section gained the `**Tooling/validator claims**` bullet with the `PYTHONPATH=` example, inserted at the specified position; four-class rubric untouched. `test-review-discussion-flow.py` adds the standalone read-and-assert test and registers it in `main()`.

No out-of-plan files, no cross-batch contract violations (all five batches are independent root batches per the `five-independent-bugs-no-shared-code` decision), no duplicated helpers, and each file's pre-existing test-harness convention was followed per the `existing-test-harness-conventions-per-file` decision.

## Verdict

APPROVE
All five independent batches match their cards exactly; tests, docs, and call sites are consistent end-to-end.
MILL_REVIEW_END
