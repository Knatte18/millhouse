{"status":"success","commit_sha":"b3760a168d5599290157a9ec32510ee8673d5205","session_id":"3fc03f64-7801-452e-9277-42e7a94dd383"}

Summary of work done for batch `plan-validate-verify-cwd` (batch 6):

- `plugins/mill/scripts/_plan_validate.py` — Card 23: `_check_verify_not_isolated` and `_check_verify_full_suite` now route through `_plan_dag.parse_verify_field`, accepting the `{cwd, command}` mapping form and also checking the overview's own module-wide `verify:` frontmatter (previously silently ignored). Card 24: added `_check_verify_malformed_cwd` (sole reporter for a `ValueError` from `parse_verify_field`) and `_check_verify_mixed_cwd` (flags a plan where batches resolve the mapping form to more than one distinct cwd, mirroring `iter_batch_verifies`'s DAG traversal). While testing, discovered and fixed a latent gap: `_plan_dag.topo_order` raises `KeyError` (not `PlanDAGError`) on a dangling `depends-on` string reference; `_check_verify_mixed_cwd` now catches both so a plan with an unrelated dangling-dep bug (already reported by `depends-on-unknown`) doesn't crash the whole validator.
- `plugins/mill/unit_tests/test-plan-validate.py` — Card 25: extended the `_make_overview` fixture helper with an `overview_verify` parameter, and added 9 new test functions covering the mapping form (clean/dirty), overview-level verify checks, malformed-mapping (missing `command`, bad `cwd` value), and mixed-cwd (conflicting + single-cwd clean).

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py` passes (86 tests, exit 0). `ruff check` clean on both changed files.

Three commits, one per card, all pushed to `hanf/nested-layout-fixes`:
- `7420c708` feat(plan-validate): accept the verify cwd mapping form and check overview-level verify (#604)
- `c596f6b7` feat(plan-validate): add verify-malformed-cwd and verify-mixed-cwd checks (#604)
- `b3760a16` test(plan-validate): cover the verify cwd mapping form and new checks (#604)

Note: Card 23's commit ended up also containing Card 24's two new check functions (I wrote all four functions in one edit pass before splitting the commits), so the `7420c708` diff is larger than a strict Card-23-only diff would be; the code is correctly attributed to the right commits functionally (Card 24's dedicated fixes — the `KeyError` guard and its own commit — landed in `c596f6b7`), but the file-level split isn't perfectly clean between commits 1 and 2.

{"status":"success","commit_sha":"b3760a168d5599290157a9ec32510ee8673d5205","session_id":"3fc03f64-7801-452e-9277-42e7a94dd383"}
