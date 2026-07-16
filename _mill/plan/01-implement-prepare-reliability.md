# Batch: implement-prepare-reliability

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: implement-prepare-reliability
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-millpy-implement.py
depends-on: []
```

## Batch Scope

This batch fixes three independent reliability bugs in `millpy-implement.py`'s `--stage prepare` path plus `_agent_dispatch.py`'s dispatch-mode default, closing issues #625, #626, #635, #643, and #636. All three fixes live in the "Stages: prepare and full" block of `millpy-implement.py`'s `main()` (roughly lines 419–586) and in `_agent_dispatch.resolve_dispatch_mode`. The external interface the next batch (`effort-tier-envelope`) consumes: `millpy-implement.py`'s `--stage prepare` `emit_prepare(...)` call site now carries `start_sha=start_sha`, and Batch 2's Card 5 adds `effort=impl_effort` to that same call — Batch 2 depends on this batch precisely because it edits the same call.

## Cards

### Card 1: fix `resolve_dispatch_mode`'s wrong default

- **Context:**
  - `mill-config.yaml`
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_agent_dispatch.resolve_dispatch_mode` (`plugins/mill/scripts/_agent_dispatch.py:80`), change `mode = claude_cfg.get("dispatch", "subprocess")` to `mode = claude_cfg.get("dispatch", "agent")`. Update the function's docstring line "Defaults to `subprocess`" (near the top of the module docstring, `_agent_dispatch.py:8`) to say "Defaults to `agent`". In `plugins/mill/unit_tests/test-agent-dispatch.py`, rename `test_resolve_dispatch_mode_defaults_to_subprocess` (line 24) to `test_resolve_dispatch_mode_defaults_to_agent`, update its docstring and body to assert `mode == "agent"` instead of `"subprocess"` (it currently asserts and enforces the wrong, pre-fix behavior), update its `print("PASS ...")` message to match, and update the corresponding entry in the module's test-runner list (the `test_resolve_dispatch_mode_defaults_to_subprocess` reference near line 257) to the renamed name. Leave `test_resolve_dispatch_mode_returns_configured_value` and `test_resolve_dispatch_mode_raises_on_unknown` unchanged — both already exercise the non-default path and are unaffected by the fallback change.
- **Commit:** `fix(agent-dispatch): default resolve_dispatch_mode to agent, matching shipped configs (#636)`

### Card 2: `start_sha` in the envelope + session_id-reuse guard on re-`--stage prepare`

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Two related changes to `millpy-implement.py`'s `main()`, in the "Stages: prepare and full (need pre-commit, render, and setup)" block starting at line 419:
  1. Restructure the `if args.resume_incomplete: ... else: ...` branch (lines 426–530) into a three-way branch. Before the existing `else` block's fresh-mint logic runs, add a new condition that fires only when `args.stage == "prepare"` (not `"full"`): call `_status.read_batches(status_path)`, find the entry matching `args.batch_name`, and if that entry's `state == "running"` and `implementer_session` is non-null (truthy), reuse it — set `session_id = <entry>["implementer_session"]` and `start_sha = <entry>["start_sha"]` from that entry, and skip `_cleanliness.capture_snapshot`, `_status.set_batch_fields`, the `git add`/`git diff --cached --quiet`/commit sequence, and the push (i.e. this reuse branch does none of the state-mutating work the existing `else` block does — it only reads). When `args.stage == "full"`, or when `args.stage == "prepare"` but no matching `running` batch entry with a session exists yet (genuine first dispatch), fall through to the existing `else` block's fresh-mint behavior (`git rev-parse HEAD`, `capture_snapshot`, fresh `uuid.uuid4()`, `set_batch_fields`, commit, push) completely unchanged — this is the critical constraint: `--stage full`'s fresh-mint behavior (the subprocess/psmux transient-retry contract documented in `mill-go/SKILL.md` step 2) must not change at all.
  2. In the `if args.stage == "prepare":` branch (currently lines 575–586), change the `emit_prepare(...)` call to pass `start_sha=start_sha` as an additional keyword argument — `emit_prepare` already accepts and handles this kwarg (`_implementer_common.py:750-793`, omits the `start_sha` envelope key when `None`, includes it when set). Both the fresh-mint path and the new reuse path from step 1 leave `start_sha` bound to a real SHA by the time this call runs, so no extra `None`-guarding is needed here beyond what `emit_prepare` already does.
- **Commit:** `fix(millpy-implement): emit start_sha in prepare envelope and reuse session_id on prepare re-run (#625, #635, #643)`

### Card 3: non-fatal prepare-stage push

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the fresh-mint `else` block's push call (`millpy-implement.py`, the `["git", "push", "origin", branch]` `_subprocess_util.run` call currently at lines 524–530), change the failure handling: instead of `print(result.stderr, file=sys.stderr); return 1` on `result.returncode != 0`, print a warning to stderr (e.g. `f"[millpy-implement] warning: git push failed ({result.stderr.strip()}); continuing -- mill-merge pushes the full branch at task end"`) and fall through to the template render / `emit_prepare` call below, exactly as if the push had succeeded. Do not change the commit step above it (the local `git commit` must still succeed and return 1 on failure — only the push is made non-fatal) or any other step in the fresh-mint branch. In `plugins/mill/unit_tests/test-millpy-implement.py`, extend `TestMillpyImplement` (the `main()`-level test class, following its existing patched-subprocess fixture pattern) with three new cases covering this batch's Cards 2 and 3 together: (a) a `--stage prepare` call on a fresh batch produces an envelope whose `start_sha` matches the patched `git rev-parse HEAD` output; (b) a second `--stage prepare` call against a batch whose `_status` entry already has `state: "running"` and a non-null `implementer_session` reuses that session_id and start_sha in the envelope, and the patched `capture_snapshot`/commit/push mocks record zero additional calls; (c) a patched `git push` subprocess returning a non-zero code still reaches the envelope print with a warning line on stderr, while a patched `git commit` failure still returns 1 without reaching `emit_prepare`.
- **Commit:** `fix(millpy-implement): make prepare-stage git push non-fatal (#626)`

## Batch Tests

`verify:` runs `test-agent-dispatch.py` (Card 1's renamed default-mode test, plus the unchanged `resolve_dispatch_mode`/`model_to_tier`/`write_brief` cases in the same file) and `test-millpy-implement.py` (covers `main()`'s prepare/full stage dispatch end-to-end via `importlib`-loaded module + patched I/O, per that file's existing fixture pattern — extend it with cases for: (a) a `--stage prepare` envelope contains `start_sha` matching the captured HEAD on a fresh dispatch; (b) a second `--stage prepare` call against a batch already `state: running` with an `implementer_session` set reuses that session_id and start_sha rather than minting fresh ones, and does not re-invoke `capture_snapshot`/commit/push; (c) a simulated non-zero `git push` return still reaches the `emit_prepare`/envelope print with a warning on stderr rather than returning 1, while an unchanged `git commit` failure still returns 1).
