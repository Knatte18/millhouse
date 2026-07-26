All 4 of 4 cards committed and matched against the batch file's `Commit:` messages. Verify passed (3/3 target test files, all assertions green). Working tree is clean with no uncommitted tracked changes.

{"status":"success","commit_sha":"95455cd2","session_id":"47380e1f-16fd-4c4e-ad65-37f5bfd7cb53","cards_done":[5,6,7,8]}

Summary: 4 of 4 cards committed this turn.

- Card 5 (`e565f541`): added `EFFORT_TIERED_SUBAGENT_TYPES` and `resolve_subagent_type(base, effort)` to `plugins/mill/scripts/_agent_dispatch.py`, plus three new tests in `plugins/mill/unit_tests/test-agent-dispatch.py`.
- Card 6 (`68de161e`): wired `resolve_subagent_type` into `emit_prepare` in `plugins/mill/scripts/_implementer_common.py` (left `emit_prepare_no_dispatch` untouched per Shared Decision); extended Case 65 in `plugins/mill/unit_tests/test-implementer-common.py`.
- Card 7 (`e74af4e1`): wired `resolve_subagent_type` into the `--stage prepare` envelope of `plugins/mill/scripts/millpy-review-discussion.py`, `plugins/mill/scripts/millpy-review-code.py`, `plugins/mill/scripts/millpy-review-plan.py`; strengthened `_assert_effort_envelope` in `plugins/mill/unit_tests/test-review-prepare-envelope.py`.
- Card 8 (`95455cd2`): corrected the stale effort-forwarding documentation in `plugins/mill/skills/mill-go/SKILL.md` (step 2 bullet + step 3 sentence).

Batch verify command (`run-all.py --only test-agent-dispatch.py test-implementer-common.py test-review-prepare-envelope.py`) passed cleanly. `ruff check` on all touched files showed only pre-existing findings (confirmed identical on `HEAD` before my edits via `git show`), none introduced by this batch, so left untouched per scope discipline. `git status --porcelain --untracked-files=no` is clean. All commits pushed to `hanf/mill-agent-effort-gap`.

{"status":"success","commit_sha":"95455cd2","session_id":"47380e1f-16fd-4c4e-ad65-37f5bfd7cb53","cards_done":[5,6,7,8]}
