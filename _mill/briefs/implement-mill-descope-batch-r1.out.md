Verify passes, no uncommitted tracked changes. Card-count self-check: 3 of 3 cards (8, 9, 10) committed — all complete.

{"status":"success","commit_sha":"a909a04dd54e07d98ea4e4d34440862635769a15","session_id":"7056e28c-bb6d-49c4-a07e-53aa87b419dd","cards_done":[8,9,10]}

Summary: All 3 cards of the mill-descope-batch batch (cards 8, 9, 10) are committed and verify passes.

- `/home/knatte/Code/millhouse/wts/mill-go-execution-and-bookkeeping-bugs/plugins/mill/scripts/_status.py` — added `remove_batch(status_path, name)`.
- `/home/knatte/Code/millhouse/wts/mill-go-execution-and-bookkeeping-bugs/plugins/mill/unit_tests/test-status.py` — tests for `remove_batch`.
- `/home/knatte/Code/millhouse/wts/mill-go-execution-and-bookkeeping-bugs/plugins/mill/scripts/_plan_dag.py` — added `find_dependents`, `remove_batch_from_index`, `_serialise_batch_index`.
- `/home/knatte/Code/millhouse/wts/mill-go-execution-and-bookkeeping-bugs/plugins/mill/unit_tests/test-plan-dag.py` — 5 new tests for the above.
- `/home/knatte/Code/millhouse/wts/mill-go-execution-and-bookkeeping-bugs/plugins/mill/scripts/millpy-descope-batch.py` — new CLI.
- `/home/knatte/Code/millhouse/wts/mill-go-execution-and-bookkeeping-bugs/plugins/mill/skills/mill-descope-batch/SKILL.md` — new skill wrapper.
- `/home/knatte/Code/millhouse/wts/mill-go-execution-and-bookkeeping-bugs/SKILLS.md` — new row, alphabetically placed.

Commits: `a8d42e57` (card 8), `1ee63271` (card 9), `a909a04d` (card 10, final HEAD). All pushed to `hanf/mill-go-execution-and-bookkeeping-bugs`. `verify:` (`run-all.py --only test-status.py test-plan-dag.py`) passes.

{"status":"success","commit_sha":"a909a04dd54e07d98ea4e4d34440862635769a15","session_id":"7056e28c-bb6d-49c4-a07e-53aa87b419dd","cards_done":[8,9,10]}
