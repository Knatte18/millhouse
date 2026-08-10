3 of 3 cards committed (Card 6, Card 7, Card 8), matching all three `Commit:` messages in the batch file exactly. Verify command (`test-review-class-taxonomy.py` + `test-review-finalize.py`) passed with all tests green. Working tree is clean.

{"status":"success","commit_sha":"6be496d66478c187df46fb9ca0363fd2c0179332","session_id":"a42c4707-abd0-4a49-95a5-bd5704b2f285","cards_done":[6,7,8]}

Files touched:
- `plugins/mill/scripts/_review_common.py` (Cards 6 and 7: added `rewrite_verdict_token`, wired it into `finalize_scope` gated on `demoted_any and verdict != original_verdict`)
- `plugins/mill/unit_tests/test-review-class-taxonomy.py` (Card 8: `_verdict_section` fixture + 4 new tests, added to `TESTS`)

{"status":"success","commit_sha":"6be496d66478c187df46fb9ca0363fd2c0179332","session_id":"a42c4707-abd0-4a49-95a5-bd5704b2f285","cards_done":[6,7,8]}
