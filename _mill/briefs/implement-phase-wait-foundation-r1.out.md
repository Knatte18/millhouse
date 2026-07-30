All 3 cards committed, matching all 3 declared `Commit:` messages in the batch file. Verify passed. Card-count self-check: 3 of 3 cards committed.

{"status":"success","commit_sha":"d3751884554f32c3ea658a2a33784c92bfbbdc60","session_id":"02467530-890f-41d8-bbb9-c13771ce71e6","cards_done":[1,2,3]}

Summary: All 3 cards in batch `01-phase-wait-foundation.md` are complete (3 of 3 committed).

- `/home/knatte/Code/millhouse/wts/phase-wait-gate/plugins/mill/scripts/_phase_wait.py` (new) — `build_wait_command` / `matches_wait_trigger` pure helper, commit `3c5bae66`
- `/home/knatte/Code/millhouse/wts/phase-wait-gate/plugins/mill/unit_tests/test-phase-wait.py` (new) — 13-case unit test including a real CRLF end-to-end bash regression case, commit `11023966`
- `/home/knatte/Code/millhouse/wts/phase-wait-gate/plugins/mill/templates/mill-config.yaml` and `/home/knatte/Code/millhouse/wts/phase-wait-gate/mill-config.yaml` — added `pipeline.entry_wait` / `pipeline.entry_wait_timeout_minutes` in sync, commit `d3751884`

Verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-phase-wait.py` passes (exit 0, all 13 assertions PASS). Working tree is clean (no uncommitted tracked changes). No file outside the batch's declared scope was touched.

{"status":"success","commit_sha":"d3751884554f32c3ea658a2a33784c92bfbbdc60","session_id":"02467530-890f-41d8-bbb9-c13771ce71e6","cards_done":[1,2,3]}
