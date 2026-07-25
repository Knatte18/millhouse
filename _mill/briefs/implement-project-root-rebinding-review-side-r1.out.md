All 4 of 4 cards in this batch are committed, verify passes, and the working tree is clean.

Summary of work:
- Card 13 (`d52de27f`): rebound `project_root` in `plugins/mill/scripts/millpy-review-code.py` to `_paths.resolve_active_hub(...)` after slug resolution.
- Card 14 (`b61c699f`): same rebind in `plugins/mill/scripts/millpy-review-plan.py`, applied before the `prepare`/`finalize`/`full` stage dispatch.
- Card 15 (`4c2e68f8`): same rebind (as `hub_dir`) in `plugins/mill/scripts/millpy-review-discussion.py`.
- Card 16 (`bdbcc0a0`): added new regression tests to `plugins/mill/unit_tests/test-review-code-flow.py`, `test-review-plan-flow.py`, and extended `test-review-discussion-flow.py`, each proving `briefs_dir`/`brief_path` resolves under `resolve_active_hub`'s value and not `resolve_hub_path`'s decoy (verified these fail against the pre-rebind code and pass after). Also fixed fixture gaps the rebind exposed in `test-review-plan-finalize-round.py`, `test-review-cli.py`, and `test-review-cli-error-envelope.py` (all of which patch `_paths.resolve_git_root`/`resolve_hub_path` directly but never mocked the new `resolve_container_path`/`resolve_active_hub` calls — two of `test-review-cli.py`'s tests were actually pre-existing failing pins of the not-yet-fixed #675 regression, now passing).

Three scope-extension plan commits (`9af2d572`, `41007cfa`, `3e94a719`) were made against `_mill/plan/05-project-root-rebinding-review-side.md` before each corresponding fixture fix, per protocol.

Verified: the full `run-all.py` unit-test suite went from 6 pre-existing failing files to 4 (`test-agent-mode-dispatch.py`, `test-language-skills-directive.py`, `test-millpy-spawn.py`, `test-millpy-claim.py`) — confirmed via checkout of the batch-start commit (`6bf565ba`) that these 4 fail identically before this batch's changes, so they are pre-existing and out of scope.

Files touched (all under `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps`):
- `plugins/mill/scripts/millpy-review-code.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/scripts/millpy-review-discussion.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-plan-finalize-round.py`
- `plugins/mill/unit_tests/test-review-cli.py`
- `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- `_mill/plan/05-project-root-rebinding-review-side.md`

{"status":"success","commit_sha":"bdbcc0a028c25c81773d06bbc9a0ac658a327386","session_id":"30f0b09f-ad0e-4b9e-91da-1597a9fedb6f","cards_done":[13,14,15,16]}
