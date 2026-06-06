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
  ONLY when the post-fix verify command actually passes. There are exactly
  three cases; implement them explicitly:
  - **Case A -- verify passes before any fixer runs** (the existing
    early-return where the initial verify `returncode == 0`, e.g. the merge
    already fixed it): emit `{"status":"success","commit_sha": <HEAD>}` as
    today. No fixer needed.
  - **Case B -- fixer ran, post-fix verify passes** (`returncode == 0`):
    emit `{"status":"success","commit_sha": <HEAD>}`.
  - **Case C -- fixer ran, post-fix verify still fails**
    (`returncode != 0`): emit `{"status":"stuck","stuck_type":"verify",
    "reason": <verify stdout+stderr>}`. Do NOT fall through to
    `finalize_from_output(...)` (finalize stage) or `_forward_output(...)`
    (full stage) -- both can infer/forward success from the agent's
    self-reported output even though verify failed; that is the bug.
  Apply Case C at BOTH success-emit sites: the `--stage finalize` block
  (the post-verify branch that currently calls `finalize_from_output` on
  non-zero) and the `--stage full` post-sub-agent re-verification in
  `_run_verify_fix` (the branch that currently calls `_forward_output`).
  Do NOT use HEAD-vs-checkpoint as the success signal -- the verify result
  is the gate. `millpy-merge-in-subagent.py` is this card's Edits target
  and is implicitly read; no separate Context entry is needed. Additionally,
  clarify the `--checkpoint` flag handling by (1) updating the argparse help
  text to note that `--checkpoint` is only consumed in full mode, not finalize
  mode, and (2) adding an inline comment in `_run_verify_fix` explaining that
  the flag is not required for prepare/finalize stages. ASCII-only messages.
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

Ordering: Card 24 Creates `test-merge-in-subagent.py`, which the `verify:`
`--only` flag requires on disk. mill-go runs `verify:` once at batch end
after both cards are implemented and committed, so the file exists when
verify runs.
