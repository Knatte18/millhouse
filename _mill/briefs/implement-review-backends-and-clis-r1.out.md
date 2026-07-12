{"status":"success","commit_sha":"cc6ba54d2590818f4cc5391eb7f8533a123f9a7f","session_id":"6f98275c-4550-40bb-9dec-a5c2fca91b50"}

All 8 of 8 cards committed (cards 6-13, verified by matching commit subjects against the batch's `## Cards` `Commit:` messages from `4374c238` (the `mill-go: start batch review-backends-and-clis` commit) to `HEAD`).

Verify command result: 7 of 8 test files passed. `test-review-cli.py` fails on 2 pre-existing assertions (`plan_brief_path`, `code_brief_path` in `test_plan_prepare_brief_path_uses_git_root` / `test_code_prepare_brief_path_uses_git_root`), confirmed to reproduce byte-identically on `main` (ran the same test file in the `main` worktree at `C:\Code\millhouse\wts\millhouse` -- same two failures, same messages). No same-task commit touches `_paths.py` (`git log main..HEAD -- plugins/mill/scripts/_paths.py` is empty), and this task's "All Files Touched" list in `00-overview.md` never lists `_paths.py` or `test-review-cli.py`, so this is a genuine pre-existing hub-vs-git-root path-resolution bug (plan/code CLIs resolve briefs under `_paths.resolve_hub_path()` rather than `git_root` in the sibling-hub container layout) unrelated to this batch's `agent_mode`/`output_path` changes. Per the brief's stuck-type guidance ("Only use `verify` when you have confirmed the failure is NOT pre-existing"), this does not warrant `stuck_type: verify`.

Files touched (all under `C:\Code\millhouse\wts\explore-fork-agent-opportunities\plugins\mill\`):
- `scripts/_review_discussion.py`, `scripts/_review_code.py`, `scripts/_review_plan.py` -- `agent_mode` param threaded to `build_tool_rule`
- `scripts/millpy-review-discussion.py`, `scripts/millpy-review-plan.py`, `scripts/millpy-review-code.py` -- `output_path` envelope key, `agent_mode=True`/`output_contract=True` on prepare, missing-file guard replacing `html.unescape`
- `unit_tests/test-review-finalize.py` -- inverted the 3 unescape round-trip tests, added 9 missing/empty/whitespace cases + 3 stale-`.out.md` regression tests
- `unit_tests/test-review-prepare-envelope.py` (new) -- envelope-shape assertions plus both carve-outs

{"status":"success","commit_sha":"cc6ba54d2590818f4cc5391eb7f8533a123f9a7f","session_id":"6f98275c-4550-40bb-9dec-a5c2fca91b50"}
