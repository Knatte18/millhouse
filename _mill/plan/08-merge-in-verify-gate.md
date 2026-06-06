# Batch: merge-in-verify-gate

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
batch: merge-in-verify-gate
number: 8
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-merge-in-subagent.py
depends-on: []
```

## Batch Scope

Fixes the merge-in verify-fix sub-agent so it cannot report success when
the fix did not actually fix anything (#409): success is gated strictly on
the post-fix verify passing. Confined to `millpy-merge-in-subagent.py`
(kept out of `_implementer_common.py` so the implementer batch is
unaffected).

## Cards

### Card 23: Gate verify-fix success on post-fix verify passing

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** For `--mode verify-fix`, report `{"status":"success"}`
  ONLY when the post-fix verify command actually passes. (1) In the
  `--stage finalize` block: when the post-verify `returncode == 0`, keep
  emitting success; when it is non-zero, emit `{"status":"stuck",
  "stuck_type":"verify","reason": <verify stdout+stderr>}` instead of
  falling through to `finalize_from_output(...)` (which can infer success
  from the agent output). (2) In `_run_verify_fix` `--stage full`: after
  the post-sub-agent re-verification, when the post-verify is non-zero,
  emit the same `stuck`/`verify` JSON instead of calling
  `_forward_output(output, ...)` (which trusts the agent's self-reported
  success). The legitimate "verify already passes (e.g. the merge fixed
  it), no fixer needed" path must still report success. Do NOT use
  HEAD-vs-checkpoint as the success signal -- the verify result is the
  gate. ASCII-only messages.
- **Commit:** `fix(merge-in): gate verify-fix success on post-fix verify passing`

### Card 24: Test merge-in verify-fix success gating

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-merge-in-subagent.py`
- **Deletes:** none
- **Requirements:** Create `test-merge-in-subagent.py` driving the
  verify-fix finalize/full paths with `subprocess.run` (the shell verify
  call) and `_implementer_claude.run` monkeypatched: (a) post-fix verify
  passes -> JSON `status: success`; (b) post-fix verify fails -> JSON
  `status: stuck`, `stuck_type: verify`, and NOT success, even when the
  monkeypatched agent output claims success; (c) verify already passes with
  no fixer needed -> success. Parse the JSON emitted on stdout. Avoid real
  git/LLM; resolve a temp project root and monkeypatch
  `_marker.slug_from_branch` / config loading as needed following existing
  test patterns.
- **Commit:** `test(merge-in): cover verify-fix success gating`

## Batch Tests

`verify:` runs the new `test-merge-in-subagent.py`. The shell verify
command and the sub-agent dispatch are monkeypatched; the test asserts the
emitted JSON verdict for passing/failing post-fix verify.
