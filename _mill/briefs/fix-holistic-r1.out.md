HEAD differs from baseline, no uncommitted tracked changes, and both content commits are distinct from the housekeeping baseline. All verify commands passed.

Summary of work:
- Finding 1 (NIT:consistency): merged `_CROSS_BATCH_BUILD_BREAK_FILE_EXTENSIONS` into the pre-existing `_PATH_CANDIDATE_EXTENSIONS` in `/home/knatte/Code/millhouse/wts/mill-plan-process-gaps-r2/plugins/mill/scripts/_plan_validate.py`, removing the duplicated tuple/predicate. Commit `8741ea85`.
- Finding 2 (NIT:scope): added a `depends_on` frontmatter option to `_write_batch_file` and used it in `test_does_not_fire_with_depends_on_edge` in `/home/knatte/Code/millhouse/wts/mill-plan-process-gaps-r2/plugins/mill/unit_tests/test-plan-validate-cross-batch-build-break.py`, matching card 14's dual-frontmatter fixture requirement. Commit `f27c3178`.

All four batch `verify:` commands ran clean (batch 1 was `null`).

{"status":"success","commit_sha":"f27c31781c3964f663ce53210b407178e117dd23","session_id":"e5bf54e9-469c-4bcf-a5f2-cb4f991d1f98"}

{"status":"success","commit_sha":"f27c31781c3964f663ce53210b407178e117dd23","session_id":"e5bf54e9-469c-4bcf-a5f2-cb4f991d1f98"}
