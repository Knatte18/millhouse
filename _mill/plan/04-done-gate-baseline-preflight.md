# Batch: done-gate-baseline-preflight

```yaml
task: Batch verify/baseline/completeness gates produce false positives or time out
batch: done-gate-baseline-preflight
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-done-gate.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Fixes #650: `pipeline.done_gate` has no pre-implementation baseline pre-flight, so a self-capturing regression/snapshot test suite used as the done_gate silently captures its "baseline" from the task's own just-finished implementation at Handoff, reporting success while providing zero actual regression protection. This batch adds a new, explicitly opt-in Prepare-phase pre-flight step: a new `_done_gate.py` module exposing `run_preflight(gate_cmd, git_root) -> dict` (reusing the exact subprocess-invocation shape the existing Handoff-time "0. Pre-done gate" inline-Python block already uses), a new `pipeline.done_gate_baseline_preflight` config key (default `false`), and a new SKILL.md Prepare-phase block that calls it once before batch 1, non-blocking on a `blocked` result. The external interface batch 05 depends on: the new SKILL.md block this batch's Card 16 adds must exist before batch 05 can annotate it with the extended-timeout note, hence batch 05's `depends-on: [4]`.

## Cards

### Card 14: New `_done_gate.py` module

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_done_gate.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Expose `run_preflight(gate_cmd: str | None, git_root: Path) -> dict`. If `gate_cmd is None`: return `{"result": "skipped", "reason": "no done_gate configured"}`. Otherwise run `subprocess.run(gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True)` — the exact invocation shape already used inline in mill-go SKILL.md's existing Handoff-time "0. Pre-done gate" block (read that block in `plugins/mill/skills/mill-go/SKILL.md` for the exact shape to mirror, including its stdout+stderr concatenation and the 2000-character tail truncation on the captured output). Non-zero exit → `{"result": "blocked", "reason": <captured output, truncated to 2000 chars exactly as the Handoff-time block does>}`. Zero exit → `{"result": "ok"}`. This function must never raise to its caller — wrap the subprocess call so any unexpected failure (e.g. `gate_cmd` invokes a missing binary) also degrades to a `{"result": "blocked", "reason": ...}` dict rather than propagating an exception, per this plan's own Shared Decision.
- **Commit:** `feat(_done_gate): add run_preflight for opt-in done_gate baseline pre-flight`

### Card 15: New config key `pipeline.done_gate_baseline_preflight`

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In both files' `pipeline:` section, add a new line immediately below the existing `done_gate: null  # ...` line: `done_gate_baseline_preflight: false  # Opt-in Prepare-phase done_gate baseline capture for self-capturing regression suites; see done_gate above. (#650)`. Match the existing comment style (inline `#` comment, same indentation as the sibling `done_gate` key) in both files exactly.
- **Commit:** `feat(config): add pipeline.done_gate_baseline_preflight key`

### Card 16: Wire the new Prepare-phase block into mill-go SKILL.md

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Insert a new subsection titled `### 0.55. Done-gate baseline pre-flight (first batch of the task only)` between the existing `### 0. Wiki health-check` and `### 0.5. Baseline pre-flight (first batch of the task only)` subsections. Content: read `(cfg.get("pipeline") or {}).get("done_gate_baseline_preflight", False)` and `(cfg.get("pipeline") or {}).get("done_gate")`; if the preflight flag is falsy OR `done_gate` is `None`/absent, skip this step entirely (log nothing, proceed to "0.5. Baseline pre-flight"). Otherwise, invoke an inline `$MILL_PYTHON -c "..."` Bash block (mirroring the shape of the existing "0. Pre-done gate" block's own inline-Python invocation) that imports `_done_gate` and calls `_done_gate.run_preflight(gate_cmd, git_root)`, printing the resulting JSON dict. Parse the result: a `blocked` result is logged (the reason string, ASCII-only) but does NOT halt the task — proceed to batch 1 regardless, exactly as this plan's `done-gate-baseline-preflight` decision in `_mill/discussion.md` specifies (a failing pre-implementation parent-branch state is diagnostic, not something this task's batches can fix, and blocking Prepare on it would make an otherwise-startable task undispatchable). Runs from `git_root` (not hub dir), identical cwd to the Handoff-time "0. Pre-done gate" block. Runs exactly once per task — first batch of the task only, same guard shape already documented for "0.5. Baseline pre-flight" (do not re-run on every batch).
- **Commit:** `feat(mill-go): add opt-in Prepare-phase done_gate baseline pre-flight step`

### Card 17: Unit tests for `_done_gate.run_preflight`

- **Context:**
  - `plugins/mill/scripts/_done_gate.py`
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-done-gate.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Follow `test-verify-baseline.py`'s exact style (single `main() -> int` function, inline numbered cases, `PASS`/`FAIL` prints, accumulated error count, `sys.exit(main())` at the bottom) per this plan's Shared Decision on new test-file conventions. Mock `subprocess.run` (no real shell command execution). Cover: (a) `gate_cmd=None` → `{"result": "skipped", "reason": "no done_gate configured"}`; (b) mocked exit 0 → `{"result": "ok"}`; (c) mocked exit 1 with captured stdout/stderr → `{"result": "blocked", "reason": <matches captured output>}`; (d) a mocked `subprocess.run` that raises an exception (e.g. missing binary) → `run_preflight` still returns a dict (does not raise) — confirms the never-raise contract from this plan's Shared Decision.
- **Commit:** `test(done-gate): cover run_preflight result shapes and never-raise contract`

## Batch Tests

`verify:` (frontmatter above) runs the new `test-done-gate.py` file (Card 17). The SKILL.md and config-template edits (Cards 15, 16) have no independently runnable surface beyond what `test-done-gate.py` already exercises through `_done_gate.run_preflight` itself.
