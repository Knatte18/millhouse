MILL_REVIEW_BEGIN
# Review: mill-plan Entry step 2: _config.load_config called with hub_root/worktree_root swapped vs its own signature

```yaml
duration_s: 322.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-20
```

## Findings

### [BLOCKING:design] "Established convention" premise for the 13-site rename is false
**Section:** Decisions › "Fix approach: rename throughout" (and Technical context items 4/5/9, lines ~49/117/289).
**Issue:** The decision's rationale claims `mill-go-base/SKILL.md` "already uses `hub_root` as the correct, established convention for this exact value," citing lines 512-514. But that snippet is a standalone bash-embedded preflight check, unrelated to Path Setup. mill-go-base's actual structural analog — its own Path Setup (lines 73-86) — binds this same hub-directory value (returned by `_paths.resolve_active_hub`, docstring: "Return the hub directory... for the slug") into a variable named `worktree_root`, then feeds it directly into `_paths.resolve_task_path(worktree_root, ...)` for status_path/plan_dir/reviews_dir — the exact pattern mill-plan uses at its own lines 49/117/289. `_paths.resolve_task_path`'s own parameter is also literally named `worktree_root` (`_paths.py:583`).
**Fix:** Reconcile before renaming: either (a) accept that renaming lines 49/117/289 to `hub_root` recreates the same "argument name doesn't match callee's own parameter name" defect this task exists to fix, just relocated to `resolve_task_path`/`_treeguard.check_and_restore` call sites, or (b) scope the rename more narrowly (e.g., only the `_config.load_config`-adjacent sites) to match the codebase's actual per-callee naming, not a single blanket convention.

### [NIT:consistency] Item 5's section label misidentifies its own location
**Section:** Technical context, "Exact rename sites" item 5 (~line 117).
**Issue:** Labeled "Phase: Plan Review's own 'Path Setup (Plan Review)' section," but line 117 is actually inside Entry's "### Entry: resuming after a max-rounds block" subsection — a separate occurrence from item 9's real line-289 site in the actually-named section. Could mislead a plan writer into treating items 5 and 9 as duplicates and skipping one.
**Fix:** Relabel item 5's location, or rely solely on the discussion's own re-grep instruction (already present) to avoid missing this site.

### [NIT:consistency] Root-cause rationale understates worktree_root's direct usage
**Section:** Decisions › "Root cause," rationale.
**Issue:** States `resolve_repo_config_path` "uses `worktree_root` only to seed `resolve_main_worktree_root`," but `_config.py:213` also uses `worktree_root` directly for a third candidate path (`worktree_root / "mill-config.yaml"`). Doesn't change the conclusion (still git-checkout-root semantics) but the "only" claim is factually inaccurate.
**Fix:** Amend rationale to note both uses (seeding candidate 2, and direct candidate 3).

## Verdict

REQUEST_CHANGES
The mill-go-base "established convention" cited to justify the full 13-site rename doesn't hold for the Path-Setup call sites.
MILL_REVIEW_END
