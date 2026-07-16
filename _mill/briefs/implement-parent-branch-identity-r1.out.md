{"status":"success","commit_sha":"edbcade30f8b495e37a1f9c2e2710b7f752bf5cb","session_id":"2fde5ada-e4d8-4b37-9468-645ed2d8e805"}

Summary: Both cards of batch 01-parent-branch-identity were completed and committed (2 of 2). Card 1 added the `expected_slug` keyword-only parameter to `_read_parent_from_status`, `resolve`, and `resolve_for_codeguide` in `plugins/mill/scripts/_parent_branch.py`, threading it through with the "mismatch treated as absent" semantics and updated docstrings. Card 2 added matching/mismatched/absent-slug-row test cases to `plugins/mill/unit_tests/test-parent-branch.py`, preserving every pre-existing assertion unmodified. The batch verify command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py`) passed all 10 assertions. Working tree is clean (no uncommitted tracked changes). Both commits were pushed to `hanf/mill-merge-stacked-branch-status-corruption`.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-merge-stacked-branch-status-corruption/plugins/mill/scripts/_parent_branch.py`
- `/home/knatte/Code/millhouse/wts/mill-merge-stacked-branch-status-corruption/plugins/mill/unit_tests/test-parent-branch.py`

{"status":"success","commit_sha":"edbcade30f8b495e37a1f9c2e2710b7f752bf5cb","session_id":"2fde5ada-e4d8-4b37-9468-645ed2d8e805"}
