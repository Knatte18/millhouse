# Batch: implementer-correctness

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
batch: implementer-correctness
number: 5
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py test-millpy-implement.py test-implementer-common.py
depends-on: []
```

## Batch Scope

Fixes three implementer-side correctness bugs: junction false-positives in
scope-violation detection (#427), missing-binary verify failures
misclassified as transient (#425), and formatter-induced dirty trees after
success (#426). Touches `_cleanliness.py`, `millpy-implement.py`,
`_implementer_common.py`, and the implementer brief template.

## Cards

### Card 14: Exclude junctions from scope-violation detection

- **Context:**
  - `plugins/mill/scripts/_pygit2_util.py`
  - `plugins/mill/scripts/_gitignore.py`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `compute_scope_violations`, exclude the junction
  directory names from the reported violations. Define a module-level
  skip-set of junction names (`.active`, `.portals`, `.wiki`, and
  `.others`) and skip any untracked path whose first path segment is in
  that set, in addition to the existing `_mill/` skip. This is required
  because pygit2's `status_porcelain` reports the junction symlinks even
  though they are gitignored (verified: returns `.portals`/`.wiki` in a
  clean worktree). Keep the function returning sorted bare path strings.
- **Commit:** `fix(cleanliness): exclude junction dirs from scope_violations`

### Card 15: Classify missing-binary verify failures as non-transient

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/templates/implementer-brief.md`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** A deterministic verify failure caused by a
  missing/unresolvable command (command-not-found / "No such file" / binary
  absent, e.g. `go` not in PATH) must be reported as `stuck_type: verify`
  (not `transient`), so mill-go does not auto-retry a deterministic
  failure. In `millpy-implement.py`, where an `_llm_claude.LLMError` is
  caught and currently always emits `{"status":"stuck",
  "stuck_type":"transient", ...}`, inspect the error text and classify
  command-not-found / missing-binary signals as `stuck_type: verify`; leave
  genuine transient signals (timeout, dead session) as `transient`.
  Implement the signal detection as a small pure helper (e.g.
  `classify_stuck_type(reason: str) -> str`) so it is unit-testable.
  Keep `commits_made` reporting unchanged.
- **Commit:** `fix(implement): classify missing-binary verify failure as stuck_type verify`

### Card 16: Commit formatter drift before reporting success

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Prevent a `success` report from leaving a dirty tree
  caused by a formatter the verify step ran (e.g. gofmt whitespace). Two
  coordinated changes: (1) in `templates/implementer-brief.md`, instruct
  the implementer to run any project formatter BEFORE the final commit and
  to stage+commit all resulting changes, so no formatter drift remains.
  (2) In `_implementer_common.py`, in the success-finalization path
  (`_forward_output` / `finalize_from_output` inferred-success), if the
  only remaining working-tree change after the implementer's commit is
  WHITESPACE-ONLY formatter drift, auto-commit it (a single
  `chore(format): commit formatter drift` commit) before emitting
  `success`, rather than letting the downstream cleanliness gate block the
  batch. Detection heuristic (deterministic): the residual dirt is
  treated as formatter drift ONLY when `git diff` (tracked files) is
  non-empty BUT `git diff --ignore-all-space` (i.e. `git diff -w`) is
  empty AND there are no untracked files -- meaning every remaining change
  is pure whitespace. If `git diff -w` still shows changes, or untracked
  files exist, the dirt is NOT formatter drift: leave it for the
  cleanliness gate to block (do not mask real uncommitted work). If either
  `git diff` subprocess used by the heuristic returns non-zero or raises,
  treat the result as "not formatter drift" (skip the auto-commit and
  proceed normally) -- never let the heuristic itself fail the run.
  ASCII-only messages.
- **Commit:** `fix(implement): commit formatter drift before success report`

### Card 17: Tests for implementer-correctness fixes

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-cleanliness.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** `test-cleanliness.py`: assert `compute_scope_violations`
  excludes `.active`/`.portals`/`.wiki` (drive via a monkeypatched
  `status_porcelain` returning those as `?? ` lines plus a genuine
  out-of-scope file -> only the genuine file is reported).
  `test-millpy-implement.py`: unit-test `classify_stuck_type` ->
  command-not-found/missing-binary text yields `verify`; timeout/dead-session
  text yields `transient`. `test-implementer-common.py`: cover the
  formatter-drift auto-commit decision (formatter-only residual ->
  auto-commit then success; genuine non-formatter dirt -> not masked).
  Follow existing fixture style; monkeypatch git/subprocess boundaries.
- **Commit:** `test(implement): cover junction skip, stuck classification, formatter drift`

## Batch Tests

`verify:` runs `test-cleanliness.py`, `test-millpy-implement.py`, and
`test-implementer-common.py`. Pure helpers (`classify_stuck_type`,
scope-violation filtering) are tested directly; git/subprocess boundaries
are monkeypatched.
