Clean tree, 3 card commits matching all 3 cards (Cards 9, 10, 11). All 3 of 3 cards committed.

{"status":"success","commit_sha":"2a47fd145f37193f6cdad1b7e30f587f72a66b38","session_id":"6b453038-ccdc-44aa-ba50-3b2270fcfbbe","cards_done":[9,10,11]}

Summary: 3 of 3 cards committed for batch `implementer-commit-sha-validation`.

- Card 9: `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/scripts/_implementer_common.py` — added `_COMMIT_SHA_RE`/`_is_valid_commit_sha`, guarded the success-path `commit_sha` override so a failed/malformed `git rev-parse HEAD` now emits a `stuck/logic` envelope instead of passing the agent's raw self-reported `commit_sha` through. Commit `47d09958`.
- Card 10: `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/unit_tests/test-implementer-common.py` — added Cases 68–70 covering the correction path, the guarded failure path, and direct `_is_valid_commit_sha` coverage. Commit `c98d91e9`.
- Card 11: `/home/knatte/Code/millhouse/wts/mill-pipeline-silent-failure-and-report-bugs/plugins/mill/templates/{implementer-brief.md,fixer-batch-brief.md,fixer-holistic-brief.md,merge-in-verify-brief.md}` — added the "full `git rev-parse HEAD`" wording to all four brief templates. Commit `2a47fd14`.

Verify (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py`) passes, all 70 cases including the 3 new ones. Working tree is clean; no scope surprises encountered (no files touched outside the batch's declared `Edits:` lists).

{"status":"success","commit_sha":"2a47fd145f37193f6cdad1b7e30f587f72a66b38","session_id":"6b453038-ccdc-44aa-ba50-3b2270fcfbbe","cards_done":[9,10,11]}
