# Batch: resolve-symbol-tests

```yaml
task: '_plan_validate.py _resolve_symbol_files: naive whole-file text search, no declaration-form check'
batch: resolve-symbol-tests
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [1]
```

## Batch Scope

This batch adds unit test coverage in `plugins/mill/unit_tests/test-plan-validate.py` for the resolution-engine changes batch `resolve-symbol-engine` (this batch's dependency) makes: declaration-form matching, qualifier disambiguation, solution-scope pruning, and a characterization test per source issue (#1008, #1015, #1023, #1030, #1033, #1037). No source files under `plugins/mill/scripts/` are touched in this batch. Every card follows the existing test file's own established pattern — call `_plan_validate.run(plan_dir, project_root)` against a `tempfile.TemporaryDirectory()`-backed fixture built with the file's existing `_make_overview`/`_make_batch_file`/`_write_plan` helpers, then assert on the `check_errors = [e for e in result if e["check"] == "context-completeness"]` list, exactly as every existing `test_check_context_completeness_symbol_*` test already does. Scenarios are described here in terms of that public, observable contract — fixture file content and the resulting `context-completeness` errors — not in terms of the internal helper names batch `resolve-symbol-engine` introduces, since this batch's own `Context:`/`Edits:` intentionally does not include `plugins/mill/scripts/_plan_validate.py` (a black-box test against the already-implemented, already-committed behavior of the prior batch needs no read access to its source).

## Cards

### Card 3: Declaration-form matching tests (all four languages)

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add new `test_check_context_completeness_symbol_*` functions (naming convention matches the existing suite; register each in the `tests` list at the bottom of the file) covering, for each of `.go`, `.cs`, `.py`, `.ts`:

  1. A token whose only occurrence in the fixture project is inside a `//`/`#` comment (not any declaration-form line) resolves to zero `context-completeness` errors.
  2. A token whose only occurrence is inside a string or template literal (e.g. a Go struct tag like `` `json:"foo_bar"` ``, or a JSON-shaped string constant) resolves to zero errors.
  3. A token whose only occurrence is a usage/field-access site in an unrelated file (e.g. `obj.Field = 1` or a function call `Helper()` where `Helper` is never itself declared in that file) resolves to zero errors.
  4. A token at a genuine top-level declaration (Go: `func`/`type`/`const`/`var`; C#: a `class`/`struct`/`interface`/`enum`/`record` or a modifier-prefixed method/property/field; Python: `def`/`class`; TS: `function`/`class`/`interface`/`type`/`enum`/`const`/`let`/`var`) still resolves to exactly one `context-completeness` error naming that file, when the file is absent from the card's own refs — this is the regression case, confirming the existing suite's Go coverage extends correctly to the other three languages.
  5. Go only: a token declared solely inside a grouped `const ( … )` block, a grouped `var ( … )` block, and a grouped `type ( … )` block (three separate scenarios, or one fixture file exercising all three token names) each resolve to exactly one error naming that file.
  6. Python only: a token declared solely as a module-level (column-0) assignment (e.g. `MAX_SIZE = 100`) resolves to exactly one error naming that file; the same token name declared only as a class-body attribute one indent level in (e.g. inside a `class Config:` body) resolves to zero errors — the accepted residual gap.

  Every fixture card must place the resolvable-or-not token in a `Requirements:` backtick, with a resolvable-token fixture's declaring file absent from the card's own `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:` (mirroring the existing `test_check_context_completeness_symbol_dirty_missing` fixture shape) so a real match would actually surface as an error rather than being suppressed by the card's own-refs exemption.
- **Commit:** `test(plan-validate): declaration-form matching coverage for .go/.cs/.py/.ts`

### Card 4: Qualifier disambiguation tests

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add new `test_check_context_completeness_symbol_*` functions covering:

  1. A dotted token (e.g. `loomengine.ConfigTemplate`) whose bare trailing segment (`ConfigTemplate`) is declared identically in two fixture files, exactly one of which declares the matching Go `package loomengine` line — resolves to exactly one error naming that one file (the package-qualified match), not zero (today's ambiguous-skip behavior).
  2. The same shape for C#/TS: a dotted token whose bare trailing segment is declared in two fixture files, exactly one of which has a matching `namespace` line (including a multi-segment namespace, e.g. `namespace Foo.Bar.Baz` matching qualifier `Baz`) — resolves to the matching file.
  3. Directory-basename fallback: a dotted token whose bare trailing segment is declared in two fixture files, NEITHER of which has any `package`/`namespace` line, but exactly one of whose containing directory's basename (case-insensitive) matches the qualifier — resolves to that one file.
  4. Still-ambiguous cases are unchanged: a dotted token whose qualifier matches zero of the candidate files (by package/namespace or directory-basename) resolves to zero errors; a dotted token whose qualifier matches more than one candidate (e.g. two files under differently-cased but identically-named qualifier directories) also resolves to zero errors.
  5. Cache-correctness regression: within a single `_plan_validate.run()` call, two DIFFERENT dotted tokens sharing the same bare trailing segment but different qualifiers (e.g. `reedengine.New` in one card's `Requirements:` and `otherpkg.New` in another card's, against a fixture with two files — one declaring `package reedengine`, the other `package otherpkg`, both declaring a `New` symbol) each resolve to their OWN qualifier's file, not both resolving to whichever qualifier was filtered first — confirms qualifier filtering is applied fresh on every lookup rather than baked into the cached result.
- **Commit:** `test(plan-validate): qualifier disambiguation coverage`

### Card 5: Solution-scope pruning tests

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add new `test_check_context_completeness_symbol_*` functions covering:

  1. For each of the four out-of-scope directory-name markers (`Deprecated`, `legacy`, `Obsolete`, `ARCHIVE` — names mentioned, not read, here; vary the casing across the four to confirm the case-insensitive match), a token declared (genuine top-level declaration form) ONLY inside a fixture file under a directory with that basename resolves to zero `context-completeness` errors, even though the declaration itself is syntactically real.
  2. A token declared both inside such a directory AND in a second fixture file outside it still resolves to exactly one error naming the OUTSIDE file — confirms pruning removes the in-scope-tree candidate from the match set entirely rather than merely deprioritizing it, so the outside file is the sole survivor (not an ambiguous two-match skip).
- **Commit:** `test(plan-validate): solution-scope directory pruning coverage`

### Card 6: Characterization tests, one per source issue

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add one minimal-fixture `test_check_context_completeness_symbol_*` function per source GitHub issue, reproducing that issue's reported scenario closely enough to serve as a named regression guard (function name should reference the issue number, e.g. `test_check_context_completeness_symbol_issue_1037_qualified_disambiguation`):

  - **#1037:** a package-qualified reference (bare trailing segment declared in 10+ — or, for a minimal fixture, at least 3 — packages, exactly one matching the qualifier) resolves to the qualified file, not zero errors.
  - **#1033:** a snake_case token (e.g. `status_file`) whose only repo occurrence is inside a Go struct tag string literal (e.g. `` `json:"status_file"` ``), and a separate PascalCase token (e.g. `SessionStart`) whose only occurrence is inside an ordinary string literal — both resolve to zero errors.
  - **#1030:** a bare property-shaped token declared only inside a fixture file under a `Deprecated`-named directory (name mentioned, not read, here) resolves to zero errors, even when the card's own `Creates:` declares a same-named property on a brand-new type (mirrors the original repro's C#-flavored scenario; the fixture may use `.cs` or `.go` — pick whichever keeps the fixture minimal).
  - **#1023:** a capitalized token whose only occurrence is as the first word of a `//` line comment resolves to zero errors.
  - **#1015:** a token whose only occurrences across the fixture project are usage/field-access sites (never a declaration) resolves to zero errors — confirms an external-module-style or struct-field-selector-style reference with no in-repo declaration is never flagged.
  - **#1008:** a token shared between two fixture files — one where the card's own `Creates:` declares a new type on that file, the other an unrelated file where the same token name happens to appear only as a non-declaration usage — resolves to zero errors (the card's own new symbol is not incorrectly flagged against the coincidental unrelated usage).

  Each function's docstring should name the source issue number and one sentence summarizing what regressed.
- **Commit:** `test(plan-validate): characterization tests for issues #1008/#1015/#1023/#1030/#1033/#1037`

## Batch Tests

`verify:` runs the full `plugins/mill/unit_tests/test-plan-validate.py` suite (same command as batch `resolve-symbol-engine`, for the same reason: it is the one test file for the one module this plan touches, and it now includes every test this batch adds alongside every pre-existing test — confirming both that the new coverage passes and that nothing pre-existing regressed).
