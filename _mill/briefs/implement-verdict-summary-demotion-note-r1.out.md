All 4 cards (12, 13, 14, 15) committed, matching all 4 declared cards in the batch file. Verify passed. Working tree clean.

Summary: 4 of 4 cards committed. Card 12 added `append_demotion_note` to `plugins/mill/scripts/_review_common.py`. Card 13 wired it into `finalize_scope` unconditionally on `demoted_any`, independent of the verdict-token-flip gate. Card 14 documented the optional third `## Verdict` line in `plugins/mill/templates/review-output.schema.md`. Card 15 added three new tests to `plugins/mill/unit_tests/test-review-class-taxonomy.py`, all passing along with all pre-existing tests in that file.

{"status":"success","commit_sha":"150a66130b57aff94ef6718580921652cd799bc8","session_id":"2a133a9e-99f5-4860-b3fc-043ced07ac41","cards_done":[12,13,14,15]}