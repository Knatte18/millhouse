# Batch: wiki-health-check

```yaml
task: (A) — Small infra fixes batch 7
batch: wiki-health-check
number: 1
cards: 3
verify: PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/test-wiki.py" && PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/unit_tests/run-all.py"
depends-on: []
```

## Batch Scope

Delivers GitHub issue #273 — mill-go's Execute loop runs a wiki health check at the start of every batch (and at the start of every Holistic code review round) so a wiki dir disappearance between batches surfaces a clean halt instead of the implementer's downstream "Missing config at <path>/config.yaml" error. Adds `_wiki.health_check(wiki_path) -> None` and `_wiki.WikiHealthError`, three unit tests covering the helper, and SKILL.md edits in two places (Execute loop sub-step 0 and Holistic loop sub-step 0).

Batch-local decision: the SKILL.md inline `python -c "..."` block uses an explicit `except _wiki.WikiHealthError` handler that prints to stderr and raises `SystemExit(1)`. The outer Bash `|| { ... }` block then releases the builder lock and prints the operator-facing halt message before `exit 1`. The order is non-negotiable — lock release must precede the orchestrator's exit, or a subsequent mill-go invocation self-deadlocks (mill-go's builder-lock acquire at Entry step 4 will block forever).

## Cards

### Card 1: Add `WikiHealthError` and `health_check()` to `_wiki.py`

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add a new exception class `WikiHealthError(Exception)` to `_wiki.py` immediately after the existing `LockBusy` class (currently at line 152). The class stores the wiki path as `self.wiki_path: Path` (set via `__init__(self, wiki_path: Path, message: str)`); `super().__init__(message)` carries the message. The class docstring states it is raised by `health_check` when the wiki clone appears missing or corrupted.

  Add a new public function `health_check(wiki_path: Path) -> None` to `_wiki.py`. Place it immediately after `sync_pull` (currently ends near line 289) and BEFORE `write_commit_push`. Behaviour:
  - If `wiki_path` does not exist (`not wiki_path.exists()`) → raise `WikiHealthError(wiki_path, f"wiki directory does not exist at {wiki_path}")`.
  - If `wiki_path` exists but `wiki_path / "config.yaml"` does not exist (`not (wiki_path / "config.yaml").exists()`) → raise `WikiHealthError(wiki_path, f"wiki/config.yaml missing at {wiki_path / 'config.yaml'}")`.
  - Otherwise return `None`.

  Add the helper to the module docstring's "Public API" list at the top of the file (between `sync_pull` and `write_commit_push`). Function docstring states purpose, signature, when it raises, and the message format. No `sys.exit` calls; raise the typed exception only.

  Append `WikiHealthError` to the `Exceptions:` block in the module docstring (currently lines 52–62 of `_wiki.py`, listing `LockBusy`, `WikiPushError`, `WikiSetupError`). Insert it immediately AFTER `WikiSetupError`, matching the same two-line shape: a short summary of when it is raised, with the second line documenting that it carries the `wiki_path` attribute.

  Update the `__all__` list if present (check the file). Otherwise no further surface change.
- **Commit:** `feat(wiki): add health_check and WikiHealthError to _wiki`

