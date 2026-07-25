# Batch: mill-go-resume-fix

```yaml
task: "mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps"
batch: mill-go-resume-fix
number: 6
cards: 1
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-implement.py"
depends-on: []
```

## Batch Scope

Closes #680. `mill-go/SKILL.md`'s `## Resume` section, `state=running` case, subprocess/psmux branch (the block starting "If `dispatch == subprocess` or `psmux` (via `millpy-bg`)") bare-invokes `millpy-implement.py <batch_name>` with no `--stage` flag (defaults to `full`), which always takes the "Normal (first-pass) dispatch" branch and mints a fresh `start_sha`/`session_id`, discarding any partial-commit evidence from the interrupted run. Agent-mode Resume (the branch immediately above it, "If `dispatch == agent`") already re-runs the standard `--stage prepare` → Agent → `--stage finalize` flow, and `millpy-implement.py`'s existing `_prepare_reuse_entry` branch already preserves `start_sha`/`implementer_session` when `--stage prepare` targets a batch already in `running` state — agent-mode Resume needs no change. This batch is a one-flag documentation/instruction change: the subprocess/psmux Resume invocation gains `--resume-incomplete`, an already-existing, already-tested `millpy-implement.py` flag that reads the original `start_sha`/`implementer_session` from `status.md` instead of re-capturing HEAD and minting a fresh UUID. No new Python behavior is introduced — `--resume-incomplete`'s start_sha-preserving behavior is pre-existing and already covered by `test-millpy-implement.py`; only the orchestrator instructions in `SKILL.md` change which flag they tell the operator/orchestrator to pass.

## Cards

### Card 17: Use --resume-incomplete in mill-go's subprocess/psmux Resume path

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `## Resume`, `state=running`, the subprocess/psmux branch, change the `millpy-bg.py` invocation's inner command from:

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
      --slug implement-<batch_name>-resume -- \
      "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
  ```

  to:

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
      --slug implement-<batch_name>-resume -- \
      "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume-incomplete
  ```

  Update the prose immediately below it — currently "The interrupted implementer session is dead and cannot be re-attached. A fresh batch start is the correct recovery: the CLI re-initialises state -> running, captures a new snapshot, and spawns a fresh implementer session." — to instead say the interrupted session is dead and cannot be re-attached, so a fresh implementer dispatch is still the correct recovery, but `--resume-incomplete` preserves the original `start_sha`/`implementer_session` recorded by the interrupted run (reading them from `status.md` instead of re-capturing HEAD and minting a fresh UUID) so finalize's completeness recount and commit accounting reflect the batch's full history, not just the resumed dispatch's own commits — consistent with how agent-mode Resume already behaves via `_prepare_reuse_entry`. Do not change anything in the agent-mode branch immediately above, and do not change the `state=reviewing`/`state=fixing` Resume branches below this one — they are out of scope.
- **Commit:** `docs(mill-go): use --resume-incomplete in subprocess/psmux Resume for state=running`

## Batch Tests

`verify: null` would be the literal-correct choice for a pure-prose `SKILL.md` change, but this batch instead points at `test-millpy-implement.py` as a regression guard: it already covers `--resume-incomplete`'s start_sha/implementer_session-preserving behavior (the flag is pre-existing, not introduced by this batch), so re-running it confirms the flag this card now tells the orchestrator to pass still behaves as documented. No new test code is added by this batch.
