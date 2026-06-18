# Batch: drift-guard-and-regression-locks

```yaml
task: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches
batch: drift-guard-and-regression-locks
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-skill-helper-drift.py
depends-on: []
```

## Batch Scope

Delivers a single new unit test file, `plugins/mill/unit_tests/test-skill-helper-drift.py`,
that is the durable regression coverage for the "SKILL.md vs shipped-API mismatch" class
(#504/#505) plus the two nested-hub source fixes that this task verifies-but-does-not-re-fix
(#495, #496). The file has two independent check groups: (Card 1) a corpus-wide scan asserting
every mill-helper reference in the mill SKILL.md files resolves to a real shipped function, and
(Card 2) targeted regression locks pinning the already-fixed source state for #495 and #496 so a
future edit cannot silently regress them. This batch is first in the DAG because batch 2's
`verify:` re-runs this same test to confirm its SKILL.md edits introduce no unresolved helper
reference. The test must be GREEN against current source on completion (the known drift is
already fixed). Batch-local decision: scan **only** `plugins/mill/skills/` — the underscore
`_<module>` helper convention is mill-specific; other plugins' SKILLs do not use it and scanning
them would only add false-positives.

## Cards

### Card 1: Drift-guard scan — every mill-SKILL helper reference resolves to a shipped function

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-parent-branch.py`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
- **Deletes:** none
- **Requirements:** Create `test-skill-helper-drift.py` as a plain-Python test (no pytest;
  follow the `test-parent-branch.py` shape — a `main()` that collects failures, prints
  `PASS`/`FAIL` lines, and `sys.exit(1)` on any failure). Compute repo paths relative to the
  file (mirror `test-parent-branch.py`'s `HUB`/`SCRIPTS` derivation; `SKILLS = HUB / "plugins" /
  "mill" / "skills"`, `SCRIPTS = HUB / "plugins" / "mill" / "scripts"`).
  Build the set of available helper functions: walk `SCRIPTS` recursively (`SCRIPTS.rglob("*.py")`,
  so `wiki/_client.py` is included), and for each file parse it with `ast.parse` and collect
  every module-level `ast.FunctionDef` / `ast.AsyncFunctionDef` name keyed by the module stem
  (filename without `.py`) — yielding a mapping `module_stem -> set(function_names)`. The module
  stem is the bare filename (`_client`, `_paths`, `_cleanliness`, ...), matching how SKILLs
  reference helpers (`_client.get_task(`), regardless of subpackage location.
  Scan every `SKILLS.rglob("SKILL.md")` and extract helper references with a regex matching the
  mill convention `_<module>.<fn>(` — i.e. an underscore-prefixed module identifier, a dot, a
  function identifier, then `(`. Match both bare inline-Python calls and the `signature: _module.fn(...)`
  annotation lines (the regex naturally covers both since both contain the `_module.fn(` substring).
  For each extracted `(module_stem, fn)`, assert `module_stem` exists in the mapping AND `fn` is in
  that module's function set; collect every unresolved reference (with the SKILL file + module.fn)
  as a failure. Maintain a module-level `ALLOWLIST: set[tuple[str, str]]` of `(module, fn)` pairs
  that are intentionally exempt (illustrative refs, or underscore-prefixed local-variable method
  calls that are not module functions); a reference in the ALLOWLIST is skipped. When you run the
  scan against current source, curate the ALLOWLIST so the test passes: for each unresolved
  reference, decide — if it is a real local/illustrative non-module reference, add it to the
  ALLOWLIST with an inline comment naming why; if it is a genuine missing-helper in a SKILL OTHER
  than the two this task edits (mill-merge / mill-merge-in), still add it to the ALLOWLIST with a
  `# pre-existing drift, out of scope (see issue/notes)` comment AND list it in this batch's
  implementer report (do not fix other skills here). The test must end GREEN. Keep ASCII-only
  output.
- **Commit:** `test(mill): add SKILL.md helper-reference drift guard`

### Card 2: Regression locks for the already-fixed nested-hub source state (#495, #496)

- **Context:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a second check group to `test-skill-helper-drift.py` that pins the
  already-fixed source facts so they cannot silently regress (the discussion mandates a
  verify-only check for these — encode the grep as an assertion rather than a manual check).
  (a) **#495 lock:** read `plugins/mill/scripts/millpy-review-plan.py` and assert it resolves the
  plan project root via `_paths.resolve_hub_path()` and NOT via bare `Path.cwd()` — assert the
  substring `project_root = _paths.resolve_hub_path()` is present, and assert `project_root = Path.cwd()`
  is absent. (b) **#496 lock:** read `plugins/mill/skills/mill-go/SKILL.md` and assert the holistic
  crash-recovery resolves its reviews dir from the hub — assert the substring `reviews_dir = hub / '_mill/reviews'`
  is present. Use clear failure messages that name the issue number and the file, so a regression is
  self-explanatory. Note in a comment that #504/#505 need no separate lock here — they are covered by
  Card 1's scan, which already asserts `_cleanliness.revert_out_of_scope_drift` (referenced by mill-go)
  resolves to a shipped function. These checks must be GREEN against current source.
- **Commit:** `test(mill): pin already-fixed #495/#496 source state against regression`

## Batch Tests

`verify:` runs only the new `test-skill-helper-drift.py` (single file — the focused scope for
this batch, per the per-batch scoping rule). It covers the corpus-wide helper-reference scan
(Card 1) and the #495/#496 regression locks (Card 2). The file must exit 0 (PASS) against
current source; a non-zero exit means either an uncurated unresolved helper reference or a
regressed source fact. No other unit test is affected by this batch.
