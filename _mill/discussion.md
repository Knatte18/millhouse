# Discussion: Repair two failing unit tests on main

```yaml
task: Repair two failing unit tests on main
slug: fix-stale-unit-tests
status: discussing
parent: main
```

## Problem

Two unit tests under `plugins/mill/unit_tests/` fail on main because the code they guard moved on and the tests did not.
Sources: GitHub issues #1147 and #1146.

- `test-millpy-validate-plan.py::test_cli_uses_resolve_hub_path_not_cwd_for_project_root` raises `TypeError`.
  `scripts/millpy-validate-plan.py:56` now passes `done_gate=cfg.get("pipeline", {}).get("done_gate")` to `_plan_validate.run`, but the test's fake `_fake_plan_validate_run(plan_dir_arg, project_root_arg, *, wiki_root, skip_checks)` (line 327) does not accept it.
- `test-mill-go-base-agent-only.py` fails with `contains banned literal 'millpy-bg'` on `skills/mill-go-base/SKILL.md`.
  `BANNED_LITERALS = ("psmux", "millpy-bg", "dispatch == subprocess")` (line 27) was written when subprocess dispatch was stripped.
  SKILL.md now legitimately uses `millpy-bg` (4 occurrences: speculative baseline launch ~line 197/202, and the subprocess/psmux review-dispatch branch ~lines 592/595).

## Scope

**In:**
- Fix the fake in `test_cli_uses_resolve_hub_path_not_cwd_for_project_root` so it accepts `done_gate`.
- Fix `BANNED_LITERALS` in `test-mill-go-base-agent-only.py` so it no longer bans `millpy-bg`.

**Out:**
- Any change to `millpy-validate-plan.py`, `_plan_validate.py`, or any SKILL.md / companion file.
- Other tests, and any broader test-suite cleanup.

## Decisions

### validate-plan fake signature

- Decision: add `done_gate=None` as a keyword-only parameter to `_fake_plan_validate_run`, matching the real `_plan_validate.run` signature (`done_gate: str | None = None`).
- Rationale: the test's purpose is the `project_root` threading (#728); the fake only needs to be call-compatible.
  A default keeps it robust if the CLI later omits the kwarg.
- Rejected: `**kwargs` catch-all (hides future signature drift); asserting a specific `done_gate` value (out of this test's purpose).

### millpy-bg ban

- Decision: remove `"millpy-bg"` from `BANNED_LITERALS`; keep `"psmux"` and `"dispatch == subprocess"`.
  Update the module/function docstrings and comments that mention the ban list only if they name `millpy-bg`.
- Rationale: `millpy-bg` is a live, supported helper used by SKILL.md; the dead literals the guard targets are `psmux` and `dispatch == subprocess`, which still pass.
- Rejected: narrowing to a `millpy-bg` context regex (fragile, guards nothing real); skipping SKILL.md for that literal (weakens the guard on companions for no reason).

## Technical context

- Test files: `plugins/mill/unit_tests/test-millpy-validate-plan.py`, `plugins/mill/unit_tests/test-mill-go-base-agent-only.py`.
- Only `SKILL.md` contains `millpy-bg`; the three companions (`resume.md`, `holistic-review.md`, `handoff.md`) have zero occurrences, and no file contains `psmux` or `dispatch == subprocess`.
- Verified failing today: the agent-only test prints the single `millpy-bg` failure on SKILL.md.

## Testing

- Both fixes are edits to the tests themselves; there is no TDD candidate beyond "the two named tests go from failing to passing".
- Verify: run each test file directly, then `run-all.py`, via `uv run --project plugins/mill`, with `PYTHONPATH=` empty per CLAUDE.md verify-command shape.
- No other test may regress.

## Q&A log

- **Q:** Fix the fake's signature exactly, or use `**kwargs`? **A:** [auto-pick] Add explicit `done_gate=None`. **Why:** mirrors the real signature and does not mask future drift.
- **Q:** Drop `millpy-bg` from the ban list, or narrow the check? **A:** [auto-pick] Drop it. **Why:** the helper is legitimately live; the other literals still guard the dead dispatch paths.
