# Plan: Keep psmux TUI alive across calls for session continuity

```yaml
task: Keep psmux TUI alive across calls for session continuity
slug: psmux-session-keepalive
approved: true
started: 20260518-115215
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: config-schema-move
    file: 01-config-schema-move.md
    depends-on: []
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
  - number: 2
    name: wrapper-flags-and-cleanup
    file: 02-wrapper-flags-and-cleanup.md
    depends-on: [1]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-sub.py
  - number: 3
    name: llm-claude-keepalive-integration
    file: 03-llm-claude-keepalive-integration.md
    depends-on: [1, 2]
    verify: uv run --project plugins/mill python plugins/mill/unit_tests/test-llm-claude.py
  - number: 4
    name: mill-go-cleanup-integration
    file: 04-mill-go-cleanup-integration.md
    depends-on: [3]
    verify: null
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions,
error-handling posture, test frameworks, style/lint constraints. One
subsection per decision. Batch-local decisions live in each batch file._

### Decision: psmux-session-name derivation

- **Decision:** When `_llm_claude` is the caller AND `caller_provided_session_id` is true, derive `psmux_name = f"mill-{session_id[:12]}"` verbatim, no normalisation, and pass it under `--psmux-session`. When `caller_provided_session_id` is false (auto-generated session id inside `_invoke`), pass `psmux_session_name=None` so the wrapper falls back to its existing `mill-<uuid8>` auto-name. The wrapper itself accepts whatever string is passed under `--psmux-session` (or any when omitted, where it picks its own).
- **Rationale:** `session_id` is a UUID4 in every existing caller (`[0-9a-f-]`), all legal in psmux session names. Deterministic mapping aids debugging via `psmux ls` — but only on the keepalive path, because the auto-gen path always tears down on success and never appears in `psmux ls`. Refines discussion.md "session-name derivation": the discussion text said "always pass" but the operator-visibility rationale only holds when `--keep-alive` is set, and `--keep-alive` is itself gated on `caller_provided_session_id`. Conditioning both flags on the same boolean keeps the one-shot path bit-for-bit identical to today.
- **Applies to:** batches 2, 3 (wrapper accepts name; LLM layer derives name iff caller-provided session_id).

### Decision: keep-alive gating rule

- **Decision:** `--keep-alive` defaults `false` on the wrapper. `_llm_claude` passes `--keep-alive` to the wrapper **iff the caller provided a non-None `session_id`** (distinct from the auto-generated UUID branch). The wrapper itself never infers `--keep-alive` from any other flag.
- **Rationale:** `session_id` carries the operator's intent ("I plan to make more calls with this id"). The auto-generated branch inside `_invoke` produces an id that never escapes the function, so the session is logically one-shot. Per discussion.md "keep-alive default".
- **Applies to:** batches 2, 3.

### Decision: three-rule cleanup model

- **Decision:** Cleanup happens in three places: (1) wrapper success path — kill iff `--keep-alive` not set; (2) wrapper error path — kill iff `session_owned_by_us` is true (i.e. the wrapper created the session this run); (3) caller — `_llm_claude.cleanup_session(session_id)` after each logical session ends (per-batch implement-review-fix loop terminating, and holistic loop terminating).
- **Rationale:** Operator refused to manage processes manually. The three rules together guarantee the only psmux sessions left alive are ones currently mid-use. Per discussion.md "cleanup model".
- **Applies to:** batches 2 (rules 1+2), 3 (rule 3 helper), 4 (rule 3 invocation).

### Decision: error mapping in `_llm_claude._invoke()` psmux branch

- **Decision:** When the wrapper exits non-zero on the psmux branch: raise `LLMSessionError` iff `resume=True` was passed; otherwise raise plain `LLMError`. Drop the existing "psmux path does not support session resume" early-raise. The new `_get_via_psmux_flag()` and `_build_psmux_argv()` keep their existing error contracts unchanged.
- **Rationale:** Mirrors the direct-CLI path. mill-go's fix loop already handles `LLMSessionError` by falling back to a fresh session — same behaviour now works for psmux. Per discussion.md "error mapping in `_llm_claude._invoke()` (psmux branch)".
- **Applies to:** batch 3.

### Decision: ASCII-only stdout/stderr

- **Decision:** Every new `print()` or `_log()` string in `millpy-claude-sub.py`, `_llm_claude.py`, and any unit-test helper is ASCII-only. Em-dash → ` -- `; right-arrow → ` -> `.
- **Rationale:** CLAUDE.md hard rule; Windows cp1252 terminals crash on non-ASCII stdout/stderr.
- **Applies to:** all batches that add log lines (batches 2, 3, 4).

### Decision: hard cutover for config schema move

- **Decision:** `llm.claude.via_psmux` → `llm.claude.psmux.via_psmux` is a hard cutover. No compatibility shim; no read of the legacy flat key. Hub `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml` change in the same commit. Any existing `.millhouse/config.local.yaml` overlay that pins the flat key must be updated by the operator as part of this PR (operator confirmed no other consumers).
- **Rationale:** CLAUDE.md "no backwards-compat shims when you can just change the code"; keeps `_get_via_psmux_flag` to one lookup path.
- **Applies to:** batch 1.

## All Files Touched

_Full union of every `Creates:` / `Edits:` across every batch, sorted
alphabetically. mill-go reads this to warn if two parallel batches
touch the same file — a sign of a misplaced dependency._

- `mill-config.yaml`
- `plugins/mill/scripts/_llm_claude.py`
- `plugins/mill/scripts/millpy-claude-sub.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/unit_tests/test-claude-sub.py`
- `plugins/mill/unit_tests/test-llm-claude.py`
