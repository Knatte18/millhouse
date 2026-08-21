MILL_REVIEW_BEGIN
# Review: mill-merge/merge-in: nested-layout config resolution, stale locks, and rollback-target bugs — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; harness reports "Sonnet 5")
reviewed_file: plan/
date: 2026-08-21
```

## Findings

No findings. Verified every "Find this exact text" block in all four batches (Cards 1-10) byte-for-byte against the live source files (`mill-merge/SKILL.md`, `mill-merge-in/SKILL.md`, `_parent_branch.py`, `_config.py`, `_review_common.py`, `millpy-review-plan.py`) — all match exactly. Confirmed:

- Batch 1 (Cards 1-2): sub-step 1a's rebase-retry insertion and Step 8's early-release relocation are internally consistent — Card 2's "Post-Step-5-success sequencing" paragraph correctly accounts for Card 1's new retry-success path, the pre-existing branch-protection fallback's own "skip to Step 8" direction is unaffected, and the Rollback section's `reset --hard origin/<parent_branch>` target is still correct after a sub-step-1a rebase-abort.
- Batch 2 (Cards 3-4): `_run_verify_gate`'s docstring/behavior (`git_root` wins over `project_root` when not None; mill-go's live batch dispatch always threads `git_root`) matches Card 3's cwd-default claim exactly. `resolve.py`'s inline walk is confirmed upward-only (cwd → git toplevel), supporting Card 4's cd-to-`hub_root` fix; the unchanged "documented convention... for symmetry" sentence correctly refers only to git-commit's skip-silently-when-absent behavior, not to cwd handling, so it isn't contradicted by Card 4's edit.
- Batch 3 (Cards 5-6): `check_liveness`'s before-text and both call sites match; the three new mocked-assertion scenarios (remote-alive/remote-dead-local-alive/both-dead) correctly exercise the short-circuit and fallback branches, and mirror `test-pr-state.py`'s `_make_run_mock` pattern (justified narrowing to `returncode`-only).
- Batch 4 (Cards 7-10): `_config.load_config`'s stub-handling block and `_review_common.load_config`'s `worktree_root = mill_dir.parent` / two downstream uses match exactly; the gate's two-condition (`worktree_root != hub_root` AND `hub_relative_path in stub_data`) correctly distinguishes all four test scenarios (Tests 1-4) from the implementation. `millpy-review-plan.py`'s call site is confirmed the sole `_review_common.load_config` call in that file.
- Structural checks: Batch Index DAG has no cycles/forward-refs (all `depends-on: []`, independent files per Shared Decision); global card numbering 1-10 is sequential with no gaps; `## All Files Touched` (8 files) is the exact union of every card's `Edits:`; every card supplies `Context`/`Edits`/`Moves: none`/`Requirements`/`Commit`; `verify:` commands use the mandated `PYTHONPATH= ` prefix; no Moves anywhere so no Rename mechanic is required.

## Verdict

APPROVE
All four batches are internally consistent, decision-aligned, and every "find this exact text" block verified byte-exact against source.
MILL_REVIEW_END
