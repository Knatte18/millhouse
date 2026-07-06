{"status":"success","commit_sha":"15b4bc3fbfe663bbffa73487b84bffeff1083035","session_id":"0a54428c-d8f2-4d8f-8d22-c52edcdc181d"}

Summary of work done in this batch (verify-cwd-foundation, batch 3):

- `plugins/mill/scripts/_plan_dag.py` — added `parse_verify_field(frontmatter, hub_root, git_root) -> tuple[str | None, Path | None]`, the single normalizer for the `verify:` string-vs-mapping form (fail-loud on unrecognized `cwd` or missing `command`). Updated `iter_batch_verifies(plan_dir, hub_root, git_root)` to route through it and yield `(name, command, cwd)` 3-tuples instead of 2-tuples.
- `plugins/mill/unit_tests/test-plan-dag.py` — updated the `iter_batch_verifies` fixture/assertion to the new signature (flat-layout fixture, 3-tuple with `None` cwd) and added `test_parse_verify_field` covering the plain-string form, both mapping-form `cwd` values, and all three `ValueError` cases.

Commits (pushed to `hanf/nested-layout-fixes`):
- `f92da0e2` feat(plan-dag): thread parse_verify_field through iter_batch_verifies (#604)
- `15b4bc3f` test(plan-dag): cover parse_verify_field and the 3-tuple iter_batch_verifies (#604)

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-dag.py` passes (13/13 checks).

Note (informational, not acted on — out of scope for this batch): `plugins/mill/scripts/millpy-fix.py` (lines 242, 357) still calls `iter_batch_verifies(plan_base)` with the old 1-arg signature. This is expected breakage that batch 5 (fixer-verify-cwd, depends-on [3,4]) is responsible for fixing per the plan's dependency graph — not part of this batch's declared file scope.

{"status":"success","commit_sha":"15b4bc3fbfe663bbffa73487b84bffeff1083035","session_id":"0a54428c-d8f2-4d8f-8d22-c52edcdc181d"}
