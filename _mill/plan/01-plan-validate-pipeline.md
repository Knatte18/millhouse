# Batch: plan-validate-pipeline

```yaml
task: mill-plan/review validation false-positives, hard-fails, and truncated failure reasons
batch: plan-validate-pipeline
number: 1
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch fixes the three bugs that live in mill-plan's pre-implementation pipeline: the `## Cards` field-legend prose in `plugins/mill/templates/plan-batch.md` leaking into rendered batch files and being misparsed as real `Context:`/`Edits:` references (#734); ambiguous `non-existent-path` fix-table wording in `plugins/mill/skills/mill-plan/SKILL.md` plus a missing self-run-the-validator instruction (#727); and a missing validator check that lets a batch's `verify:` command silently skip a Go integration-tagged test file it just added or edited (#724). All three are bundled into one batch because Fix 2 and Fix 3 both add rows to the same SKILL.md fix table, and Fix 1's and Fix 3's regression tests both land in `test-plan-validate.py` — keeping them in one batch avoids an artificial `depends-on` edge that would otherwise be needed purely to satisfy the `parallel-modifies-overlap` check (see the overview's "three independent root batches" Shared Decision). No card in this batch depends on another card's edits landing first — cards 1-2 (template), 3 (SKILL.md wording), 4-5 (new check + its SKILL.md row), and 6 (tests for the new check) touch disjoint regions of their respective files and can be implemented in any order, though the numbering below is a sensible one.

## Cards

### Card 1: Move the Cards field-legend into plan-batch.md's stripped HTML comment

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  The template today has an HTML comment closing with `Strip this HTML comment before writing.\n-->`, followed by rendered content that includes (in order): the `# Batch: <BATCH_NAME>` H1, the yaml frontmatter block, `## Rename mechanic`, `## Batch Scope`, `## Cards`, then — still under `## Cards` and still rendered (not commented) — an intro sentence beginning `_One `### Card N` per card. Cards are logical sub-sections, not files. ... Fields per card:_`, followed by seven field-legend bullets (`- **Context:**`, `- **Edits:**`, `- **Creates:**`, `- **Deletes:**`, `- **Moves:**`, `- **Requirements:**`, `- **Commit:**`, each with its full explanatory sentence(s)), followed by two trailing paragraphs (`Context/Edits/Creates/Deletes/Moves fields contain ONLY backtick-wrapped paths...` and `Note for reviewers: the plan-reviewer bulks...`), and only THEN the literal `### Card N: <short title>` example card block.
  Move the intro sentence + all seven field-legend bullets + both trailing paragraphs (everything currently between the `## Cards` heading and the `### Card N: <short title>` example heading) into the template's existing HTML comment — insert it as new comment content immediately before the comment's closing `Strip this HTML comment before writing.\n-->` line, preserving the moved text verbatim (do not reword any of it). After this edit: `## Cards` (the heading itself) stays outside the comment as rendered content, immediately followed by the (still rendered, unchanged) `### Card N: <short title>` example card block and then `## Batch Tests`. The field-legend prose no longer appears anywhere in the rendered (post-strip) template output.
- **Commit:** `fix(templates): move Cards field-legend into stripped HTML comment (#734)`

