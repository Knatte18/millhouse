Working tree is clean. Last commit SHA is `aa2fffb2d34a55d1d2801988733cc168691d6a75`.

{"status":"success","commit_sha":"aa2fffb2d34a55d1d2801988733cc168691d6a75","session_id":"22b880e5-2ada-470b-a450-47d09eab9e0b"}

The three cards have been implemented and committed:

**Card 1** — `plugins/mill/scripts/_implementer_common.py`: Added `verify_cmd=None` keyword-only parameter to `_batch_completeness_stuck`; inserted early-return when `verify_cmd is not None`; added `"commits_made": count` to the stuck dict.

**Card 2** — `plugins/mill/scripts/_implementer_common.py`: Added `_is_only_start_batch_commit` helper (detects the prepare-housekeeping-commit-only case). Extended the parsed-success empty-commit guard to also check `_is_only_start_batch_commit` after the `HEAD == start_sha` check. Added the same guard before all three inference-path success emits (formatter-drift, snapshot-present clean-tree, no-snapshot). Passed `verify_cmd=verify_cmd` to all four `_batch_completeness_stuck` call sites.

**Card 3** — `plugins/mill/unit_tests/test-implementer-common.py`: Added import of `_batch_completeness_stuck`. Appended cases 36–43 covering all three bug surfaces (Bug #557 empty-commit guard on parsed and inferred paths, Bug #548 gate-disable, Bug #545/#560 `commits_made` field).

{"status":"success","commit_sha":"aa2fffb2d34a55d1d2801988733cc168691d6a75","session_id":"22b880e5-2ada-470b-a450-47d09eab9e0b"}