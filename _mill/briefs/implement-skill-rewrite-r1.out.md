Card 8 is committed: 1 of 1 cards. The rewritten `plugins/mill/skills/mill-merge/SKILL.md` is now a dispatcher around `millpy-merge.py`, with the frontmatter unchanged.

Verify (`test-guards.py`) first failed on a literal U+2192 arrow in `plugins/mill/unit_tests/test-merge.py`, left over from an earlier batch. I replaced the literals in the `_ascii` assertion with `\u` escapes (second commit). `test-merge.py` is in the plan's files touched but not in this batch's Edits.

After that, `test-guards.py` reports no FAIL lines and `test-merge.py` passes all 70 tests.

{"status":"success","commit_sha":"f2f5ee9fcd68f6f6247c9b21333b6d0bc7061fe0","session_id":"d11069dd-b580-468c-b8d4-7cbfec841311","cards_done":[8]}