### Card 2: Unit tests for `_wiki.health_check`

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Extend `plugins/mill/unit_tests/test-wiki.py` with three new test cases. The file's existing pattern is INLINE `try / except` blocks inside the single `main()` function — each test labelled `# --- (a) ... ---`, `# --- (b) ... ---`, etc. — using the local `ok(name)` and `fail(name, exc)` helpers defined at the top of `main()` (lines 45–57) which update the file-local `passed` / `failed` counters and print/stderr the result. There is NO function-list dispatch; do NOT introduce one.

  Tests required (added as new lettered cases after the existing final case in `main()`, inside the same `passed` / `failed` scope):

  - `# --- (X) health_check passes when config.yaml present ---`: inside a `try:` block, `with tempfile.TemporaryDirectory() as tmp_str:`, build `wiki = Path(tmp_str)` and write `wiki / "config.yaml"` with any non-empty content. Call `_wiki.health_check(wiki)` and assert it returns `None` and does NOT raise. On success: `ok("health_check: returns None when config.yaml present")`. On exception: outer `except Exception as exc: fail("health_check: returns None when config.yaml present", exc)`.
  - `# --- (Y) health_check raises when config.yaml missing ---`: outer `try:` block, `with tempfile.TemporaryDirectory() as tmp_str:`, build `wiki = Path(tmp_str)` (do NOT write `config.yaml`). Wrap the `_wiki.health_check(wiki)` call in an inner `try: ... except _wiki.WikiHealthError as exc: ...` so we can assert the raise happened. Inside the inner `except`, assert `str(wiki / "config.yaml")` is a substring of `str(exc)`. If the inner `try` fell through without raising, raise `AssertionError("health_check did not raise for missing config.yaml")`. Wrap the whole thing in the outer `try / except Exception as exc: fail(..., exc)` and `ok("health_check: raises when config.yaml missing")` on success — matching tests (a)–(d) verbatim.
  - `# --- (Z) health_check raises when wiki dir missing ---`: outer `try:` block, `with tempfile.TemporaryDirectory() as tmp_str:`, build `nonexistent = Path(tmp_str) / "nonexistent-wiki"` (do NOT create the directory). Inner `try: ... except _wiki.WikiHealthError as exc: ...` around the `_wiki.health_check(nonexistent)` call. Inside the inner `except`, assert: (1) `str(nonexistent)` is a substring of `str(exc)`, and (2) `exc.wiki_path == nonexistent` (uses the `.wiki_path` attribute introduced in Card 1). If the inner `try` fell through without raising, raise `AssertionError("health_check did not raise for missing wiki dir")`. Same outer `fail` / `ok("health_check: raises when wiki dir missing")` wrapping.

  All three new cases must use the existing `ok(name)` and `fail(name, exc)` helpers (NOT new counters; NOT a separate test-function list; NOT `print("PASS: ...")` directly — the `ok` helper handles the print). Module-qualify the call site (`_wiki.health_check(...)`). The lettered prefix `(X)/(Y)/(Z)` is a placeholder — use the next available letter after the file's last existing case (the file already runs through several letters; pick whichever three come next).
- **Commit:** `test(wiki): cover health_check happy + missing-config + missing-dir paths`

### Card 3: Wire health check into mill-go SKILL.md

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Edit `plugins/mill/skills/mill-go/SKILL.md` to add a wiki health-check sub-step at the start of each Execute loop iteration AND at the start of each Holistic code review round. Both sub-steps share identical content.

  Insertion locations in `mill-go/SKILL.md`:
  - **Execute loop**: Insert a new sub-section titled `### 0. Wiki health-check` immediately BEFORE the existing `### 1. Implement` heading (currently line 84). The new sub-section is the first work each batch iteration performs.
  - **Holistic code review loop**: Insert a new step `0. Wiki health-check` immediately BEFORE the existing step `1. Crash-recovery.` heading (currently line 239). Keep the existing step numbers as they are; the new step is `0`, so the existing list reads `0, 1, 2, ...`. Steps `1` through `7` in the section keep their numbers.

  Sub-section / step body (identical in both insertion locations except for the heading style — `### 0.` for Execute, `0.` for Holistic):

  ```bash
  PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import sys
  import _paths, _wiki
  wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
  try:
      _wiki.health_check(wiki_path)
  except _wiki.WikiHealthError as e:
      print(f'[mill-go] wiki health check failed: {e}', file=sys.stderr)
      raise SystemExit(1)
  " || {
      PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
      echo "[mill-go] HALT: wiki appears missing or corrupted — re-run mill-setup to restore it" >&2
      exit 1
  }
  ```

  The body is preceded by one paragraph of explanatory prose (a single line):
  > Before launching the implementer / reviewer for this batch, verify the wiki is intact. If the check fails, release the builder lock and halt — the wiki disappeared mid-run and the implementer's downstream "Missing config" error would mask the root cause.

  The `### 0. Wiki health-check` sub-section in the Execute loop sits at the same indentation depth as `### 1. Implement` (level-3 heading). In the Holistic loop, the new `0.` step is an unnumbered-to-LLM numbered-list entry matching the style of the existing `1.` / `2.` / `3.` items in that section (they use plain `1.` Markdown-list prefixes, not `Step 1.` headings).

  After the edit, the Execute loop's first action is the health check; the second is `### 1. Implement` (existing). The Holistic loop's first action per round is the health check; the second is `1. Crash-recovery.` (existing). No other text in the SKILL.md changes — leave the Step 0 / Entry / Prepare / Resume / Stuck / Blocked / Handoff sections untouched.
- **Commit:** `feat(mill-go): wiki health-check per batch + per holistic round`

## Batch Tests

The frontmatter `verify:` runs `unit_tests/test-wiki.py` first (fast feedback on the new tests) then `unit_tests/run-all.py` (regression guard across every other test file in the suite).

Acceptance:
- `test-wiki.py` exits 0 with the three new `test_health_check_*` PASS lines present in stdout.
- `run-all.py` exits 0 (no other test files regress; the new tests count toward the suite total).

SKILL.md changes are NOT unit-tested directly. The implementer verifies the SKILL.md edit by re-reading the inserted sub-section and confirming both insertion locations are present.