### Card 2: Regression test — legend-in-comment is not parsed as batch references

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `test_check_cards_legend_in_comment_not_parsed_as_refs() -> int` to `plugins/mill/unit_tests/test-plan-validate.py`, following this file's existing `def test_<name>() -> int` / PASS-FAIL-print / `_write_plan`+`tempfile.TemporaryDirectory` fixture convention (see e.g. `test_check_non_existent_path_clean`).
  Part 1 (regression guard for the fix): build a batch-file text string whose `## Cards` section places field-legend-style lines OUTSIDE any HTML comment — bare markdown text matching the field-legend shape (e.g. a line `- **Context:** every file the implementer reads but does not change.` with no backtick-wrapped path, immediately followed by other legend-shaped lines mirroring the other six fields) placed directly under a `## Cards` heading, followed by one real, valid `### Card 1: example` block (built via `_make_batch_file` or equivalent inline text with valid backtick-wrapped Context:/Edits:/Creates:/Deletes:/Moves:/Requirements:/Commit: fields). Write it via `_write_plan` into a temp `plan_dir` with a matching `_make_overview` single-batch index, call `_plan_validate.run(plan_dir, project_root, ...)`, and assert this "before-the-fix" shape currently produces at least one finding whose `check` is `reads-not-backtick-path` or `non-existent-path` (the legend text's inline field-label bullets have no backtick-wrapped path, tripping the backtick-format/non-existent-path checks) — this proves the fixture reproduces the original #734 bug.
  Part 2 (the fix itself): build the same batch-file text but with the legend-style lines wrapped inside an HTML comment (`<!-- ... -->`) immediately before the same real `### Card 1: example` block, i.e. the corrected post-fix template shape. Write and validate the same way; assert zero findings with `check` in `{"non-existent-path", "reads-not-backtick-path", "all-files-touched-mismatch", "parallel-modifies-overlap"}` for this batch.
  Both parts belong in the same test function (or two adjacent assertions within it); print `PASS`/`FAIL` and return 0/1 per this file's convention. **Wire the new function into `main()`'s `tests` list**: `main()` only executes functions present in its explicit `tests = [...]` list (currently ending with the `verify-unrelated-test-file` check's five entries) — `run-all.py` gates solely on `main()`'s return code, so a test function that is never added to that list is dead code that silently never runs. Add `test_check_cards_legend_in_comment_not_parsed_as_refs` to the `tests` list.
- **Commit:** `test(plan-validate): regression guard for Cards legend leaking into rendered batch content (#734)`

### Card 3: Reword the non-existent-path fix-table row and add the self-run-validator instruction

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the step 1.5 fix table (`### Phase: Plan Review`, the `| check | mechanical fix |` table), replace the `non-existent-path` row's mechanical-fix cell with this exact text, verbatim:

  "A path declared as a `Creates:` target anywhere in this plan counts as existing for `Context:`/`Edits:` purposes; this row fires only for paths that are neither on disk nor declared as a `Creates:` target anywhere in the plan. If the path is a typo of an existing file, correct it. If it is meant to be a new `Creates:` target that does not yet appear anywhere in the plan, add it as a `Creates:` entry in the appropriate card. If neither applies, the planner intended to read a file that does not exist — halt; this is not mechanically fixable."

  Separately, in the same file, immediately after the existing "**Self-validate the DAG** before committing: ..." sentence (in `### Phase: Plan`, just before the "Update `_mill/status.md`" subsection), add a new sentence/paragraph instructing a self-run of the real validator gate before committing the plan, with the exact call shape:

  `_plan_validate.run(plan_dir, project_root, root=<root read via _load_root_from_overview(plan_dir / "00-overview.md")>, git_root=git_root, wiki_root=wiki_root, skip_checks=frozenset(), parent_branch=<_parent_branch.resolve(status_path, interactive=False), falling back to None on any exception>, max_cards_per_batch=cfg.get("pipeline", {}).get("max_cards_per_batch", 10), max_batch_context_tokens=cfg.get("pipeline", {}).get("max_batch_context_tokens", 120000))`

  State that this mirrors `millpy-review-plan.py`'s own step-1.5 gate exactly (same seven keyword arguments: `root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens` — the real gate passes `skip_checks=frozenset(args.skip_checks)`; the self-run has no CLI args to source a skip-list from, so it passes `skip_checks=frozenset()` explicitly, which is also `_plan_validate.run`'s own default), that `git_root`/`wiki_path` are already bound at mill-plan's Entry step so no new resolution work is needed, and that this self-run instruction has no "or invoke the standalone CLI" fallback — do not add one.
- **Commit:** `fix(mill-plan): clarify non-existent-path fix-table wording, add self-run validator instruction (#727)`

### Card 4: Add the verify-excludes-edited-tagged-test validator check

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new function `_check_verify_excludes_edited_tagged_test(batch_files: list[Path], project_root: Path, root: str | None, *, wiki_root: Path | None = None, git_root: Path | None = None) -> list[dict]` to `_plan_validate.py`, placed near `_check_verify_not_isolated` (whose project-marker-detection-once and malformed-mapping-silent-skip pattern it mirrors). This function MUST accept and thread `root`/`wiki_root`/`git_root` exactly like its sibling checks that resolve paths (e.g. `_check_non_existent_path`, `_check_move_source_missing`, `_check_batch_oversized`) — a Go project using a nested layout (`root` set, or `git_root != project_root`) must resolve `_test.go` tokens the same way every other check does, or the check silently no-ops for exactly the layouts it most needs to cover. Logic:
  1. One-time Go-project detection: `(project_root / "go.mod").exists()`. If False, return `[]` immediately (fail-open — non-Go projects are never checked, exactly like `_check_verify_not_isolated`'s `is_python_project` gate).
  2. For each batch file: collect its `Edits:`-only tokens ending in `_test.go`, via the existing `_parse_edits_only(batch_path)` helper filtered to `.endswith("_test.go")`. Do NOT include `Creates:` tokens — this step-2 collection is the sole reason scenario (h) in Card 6 produces zero findings for a `Creates:`-only integration-tagged file: since the token is never collected here, step 3's `resolve_existing_paths` call is never even made on it (a `Creates:` target does not exist on disk at plan-validation time by this codebase's own established convention, so including it would be pointless anyway). This is an accepted, documented limitation, not a bug.
  3. For each such token, resolve it via `resolve_existing_paths([token], project_root, root, wiki_root=wiki_root, git_root=git_root)` (already imported into this module's namespace from `_review_common`; note the function's own `root`/`wiki_root`/`git_root` parameters are threaded in here, NOT hardcoded `None`) and skip tokens that don't resolve to an on-disk file. For each resolved file, read its text and scan lines from the top: skip blank lines and lines starting with `//`; the first line that is neither blank nor a `//`-comment (e.g. `package foo`, `/*`) ends the scan. Bound the scan to the first 40 lines of the file (a safety net — an Apache-2.0 header is ~15 lines, a BSD-3-Clause header ~25-27 lines, so 40 gives headroom above real-world license-header lengths without being unbounded). If any scanned line matches `^//go:build` and its constraint expression (the rest of the line) contains the word `integration`, the file is "integration-tagged."
  4. If the batch has at least one integration-tagged file among its collected tokens: parse the batch's `verify:` command via `_plan_dag.parse_verify_field(frontmatter, project_root, project_root)` (same pattern as `_check_verify_not_isolated`; malformed mapping raises `ValueError` — catch it and skip this batch, since `_check_verify_malformed_cwd` is the sole reporter for that). If `command` is `None`, skip. Check whether `command` contains a `-tags` flag whose value includes the literal token `integration` — match `-tags` or `-tags=` followed by a value, split the value on `,`/whitespace, check for `"integration"` as one of the resulting tokens (so `-tags integration`, `-tags=integration`, and `-tags "integration,other"` all count; `-tags integrationtest` does not).
  5. If the batch has an integration-tagged `_test.go` file among its `Edits:` but the verify command lacks that `-tags ...integration...` flag (or has no `-tags` flag at all, or `command is None`), append one error dict `{"check": "verify-excludes-edited-tagged-test", "batch": batch_path.stem, "card": None, "path": <the tagged file's raw token>, "message": <describe the batch, the tagged file, and the missing -tags flag>}`.
  Register the new check in `run()` alongside the other `errors.extend(...)` calls, threading the SAME `effective_root`/`git_root`/`wiki_root` values `run()` already computes and passes to sibling checks like `_check_non_existent_path`/`_check_batch_oversized`: `errors.extend(_check_verify_excludes_edited_tagged_test(batch_files, project_root, effective_root, wiki_root=wiki_root, git_root=git_root))`.
  Update the module's top-of-file docstring (the "Checks performed (check keys):" list, currently lines 13-46) to add a `verify-excludes-edited-tagged-test` entry describing it as: Go-specific (gated on `go.mod` presence), flags a batch whose `Edits:`-only `_test.go` files include a `//go:build ...integration...`-tagged file when the batch's `verify:` command lacks a matching `-tags ...integration...` flag.
- **Commit:** `feat(plan-validate): add verify-excludes-edited-tagged-test check for Go integration-tagged tests (#724)`

### Card 5: Add the verify-excludes-edited-tagged-test fix-table row

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the same step 1.5 fix table edited by Card 3, add one new row (place it immediately after the `verify-unrelated-test-file` row, since both concern a batch's `verify:` command), with this exact mechanical-fix text:

  "Open the offending batch's verify: command (payload's batch/path fields name the batch and the tagged test file). If a -tags flag already exists, append ,integration to its value; otherwise append \" -tags integration\" to the command."

  Use `verify-excludes-edited-tagged-test` as the row's check-key cell, matching the check key registered in Card 4.
- **Commit:** `docs(mill-plan): add fix-table row for verify-excludes-edited-tagged-test (#724)`

### Card 6: Tests for verify-excludes-edited-tagged-test

- **Context:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add one `def test_<name>() -> int` function per scenario below to `plugins/mill/unit_tests/test-plan-validate.py`, following this file's existing convention (one function per scenario, `tempfile.TemporaryDirectory`, PASS/FAIL print + 0/1 return). Each scenario needs a real `go.mod` file written at the fixture's `project_root` (when the scenario is Go-project) and a real `_test.go` file written at the token's path under `project_root` with caller-controlled leading content (write these directly via `Path.write_text` with `.parent.mkdir(parents=True, exist_ok=True)` — no git needed, `resolve_existing_paths` only checks disk existence). Use `_make_verify_only_batch_text` (already in this file) to control the batch's exact `verify:` command string, and `edits=[...]` to place the `_test.go` token in the batch's `Edits:` field.
  Scenarios:
  (a) Go project (`go.mod` present), batch's `Edits:` includes a `_test.go` file whose content starts with `//go:build integration\n\npackage foo\n`, `verify:` has no `-tags` flag → exactly one `verify-excludes-edited-tagged-test` finding naming the batch and the file.
  (b) Same fixture, `verify:` includes `-tags integration` → zero findings for this check.
  (c) Same fixture, `verify:` includes `-tags integration,other` → zero findings (tests comma-split token matching).
  (d) Go project, batch edits a `_test.go` file with NO `//go:build` line at all (plain `package foo\n...`) → zero findings.
  (e) NOT a Go project (no `go.mod` at `project_root`), otherwise identical to scenario (a)'s dirty fixture → zero findings (tests the language gate is fail-open).
  (f) Go project, batch's `verify:` frontmatter is a malformed `{cwd, command}` mapping (missing `command` key or invalid `cwd` value) → zero findings from this check, no crash/exception propagates out of `_plan_validate.run()`.
  (g) Go project, the integration-tagged `_test.go` file's `//go:build integration` line is preceded by several leading `//`-comment lines (e.g. a 5-10 line copyright/license header) before the build-constraint line, `verify:` has no `-tags integration` → finding still raised (regression guard for the header-comment scan — a first-line-only check would false-negative this).
  (h) Go project, the ONLY reference to an integration-tagged `_test.go` file is via that card's `Creates:` (not `Edits:`) — the file does not exist on disk — `verify:` has no `-tags integration` → zero findings (documents the accepted `Creates:`-coverage limitation from Card 4 step 2/3 explicitly, rather than leaving it an implicit silent gap).
  **Wire all eight new functions into `main()`'s `tests` list** (same requirement as Card 2 — `run-all.py` only executes what `main()`'s `tests` list enumerates; add all eight function names to that list or they never run).
- **Commit:** `test(plan-validate): cover verify-excludes-edited-tagged-test scenarios (#724)`

## Batch Tests

`verify:` runs `run-all.py --only test-plan-validate.py`, covering both the Fix 1 regression guard (Card 2) and all eight Fix 3 scenarios (Card 6) in the same file already covering `_plan_validate.py`'s other checks. Fix 2 (Card 3, Card 5) is a doc-only change with no runnable surface — verified by the reviewer reading the rendered SKILL.md diff, not by this batch's automated verify.
