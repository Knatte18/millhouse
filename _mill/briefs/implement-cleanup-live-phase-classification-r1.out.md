1 commit matches the single card (Card 2) declared in this batch. Batch fully complete: 1 of 1 card committed.

{"status":"success","commit_sha":"2ba4fb6f","session_id":"23eaf3d5-2b73-4b5c-bf86-07c33db60206","cards_done":[2]}

## Summary

Implemented Card 2 (the batch's only card) of `02-cleanup-live-phase-classification.md`: replaced the flat `_LIVE_PHASES` set-membership check in `millpy-cleanup.py`'s `build_plan` with a new `_is_live_phase(phase)` helper that also recognizes round-suffixed and batch-embedded phase forms (`discussion-fix-rN`, `plan-review-rN`, `plan-fix-rN`, `reviewing-{batch}-rN`, `fixing-{batch}-rN`, `approved-{batch}`, `nits-fixed-{scope}`) via a module-level regex tuple, while dropping the two dead bare `"reviewing"`/`"fixing"` entries. The helper guards `isinstance(phase, str)` first so a malformed (non-str) `phase` value degrades to `False` instead of raising `TypeError`.

Files changed:
- `/home/knatte/Code/millhouse/wts/mill-go-verify-gate-misclassification/plugins/mill/scripts/millpy-cleanup.py` — added `import re`, module-level `_LIVE_PHASES`/`_LIVE_PHASE_PATTERNS`/`_is_live_phase`, and updated the `build_plan` branch to call `_is_live_phase(phase)`.
- `/home/knatte/Code/millhouse/wts/mill-go-verify-gate-misclassification/plugins/mill/unit_tests/test-cleanup.py` — imported `_is_live_phase`, added `test_is_live_phase()` (called from `main()` next to `test_scan_orphan_portals()`), and added a new `build_plan` integration sub-block asserting a round-suffixed phase (`plan-review-r2`) is treated as live end-to-end with `to_report == []`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-cleanup.py` passes in full (all existing + new assertions). Ran `uvx ruff check` on both changed files — no new violations introduced by my edits (pre-existing findings elsewhere in the files are out of scope). Committed via the `git-commit` skill (single commit `2ba4fb6f`, on branch `hanf/mill-go-verify-gate-misclassification`, pushed to remote). Working tree is clean of tracked modifications (pre-report self-check confirmed via `git status --porcelain --untracked-files=no`).

Card-count self-check: 1 commit found between batch-start `d294a4d9` and `HEAD`, matching the batch's single declared card (Card 2). All cards committed — 1 of 1.
