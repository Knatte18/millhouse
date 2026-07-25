# Batch: fail-fast-guard

```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: fail-fast-guard
number: 1
cards: 2
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py"
depends-on: []
```

## Batch Scope

Closes #672. `millpy-implement.py`'s `--stage` argument defaults to `"full"` (`main()`, `argparse.add_argument("--stage", ..., default="full")`). A `full`-stage run executes the implementer synchronously in-process, with a timeout of up to `cfg["llm"]["implementer_timeout"]` (default 1800s). Nothing in `main()` today checks the configured dispatch mode before taking this path, so a bare invocation (no `--stage` flag) — or an explicit `--stage full` — under `dispatch: agent` config blocks the caller for up to 30 minutes instead of failing in milliseconds. This batch adds a guard immediately after config load, before any other setup work (git config checks, slug resolution, batch lookup), so a misrouted call fails before touching git or the wiki daemon at all. This batch is self-contained: it touches only `millpy-implement.py` and its own test file, and the next batch that also edits this file (`project-root-rebinding`) depends on this one completing first to avoid two batches editing the same file's `main()` in an undefined order.

## Cards

### Card 1: Add agent-mode/full-stage fail-fast guard to millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `main()`, immediately after the `cfg = _review_common.load_config(git_root, mill_dir)` try/except block (the block ending with `return 1` on `_review_common.ReviewError`, currently just above the `git config --global --get user.name` checks) and before any further setup, add:

  ```python
  if args.stage == "full" and _agent_dispatch.resolve_dispatch_mode(cfg) == "agent":
      print(
          "millpy-implement.py: --stage full is incompatible with dispatch: agent"
          " config. Use --stage prepare followed by --stage finalize instead"
          " (see mill-go/SKILL.md \"## Agent-mode dispatch\").",
          file=sys.stderr,
      )
      return 1
  ```

  Since `--stage` defaults to `"full"` via `argparse`, this single check covers both a bare invocation (no `--stage` flag) and an explicit `--stage full` invocation — do not special-case the two. `_agent_dispatch` is already imported at module scope; no new import is needed. Place the guard before the `git config --global --get user.name`/`user.email` checks and before `_marker.slug_from_branch` is called, so a misconfigured call fails before any git or wiki-daemon I/O.
- **Commit:** `fix(millpy-implement): fail fast on full-stage under agent-mode dispatch`

### Card 2: Add tests for the fail-fast guard

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `TestMillpyImplement`, add test methods (following the existing `setUp`/`_run_main` pattern already in the file — `self.mock_load_config` is a `unittest.mock.patch.object` on `millpy_implement._review_common.load_config`):
  1. `test_agent_mode_full_stage_guard_bare_invocation` — override `self.mock_load_config.return_value` to include `"llm": {"claude": {"dispatch": "agent"}, "implementer_timeout": 1800}` (merge with the existing `self.mock_load_config.return_value`'s other keys — don't drop `paths`/`roles`), call `self._run_main(["test-batch"])` (no `--stage` flag), and assert `rc == 1` and that `millpy_implement._implementer_claude.run` was never called (patch it and assert `assert_not_called()`).
  2. `test_agent_mode_full_stage_guard_explicit_full` — same cfg override, call `self._run_main(["test-batch", "--stage", "full"])`, assert the same `rc == 1` / not-called outcome.
  3. `test_agent_mode_prepare_stage_not_guarded` — same agent-mode cfg override, call `self._run_main(["test-batch", "--stage", "prepare"])`, assert the guard does NOT fire (the call proceeds past the guard — assert `rc` is not the guard's `1` by asserting stdout contains a `"stage": "prepare"` JSON envelope, or by asserting a distinct mocked marker further down the prepare path was reached).
  4. `test_subprocess_mode_full_stage_not_guarded` — leave `self.mock_load_config.return_value` at its existing default (no `llm.claude.dispatch` key, so `resolve_dispatch_mode` returns its own default — confirm via Card 1's guard logic which default value that is before asserting; do NOT assume `"subprocess"` if `_agent_dispatch.resolve_dispatch_mode`'s documented default is `"agent"` — read `plugins/mill/scripts/_agent_dispatch.py` to confirm, and explicitly set `"llm": {"claude": {"dispatch": "subprocess"}, "implementer_timeout": 1800}` in this test's cfg override to be unambiguous), call `self._run_main(["test-batch"])` with `_implementer_claude.run` mocked to return a success JSON tuple (matching `test_1_initial_dispatch_success`'s pattern), and assert `rc == 0` (the guard does not fire under non-agent dispatch).
- **Commit:** `test(millpy-implement): cover agent-mode full-stage fail-fast guard`

## Batch Tests

`verify:` runs `test-millpy-implement.py`, which Card 2 extends directly — this is the only test file covering `millpy-implement.py`'s CLI entry point, so no `--only` list beyond this single file is needed.
