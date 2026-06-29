# Batch: merge-in-cli-parity

```yaml
task: "Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity"
batch: "merge-in-cli-parity"
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-merge-in-subagent.py test-merge-in-subagent.py
depends-on: []
```

## Batch Scope

This batch delivers #569: `millpy-merge-in-subagent.py --stage finalize` rejects the
`--session-id` flag that its own `--stage prepare` envelope emits (via the shared `emit_prepare`
helper), breaking mill-go's generic "thread applicable prepare-envelope fields into finalize"
guidance during agent-dispatch conflict resolution. The fix brings the merge-in-subagent parser
up to the same accept-and-ignore parity that `millpy-fix.py` and `millpy-implement.py` already
have (see overview Shared Decisions). It is an isolated unit touching only
`millpy-merge-in-subagent.py` and its CLI test, with no edits overlapping batch 1, so it runs in
parallel (`depends-on: []`). `millpy-fix.py` is the read-only parity reference and is never
modified.

## Cards

### Card 8: Accept ignored --session-id/--start-sha/--round on millpy-merge-in-subagent.py (#569)

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-merge-in-subagent.py` `main()`, add three `default=None` accepted-but-ignored arguments to the parser immediately after `--agent-output`: `--session-id`, `--start-sha`, and `--round` (declare each with `default=None` and no `type=`, so any threaded value parses). Each help string states it is accepted for CLI-shape parity with `millpy-fix.py` / `millpy-implement.py` and is ignored — conflicts-mode finalize delegates to `finalize_from_output(..., session_id=None)` and verify-fix finalize re-runs `--cmd` directly. Do NOT reference `args.session_id` / `args.start_sha` / `args.round` anywhere in the finalize or mode branches. ASCII-only help text.
- **Commit:** `fix(merge-in-subagent): accept ignored --session-id/--start-sha/--round for finalize parity (#569)`

### Card 9: Test ignored finalize-parity flags on merge-in-subagent (#569)

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a conflicts-mode finalize test to `test-millpy-merge-in-subagent.py` that calls `main()` with `--mode conflicts --stage finalize --agent-output <path> --session-id <id> --start-sha <sha> --round 1` and asserts it returns 0 (no `unrecognized arguments` error) and that finalize proceeds — i.e. it delegates to `finalize_from_output`. Mirror the existing in-process `main(argv)` patching style used by the file's other finalize tests (patch git / path resolution / `finalize_from_output` as the existing tests do).
- **Commit:** `test(merge-in-subagent): cover ignored finalize-parity flags (#569)`

## Batch Tests

`verify:` runs `run-all.py --only test-millpy-merge-in-subagent.py test-merge-in-subagent.py`.
`test-millpy-merge-in-subagent.py` is the CLI `main(argv)` test file that card 9 extends and is
the direct target for the #569 parser change; `test-merge-in-subagent.py` is included as
regression coverage for the script's internal helpers (conflict/verify-fix flows) so the parser
addition does not perturb them. Bounded two-file scope keeps each post-round verify fast.
