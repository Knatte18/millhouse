All 4 cards in this batch have been committed and verified. Card-count self-check: range start is `2a8073a6` (the `mill-go: start batch project-root-rebinding-implement-side` commit). Commits since then: `646e7973` (Card 9), `a285991d` (Card 10), `e2ee4e58` (Card 11), `5127c7f5` (plan-scope-extension commit, not a card), `dcacd125` (Card 12). All 4 declared cards (9, 10, 11, 12) match a commit subject exactly — **4 of 4 cards committed**, all verified.

{"status":"success","commit_sha":"dcacd125","session_id":"7860acea-6ac5-49d6-bb0c-b215fa800917","cards_done":[9,10,11,12]}

Summary of work and relevant files:

- `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/scripts/millpy-implement.py` — Card 9: rebinds `project_root`/`mill_dir` via `_paths.resolve_active_hub(..., skip_slug_validation=True)` immediately after slug resolution.
- `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/scripts/millpy-fix.py` — Card 10: same rebind pattern.
- `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/scripts/millpy-merge-in-subagent.py` — Card 11: captures the previously-discarded `slug` and rebinds `project_root` (was raw `Path.cwd()`).
- `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/unit_tests/test-millpy-implement.py`, `test-millpy-fix.py`, `test-millpy-merge-in-subagent.py` — Card 12: added `resolve_container_path`/`resolve_active_hub` mocks to `setUp`, one new regression test per file, and fixed 4 pre-existing nested-hub tests in `test-millpy-implement.py` (and 3 in `test-millpy-fix.py`) that needed `resolve_active_hub` also overridden to keep the nested-hub simulation working under the new rebind.
- `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/unit_tests/test-merge-in-subagent.py` — discovered scope, added to the plan (`_mill/plan/04-project-root-rebinding-implement-side.md`) and fixed: added `resolve_git_root`/`resolve_active_hub` mocks to its 4 fixture cases, and corrected `test_9_missing_mode`'s stale `SystemExit(2)` expectation to match actual `main()` behavior (return 1), confirmed identical on parent branch `hanf/linux-port-more`.
- `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/_mill/plan/04-project-root-rebinding-implement-side.md` — extended Card 12's `Edits:` and requirements to cover the discovered `test-merge-in-subagent.py` gap.

Batch verify command (`test-millpy-implement.py test-millpy-fix.py test-millpy-merge-in-subagent.py test-merge-in-subagent.py test-paths.py`) passes: 39 tests, all green.

{"status":"success","commit_sha":"dcacd125","session_id":"7860acea-6ac5-49d6-bb0c-b215fa800917","cards_done":[9,10,11,12]}
