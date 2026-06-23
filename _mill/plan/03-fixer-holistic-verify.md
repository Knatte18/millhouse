# Batch: fixer-holistic-verify

```yaml
task: "Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling"
batch: fixer-holistic-verify
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-millpy-fix.py
depends-on: [2]
```

## Batch Scope

Fixes #518b — the holistic fixer could report success while leaving a knowingly-failing test, because the holistic path passes `verify_cmd=None` (no script-side gate). Adds a structural catch: `millpy-fix.py`'s holistic finalize derives a concatenated `verify_cmd` from the non-null per-batch `verify:` commands (via `_plan_dag.iter_batch_verifies`) and runs the existing `_run_verify_gate`, so a self-induced failing/timing-out test auto-demotes to `stuck/verify`. Complements this with a brief-level judgement path: the fixer returns `stuck_type: logic` when a BLOCKING demand is physically unsatisfiable. Depends on batch 2 (shared `millpy-fix.py` / `test-millpy-fix.py` writes). No downstream consumer.

## Cards

### Card 8: derive concatenated holistic verify_cmd and run the gate

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The critical hook is the `--stage finalize` branch (around lines 192-213), because `dispatch == agent` (this hub) emits success via `finalize_from_output`, not the full stage. Today that branch sets `verify_cmd = None` and only resolves a real command `if args.scope == "batch"`. Change it so that for `args.scope == "holistic"` it derives a command: reuse the already-resolved `plan_base = _paths.resolve_task_path(project_root, "_mill/plan/")` (computed at line 170), call `_plan_dag.iter_batch_verifies(plan_base)` (returns non-null `(batch_name, verify_cmd)` pairs in DAG order), take the `verify_cmd` values, and join with ` && ` to form the holistic `verify_cmd`; if the list is empty, leave `verify_cmd = None`. Pass it into the existing `finalize_from_output(..., verify_cmd=verify_cmd)` call so a non-zero combined exit demotes a self-reported `success` to `stuck/verify` via `_run_verify_gate`. Apply the same derivation to the holistic full-stage dispatch path (the `args.scope == "holistic"` branch that currently passes `verify_cmd=None` to `_forward_output`) so subprocess/psmux mode is also gated. Join contract: `iter_batch_verifies` already filters null/missing verifies, so no dangling ` && ` is possible; each survivor keeps its own `PYTHONPATH= ` prefix. ASCII-only.
- **Commit:** `feat(fix): structural holistic verify gate via derived batch verify_cmd`

### Card 9: fixer-brief unsatisfiable-demand contract + receiving-review language

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:**
  - `plugins/mill/templates/fixer-batch-brief.md`
  - `plugins/mill/templates/fixer-holistic-brief.md`
  - `plugins/mill/skills/mill-receiving-review/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In both fixer briefs, add an instruction: if a BLOCKING finding requires a change the fixer can demonstrate CANNOT pass (e.g. an in-process test of a detached-spawn / `os.Executable()` path, or a demand contradicting an in-repo analog the codebase deliberately follows), the fixer must NOT comply silently — it returns `stuck_type: logic` describing the contradiction and citing the in-repo analog, rather than producing a knowingly-failing test reported as success. In `fixer-holistic-brief.md` additionally reinforce: run the full verify and do not report `success` while any test is failing or timing out. Use the `stuck_type` vocabulary already documented in `millpy-fix.py`. In `mill-receiving-review/SKILL.md`, extend the HARM CHECK / Legitimate-Pushback section to name the "physically unsatisfiable / contradicts in-repo convention" case explicitly as a valid pushback. ASCII-only.
- **Commit:** `feat(fixer): route unsatisfiable BLOCKING demands to stuck_type:logic`

### Card 10: tests for the derived holistic verify gate

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-millpy-fix.py`, add cases for the holistic derivation: (a) a plan with two batches having non-null `verify:` derives `cmd1 && cmd2` and, when the combined command exits non-zero (use a stub like `exit 1`), demotes a self-reported `success` to `stuck/verify`; (b) the same with a passing stub (`exit 0`) preserves `success`; (c) a plan whose batches all have `verify: null` derives `None` (no gate, success preserved). Reuse the `_run_verify_gate` fixture style from `test-implementer-common.py`. Drive the plan-dir fixture with synthetic `00-overview.md` + batch files, or monkeypatch `_plan_dag.iter_batch_verifies` to return controlled pairs — pick whichever matches the existing fix-test fixtures.
- **Commit:** `test(fix): cover derived holistic verify gate (pass/fail/none)`

## Batch Tests

`verify:` runs `test-millpy-fix.py` — the only suite with runnable surface here (the derived-gate logic lives in `millpy-fix.py`). The fixer-brief and `mill-receiving-review` edits are prose validated by the plan reviewer; card 10 separately asserts the briefs contain the unsatisfiable-demand instruction via a content check if practical. Key scenarios: pass/fail/none derivation in card 10.
