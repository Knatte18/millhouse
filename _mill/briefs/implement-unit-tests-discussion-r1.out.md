All three cards in batch `unit-tests-discussion` are now committed and the batch's verify command passes.

{"status":"success","commit_sha":"418839ae","session_id":"0a39005a-9c34-4bc5-916b-d087e1541bef","cards_done":[13,14,15]}

Summary (3 of 3 cards committed — all complete):

- Card 13 (`_reviewers.resolve_reviewer_override` unit tests) was already committed before this session started (commit `d714ebaa`), confirmed via `git log 5bd9259a..HEAD --oneline` matching its `Commit:` message exactly.
- Card 14 (`prepare()`-level `reviewer_override` unit tests) had uncommitted WIP in the working tree at session start. While completing it I found the plan's literal instruction (`_test_registry.write_to(wiki_root, ...)`) was a no-op for named reviewer specs — `_reviewers.load()` only falls back to `wiki_root/agents.yaml` when the plugin template is empty, which it never is in this source tree. Fixed by adding a `_write_local_overlay(mill_dir, **entries)` helper that writes to `.millhouse/agents.local.yaml` (the layer `_reviewers.load()` actually merges local overrides from), mirroring `test-reviewers.py`'s established convention. Committed as `360aabd0`.
- Card 15 (`run()`-level `reviewer_override` unit tests) surfaced a genuine bug in the already-committed `discussion-review-cli` batch: `run()` calls `prepare()` first, and `prepare()` hardcoded `reject_non_claude=True` for `reviewer_override` regardless of caller, so a non-Claude override always raised inside `prepare()` before `run()`'s own `reject_non_claude=False` resolve could ever execute — making that downstream resolve dead code, contrary to its own inline comment. Per the "file not listed" protocol, I first amended `_mill/plan/05-unit-tests-discussion.md` (moving `_review_discussion.py` from Card 15's Context to Edits) and committed that plan edit (`0fa442cb`) before touching the code. Fix: `prepare()`'s reviewer_override resolve now uses `reject_non_claude=agent_mode` — reusing the existing `agent_mode` flag that already distinguishes the Agent-mode `--stage prepare` CLI entrypoint (Claude-only) from `run()`'s internal legacy direct-dispatch call (any configured provider). Committed as `418839ae`.

Verify: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-reviewers.py test-review-discussion-flow.py` passes. Also spot-checked batch 2's `test-review-prepare-envelope.py` / `test-review-cli-error-envelope.py` (unaffected) and ran the full `run-all.py` suite; the only 2 failures (`test-millpy-spawn.py`, `test-millpy-claim.py`) are unrelated to this task — no commit on this branch touches spawn/claim code, confirming pre-existing/out-of-scope.

Files touched:
- `/home/knatte/Code/millhouse/wts/mill-review-dispatch-attribution-gaps/plugins/mill/unit_tests/test-review-discussion-flow.py`
- `/home/knatte/Code/millhouse/wts/mill-review-dispatch-attribution-gaps/plugins/mill/scripts/_review_discussion.py`
- `/home/knatte/Code/millhouse/wts/mill-review-dispatch-attribution-gaps/_mill/plan/05-unit-tests-discussion.md`

{"status":"success","commit_sha":"418839ae","session_id":"0a39005a-9c34-4bc5-916b-d087e1541bef","cards_done":[13,14,15]}
