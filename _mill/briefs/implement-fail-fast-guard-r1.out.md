Both cards for this batch are committed and verified. Card-count self-check: 2 of 2 cards committed (Card 1: `86b577e8 fix(millpy-implement): fail fast on full-stage under agent-mode dispatch`; Card 2: `027db4f8 test(millpy-implement): cover agent-mode full-stage fail-fast guard`), matching the batch file's two `### Card N:` headings exactly. Verify command (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py`) passed with 65/65 tests OK. Working tree is clean of tracked in-scope modifications.

{"status":"success","commit_sha":"027db4f8","session_id":"18ae4c05-7df8-4e85-b257-7d6ae4757065","cards_done":[1,2]}

Summary of work:
- `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/scripts/millpy-implement.py`: added the fail-fast guard in `main()` immediately after `cfg` loads, before any git config check, slug resolution, or wiki daemon I/O. Guard fires when `args.stage == "full"` (covers both bare invocation and explicit `--stage full`, since `full` is argparse's default) and `_agent_dispatch.resolve_dispatch_mode(cfg) == "agent"`.
- `/home/knatte/Code/millhouse/wts/mill-go-dispatch-path-gaps/plugins/mill/unit_tests/test-millpy-implement.py`: fixed the shared `setUp`'s `mock_load_config` default (and three per-test overrides in `test_10_model_default_fallback`, `test_11_brief_size_guard_fires`, `test_12_brief_size_guard_disabled` that reconstruct the `llm` dict without a dispatch key — these would otherwise fall back to `resolve_dispatch_mode`'s `"agent"` default and break under Card 1's new guard) to pin `llm.claude.dispatch` to `"subprocess"`. Added four new tests covering the guard firing on bare/`--stage full` under agent-mode, not firing under `--stage prepare`, and not firing under the subprocess-mode default.

Both commits are pushed to `hanf/mill-go-dispatch-path-gaps`.

{"status":"success","commit_sha":"027db4f8","session_id":"18ae4c05-7df8-4e85-b257-7d6ae4757065","cards_done":[1,2]}
