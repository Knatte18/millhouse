Both cards (9 and 10) of this 2-card batch are committed and verify passes. Card-count self-check: 2 of 2 cards committed — this is an honest, fully complete batch, not a partial claim.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-pipeline-dispatch-entrygate-gaps/plugins/mill/scripts/_status.py` — added `_INFERRED_SUCCESS_LOG_HEADING`, `_find_inferred_success_log_block`, and `append_inferred_success_log`, modeled directly on `append_recovery_log`.
- `/home/knatte/Code/millhouse/wts/mill-pipeline-dispatch-entrygate-gaps/plugins/mill/unit_tests/test-status.py` — added `append_inferred_success_log` import and a new test block mirroring the `append_recovery_log` test block's five-case coverage.

Commits:
- `67629117` feat(status): add append_inferred_success_log helper for #781 observability
- `1a9fb81a` test(status): cover append_inferred_success_log lazy-section and append-only behavior

{"status":"success","commit_sha":"1a9fb81aa4084e12c6467c10647673025ed1af4f","session_id":"ffaf80a9-9b6e-4f39-869d-3ea10d02ceb4","cards_done":[9,10]}
