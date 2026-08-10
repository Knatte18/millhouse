# Plan: mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references

```yaml
task: 'mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references'
slug: mill-go-skilldoc-accuracy-gaps
approved: true
started: 20260810-181019
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: mill-go-blocked-halt-fixes
    file: 01-mill-go-blocked-halt-fixes.md
    depends-on: []
    verify: PYTHONPATH= sh -c '[ "$(grep -c "update_field(status_path, .blocked_reason." plugins/mill/skills/mill-go/SKILL.md)" = "0" ] && [ "$(grep -c 600000ms plugins/mill/skills/mill-go/SKILL.md)" = "4" ]'
  - number: 2
    name: mill-plan-portable-cross-refs
    file: 02-mill-plan-portable-cross-refs.md
    depends-on: []
    verify: PYTHONPATH= sh -c '[ "$(grep -c "plugins/mill/skills/mill-go\|plugins/mill/skills/mill-receiving-review\|plugins/mill/docs" plugins/mill/skills/mill-plan/SKILL.md)" = "0" ]'
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: doc-only task, no application/script code changes

- **Decision:** Every card in this plan edits only `SKILL.md` prose in `plugins/mill/skills/mill-go/` and `plugins/mill/skills/mill-plan/`. No `_status.py`, no other `plugins/mill/scripts/*.py` file, and no other `SKILL.md` is touched.
- **Rationale:** `_mill/discussion.md`'s Scope section explicitly excludes application/script code changes and excludes `mill-start/SKILL.md:276` (an identical-pattern bug in a different file, deliberately deferred as a follow-up).
- **Applies to:** all batches.

### Decision: PYTHONPATH= prefix required on every verify:, including the grep-only checks

- **Decision:** Every `verify:` command in this plan (both batches' `verify:` and both `verify:` mirrors in the Batch Index above) starts with the literal `PYTHONPATH=` prefix, even though every command is a plain `grep`/`sh` invocation with no Python involved.
- **Rationale:** This repo has `plugins/mill/pyproject.toml`, so `_plan_validate.py`'s `verify-not-isolated` check (`is_python_project` gate) requires the `PYTHONPATH=` prefix on **every** `verify:` command unconditionally once a Python marker file exists at the project root — the check does not inspect whether the command itself invokes Python. `_mill/discussion.md`'s Testing section claims "no `PYTHONPATH=` prefix is needed... the `verify:` prefix rule in CLAUDE.md applies to Python-project test subprocesses, not to grep-only verify commands with no Python involved" — that claim does not match the validator's actual (unconditional-per-project) behavior, confirmed by reading `_check_verify_not_isolated` in `plugins/mill/scripts/_plan_validate.py`. This plan follows the validator's real behavior rather than the discussion's inaccurate claim, to avoid a guaranteed Step 1.5 validator-fix cycle.
- **Applies to:** all batches.

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
