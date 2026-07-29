Both card commits are present, matching the batch's 2 declared cards exactly. 2 of 2 cards committed, verify passed (53/53 tests).

{"status":"success","commit_sha":"54c3f1b8","session_id":"1b6bdf22-9d82-4417-bdde-de9fea479cd1","cards_done":[1,2]}

Summary of work:

- `/home/knatte/Code/millhouse/wts/mill-review-dispatch-attribution-gaps/plugins/mill/scripts/_reviewers.py` — added public `resolve_reviewer_override(registry, name, *, reject_non_claude)` between `resolve()` and `resolve_role()`, plus a docstring entry in the module's `Public API:` list. Commit `cba7e5a2`.
- `/home/knatte/Code/millhouse/wts/mill-review-dispatch-attribution-gaps/plugins/mill/scripts/_reviewer_single.py` — forwarded `effort=spec.get("effort")` to `_reviewer_test_stub.run()` in the `test_stub` provider branch, matching the forwarding every other provider branch already does. Commit `54c3f1b8`.

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py` passed all 53 tests. Working tree is clean (git status --porcelain --untracked-files=no returned nothing). 2 of 2 cards committed — all complete.

{"status":"success","commit_sha":"54c3f1b8","session_id":"1b6bdf22-9d82-4417-bdde-de9fea479cd1","cards_done":[1,2]}
