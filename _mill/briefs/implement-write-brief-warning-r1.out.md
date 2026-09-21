1 of 1 card committed — all complete. The commit subject matches Card 12's declared `Commit:` message exactly.

{"status":"success","commit_sha":"6a12aa1c16cea14620cb9fbc006ce8071aacff12","session_id":"751c9d4a-ceab-4860-af97-5a4dbb07ddd2","cards_done":[12]}

Summary: 1 of 1 card committed (Card 12). Edited `/home/knatte/Code/millhouse/wts/mill-plan-process-gaps-r2/plugins/mill/scripts/_agent_dispatch.py` (added `import sys`, stderr warning before the stale `.out.md` unlink in `write_brief`, updated module docstring) and `/home/knatte/Code/millhouse/wts/mill-plan-process-gaps-r2/plugins/mill/unit_tests/test-agent-dispatch.py` (added `contextlib`/`io` imports and `test_write_brief_warns_on_stale_out_md_overwrite`, registered in `main()`'s `tests` list). Verify command (`test-agent-dispatch.py` run directly) passed all 21 tests. Pushed to `hanf/mill-plan-process-gaps-r2`. Pre-existing, unrelated ruff findings (`RUF022`, `RUF100`) were confirmed present on `main` before this change and left untouched per the plan's "done_gate stays null" Shared Decision.

{"status":"success","commit_sha":"6a12aa1c16cea14620cb9fbc006ce8071aacff12","session_id":"751c9d4a-ceab-4860-af97-5a4dbb07ddd2","cards_done":[12]}
