Summary of work:

**Finding addressed:** BLOCKING:scope — `mill-merge/SKILL.md` Step 4 carried a #930 citation-scan duplicate that no card in the plan authorized (added in an earlier round without a corresponding plan update).

**Resolution (FIX, via plan-authorization path per Fix discipline item 6):** Rather than reverting the already-correct code (which the reviewer itself noted "may be correct"), added Card 8 to batch 1 (`_mill/plan/01-mill-merge-in-parent-and-baseline.md`) retroactively authorizing and documenting the `mill-merge/SKILL.md` Step 4 citation-scan extension, and updated `_mill/plan/00-overview.md`'s Shared Decision to note the round-3 addendum. `mill-merge/SKILL.md` already belonged to batch 1's file family (Card 1 edits it), so no new DAG edge or cross-batch dependency was introduced. No source-code edit was needed since the existing implementation already matched what Card 8 now documents.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-merge-finalize-codeguide-bugs/_mill/plan/01-mill-merge-in-parent-and-baseline.md`
- `/home/knatte/Code/millhouse/wts/mill-merge-finalize-codeguide-bugs/_mill/plan/00-overview.md`

Commit: `ff76b1fddaabd12630ecbcd1fb51632918e3d309` — "plan: extend batch mill-merge-in-parent-and-baseline for #930 mill-merge citation-scan authorization" (pushed).

Verify: `PYTHONPATH= "$MILL_PYTHON" plugins/codeguide/unit_tests/test-resolve-scope.py` — all 19 scenarios passed. Batches 1 and 2 have `verify: null`.

Baseline HEAD was `fc4313ca80f1bb903ab2bcdaa1c9bc3ff7d21a8f`; final HEAD `ff76b1fddaabd12630ecbcd1fb51632918e3d309` differs, confirming a new commit was made. `git status --porcelain --untracked-files=no` is clean.

{"status":"success","commit_sha":"ff76b1fddaabd12630ecbcd1fb51632918e3d309","session_id":"ef87bf6d-913d-453e-971f-a5663ed4b59e"}