{"status":"success","commit_sha":"db6e7cba382a0113d60957fbaddc4daeb50581bd","session_id":"6185138d-491d-4ee4-a8ec-29f9948d261c","cards_done":[3,4,5,6]}

All 4 of 4 cards committed and verified this turn — Cards 3, 4, 5, 6, all matching their `Commit:` messages in the git log. The batch's `verify:` command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-merge-in-subagent.py`) passes with all cases green, including the new Case 78/79 and `test_2x_conflicts_finalize_emits_pre_merge_head` / `test_2x_conflicts_full_mode_emits_pre_merge_head`. Working tree is clean.

Files touched:
- `/home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability/plugins/mill/scripts/_implementer_common.py` — added `commit_sha_field_name` keyword param to `_forward_output` / `finalize_from_output`; success-fallback block now writes under that key, popping any stale `commit_sha` when non-default.
- `/home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability/plugins/mill/scripts/millpy-merge-in-subagent.py` — both conflicts-mode call sites (finalize-stage `finalize_from_output` call, full-mode `_forward_output` return) now pass `commit_sha_field_name="pre_merge_head"`.
- `/home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability/plugins/mill/unit_tests/test-implementer-common.py` — Cases 78 and 79 added.
- `/home/knatte/Code/millhouse/wts/implementer-commit-sha-and-status-line-reliability/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` — `test_2x_conflicts_finalize_emits_pre_merge_head` and `test_2x_conflicts_full_mode_emits_pre_merge_head` added.

{"status":"success","commit_sha":"db6e7cba382a0113d60957fbaddc4daeb50581bd","session_id":"6185138d-491d-4ee4-a8ec-29f9948d261c","cards_done":[3,4,5,6]}
