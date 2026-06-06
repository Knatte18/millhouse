# Batch: plan-verify-language-aware

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
batch: plan-verify-language-aware
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: []
```

## Batch Scope

Makes the `verify-not-isolated` plan-validator check Python-project-aware
so Go/C# verify commands are not forced to carry a meaningless
`PYTHONPATH=` prefix (#421), and updates the two docs that enshrine the
universal rule (mill-plan SKILL.md and the repo CLAUDE.md). Touches
`_plan_validate.py` and the two markdown docs only.

## Cards

### Card 7: Python-aware `verify-not-isolated` check

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_check_verify_not_isolated`, only require the
  `verify_stripped.startswith("PYTHONPATH=")` prefix when the project is a
  Python/mill project. Detect this by the presence of a Python marker at
  the worktree root -- `pyproject.toml` (root or `plugins/mill/`), or
  `setup.py`/`setup.cfg`. When no Python marker is present (e.g. a Go repo
  with `go.mod`, or a C# repo with a `.csproj`/`.sln`), skip the check
  entirely (return no findings for that batch) so a native `verify:` such
  as `go test ./...` is accepted. The detection must derive the worktree
  root from the batch files' location (do not consult cwd for the marker;
  thread the resolved root). Keep the existing finding shape
  (`check`/`batch`/`path`/`message`) unchanged when the check does fire.
- **Commit:** `fix(plan-validate): require PYTHONPATH= verify prefix only for Python projects`

### Card 8: Reword the universal PYTHONPATH= rule in docs

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-plan/SKILL.md`, update the "Verify command
  shape" guidance (and the plan-batch template reference if mirrored) so it
  states the `PYTHONPATH= ` prefix is required for verify commands that
  invoke a Python interpreter or `uv` (Python/mill projects), NOT as a
  universal prefix; non-Python projects use the native test runner
  directly. In `CLAUDE.md` (repo root), update the `## Script invocation`
  "Verify command shape" note the same way -- the rule is Python-only and
  the validator now enforces it conditionally. Do not change the behavior
  description for Python projects (the prefix still prevents cache-PYTHONPATH
  inheritance). ASCII-only.
- **Commit:** `docs(plan): clarify PYTHONPATH= verify prefix is Python-only`

### Card 9: Test language-aware verify check

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add cases driving `_check_verify_not_isolated` (or the
  top-level validate entry) against a temp worktree: (a) Python marker
  present + a batch `verify:` lacking `PYTHONPATH=` -> one
  `verify-not-isolated` finding; (b) Python marker present + `verify:` with
  the prefix -> no finding; (c) no Python marker (e.g. only a `go.mod`) +
  a native `verify: go test ./...` -> no finding. Follow the existing
  fixture style in `test-plan-validate.py`.
- **Commit:** `test(plan-validate): cover Python-aware verify-not-isolated check`

## Batch Tests

`verify:` runs `test-plan-validate.py` only. The new cases construct temp
worktrees with/without Python markers and assert the finding set; no real
review or git is involved.
