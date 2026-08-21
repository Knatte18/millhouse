# Batch: validator-checks-lang-gitignore

```yaml
task: "mill-plan SKILL.md: Phase Plan Review gate, convergence, and DAG-validation correctness bugs"
batch: validator-checks-lang-gitignore
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch fixes the script/test side of the three remaining validator-check issues (#887, #881,
#868) — every card here touches only `_plan_validate.py` and `test-plan-validate.py`, deliberately
excluding `mill-plan/SKILL.md` (the two small fix-table row edits #887 and #868 also need live in
Batch 3 instead). This split exists purely to satisfy the `batch-oversized` context-token cap: all
three cards together touching `_plan_validate.py` + `test-plan-validate.py` +
`mill-plan/SKILL.md` estimate to ~133528 tokens (cap 120000) — dropping `mill-plan/SKILL.md` from
this batch brings it to ~104934 tokens, comfortably under cap, while `mill-plan/SKILL.md`-only work
moves to Batch 3 (~21170 tokens). This batch is a root batch (no dependencies) — it shares no file
with Batch 1, so it can run in parallel with it; Batch 3 depends on both. `verify:` runs
`test-plan-validate.py` only (not the full 77-file suite) — scoped to the one file this batch's new
and modified tests live in.

## Cards

### Card 8: #887 — new check: cross-batch Creates: reference requires a depends-on edge

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `_compute_transitive_ancestors` (used below) is defined locally inside `_plan_validate.py` itself
  (not imported from `_plan_dag.py`) — no need to read `_plan_dag.py`'s source; the exact usage
  pattern is already visible in this same file's `_check_parallel_modifies_overlap`.

  In `plugins/mill/scripts/_plan_validate.py`, add a new module-level function
  `_check_cross_batch_creates_no_depends_on(batch_files: list[Path], overview_text: str) ->
  list[dict]`, placed immediately after `_check_parallel_modifies_overlap`'s own function body ends
  (i.e., directly following that function, before the next check function in the file). Structure it
  by closely mirroring `_check_parallel_modifies_overlap`'s own existing shape (same file, same
  parameters, same `extract_batch_index`/`PlanDAGError` guard):
  1. `try: batches = extract_batch_index(overview_text) except PlanDAGError: return []` — same
     early-return-on-parse-error guard `_check_parallel_modifies_overlap` already uses (check 4 has
     already recorded the parse error; don't double-report).
  2. `ancestors = _compute_transitive_ancestors(batches)` — reuse this existing function verbatim,
     do not reimplement.
  3. Build `stem_to_path: dict[str, Path] = {bf.stem: bf for bf in batch_files}` and
     `batch_name_to_path: dict[str, Path] = {}`, populated by iterating `batches` and mapping each
     `entry["name"]` to its file via `Path(entry.get("file", "")).stem` looked up in `stem_to_path` —
     copy this exact construction from `_check_parallel_modifies_overlap`'s own `batch_name_to_path`
     block (both `ancestors` and `batch_creates`/context-edits below must share this SAME
     `entry["name"]`-keyed space, not file stems, since `_compute_transitive_ancestors` returns a
     dict keyed by `entry["name"]`).
  4. Build `batch_creates: dict[str, set[str]] = {name: _parse_creates_only(path) for name, path in
     batch_name_to_path.items()}` (reuse the already-present `_parse_creates_only` helper).
  5. Build `batch_context_edits: dict[str, set[str]] = {name: _parse_context_only(path) |
     _parse_edits_only(path) for name, path in batch_name_to_path.items()}` (reuse the already-present
     `_parse_context_only` / `_parse_edits_only` helpers — deliberately Context:+Edits: ONLY, never
     Creates:, so a batch's own `Creates:` tokens are never scanned against other batches' `creates`
     sets).
  6. For each `(name_b, tokens)` in `batch_context_edits.items()`: for each `token` in `tokens`
     (skip when `token.lower() == "none"`): for each `(name_c, creates)` in `batch_creates.items()`
     where `name_c != name_b`: if `token in creates` and `name_c not in ancestors.get(name_b,
     set())`, append one error dict `{"check": "cross-batch-creates-no-depends-on", "batch":
     batch_name_to_path[name_b].stem, "card": None, "path": token, "message": f"'{token}' is created
     by batch '{name_c}' but batch '{name_b}' (file {batch_name_to_path[name_b].name}) has no
     depends-on edge to '{name_c}'"}` and `break` out of the innermost loop (stop after the first
     matching creator for this token — defensive against the pathological case of two batches both
     declaring the same `Creates:` target, which is a separate, pre-existing structural error other
     checks already catch).
  7. Return the collected `errors: list[dict]`.

  Give the function a docstring in the same style as `_check_parallel_modifies_overlap`'s neighbors
  (one-line summary, `Error dict shape: {check, batch, card, path, message}.` line, brief Args/Returns
  matching the existing convention in this file).

  Wire the new check into `run()`: add `errors.extend(_check_cross_batch_creates_no_depends_on(
  batch_files, overview_text))` immediately after the existing line
  `errors.extend(_check_parallel_modifies_overlap(batch_files, overview_text))`.

  Update `run()`'s own docstring — the sentence "Checks 1, 2, 3, 4, 5, 6, 8 from issue #10, plus
  wiki-config-mutation, plugin-manifest-context-missing, verify-not-isolated, verify-full-suite,
  verify-malformed-cwd, verify-mixed-cwd, verify-unrelated-test-file, out-of-worktree-target,
  batch-oversized, commit-none-with-content, and five Move-specific checks (move-format,
  move-redundant, move-source-missing, move-target-collision, move-mechanic-missing)." — append
  ", and cross-batch-creates-no-depends-on" immediately before the final period. (The corresponding
  Step 1.5 fix-table row for this new check name is added in Batch 3, not here — kept out of this
  batch to stay under the batch-context-token cap; see Batch 3's own card.)

  In `plugins/mill/unit_tests/test-plan-validate.py`, add three new test functions immediately after
  `test_check_parallel_modifies_overlap_dirty` (following that pair's exact fixture-construction
  style — `_make_overview`, `_make_batch_file`, `_write_plan`, `_plan_validate.run`, filtering
  `result` by `e["check"] == "cross-batch-creates-no-depends-on"`):
  1. `test_check_cross_batch_creates_no_depends_on_clean` — batch `alpha` creates
     `shared/new_file.py`; batch `beta` depends-on `["alpha"]` and its `Context:` (or `Edits:`)
     references `shared/new_file.py` → assert zero findings for this check.
  2. `test_check_cross_batch_creates_no_depends_on_dirty` — same as above but `beta`'s `depends-on`
     is `[]` (missing the edge to `alpha`) → assert exactly one finding, `path == "shared/new_file.py"`,
     and the message mentions both `alpha` and `beta`.
  3. `test_check_cross_batch_creates_no_depends_on_transitive_clean` — three batches: `alpha`
     creates `shared/new_file.py`; `beta` depends-on `["alpha"]` (no reference to the file itself);
     `gamma` depends-on `["beta"]` and references `shared/new_file.py` in `Context:` → assert zero
     findings (transitive ancestry via `beta` is honored, matching `_compute_transitive_ancestors`'
     BFS semantics).

  Update this test file's module docstring's "Check coverage:" list to add a line:
  `  cross-batch-creates-no-depends-on (#887) — Context:/Edits: reference to a file another batch
  creates, with no depends-on edge to that creating batch`.

  In `plugins/mill/scripts/_plan_validate.py`'s own module-level docstring (top of file, the
  "Checks performed (check keys):" list), add a new line immediately after the existing
  `commit-none-with-content` entry (matching that entry's existing indentation/wrapping style):
  `    cross-batch-creates-no-depends-on — a card's Context:/Edits: references a file another batch's
  Creates: produces, with no depends-on edge (direct or transitive) from the referencing batch to the
  creating batch`.

  Add all three new function names (`test_check_cross_batch_creates_no_depends_on_clean`,
  `test_check_cross_batch_creates_no_depends_on_dirty`,
  `test_check_cross_batch_creates_no_depends_on_transitive_clean`) to the `tests = [...]` list
  inside `main()` (near line ~6436), placed near the existing `test_check_parallel_modifies_overlap_*`
  entries in that list, so `run-all.py --only test-plan-validate.py` actually exercises them —
  `main()` has no dynamic test discovery; a function defined in the file but not listed there is dead
  code that never runs.
- **Commit:** `feat(plan-validate): add cross-batch-creates-no-depends-on check`

### Card 9: #881 — language-aware unbounded-verify guard

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_plan_validate.py`, extract the inline Python-project-detection block
  currently living inside `_check_verify_not_isolated` (the four-line `is_python_project = (...)`
  assignment, its four `.exists()` OR-clauses checking `pyproject.toml`, `setup.py`, `setup.cfg`, and
  the nested plugins-mill pyproject marker, together with its preceding one-line comment) into a new
  module-level function `_is_python_project(project_root: Path) -> bool`, placed immediately before
  `_check_verify_not_isolated`'s own `def` line. The extracted function's body is the same four-clause
  boolean OR expression, returned directly — preserve the exact four markers unchanged, in the same
  order, since the fourth (the nested plugins-mill marker) is load-bearing for this very self-hosted
  repo (it has no root-level `pyproject.toml`/`setup.py`/`setup.cfg` and is detected as Python solely
  via that nested marker). Give it a one-line docstring: "Return whether `project_root` looks like a
  Python project (root-level pyproject.toml/setup.py/setup.cfg, OR a nested plugins/mill/pyproject.toml
  marker for this repo's own dogfood layout)." Update `_check_verify_not_isolated`'s own body to
  replace its inline four-line assignment with `is_python_project = _is_python_project(project_root)`,
  keeping its own preceding comment line ("Python-project detection is a one-time lookup shared
  across every batch and the overview...") — reword it to note the detection now lives in the shared
  `_is_python_project` helper.

  In `_check_verify_full_suite`, widen its existing `_check_frontmatter` inner function beyond the
  current single `if "run-all.py" in command and "-k " not in command and "--only " not in command:`
  branch. Replace that one `if` with a sequence of independent checks (any one matching returns a
  finding; keep the existing run-all.py branch's exact condition and message text unchanged as the
  first check in the sequence):
  1. **Unchanged (Python/mill, `run-all.py`):** `"run-all.py" in command and "-k " not in command and
     "--only " not in command` → existing message text, unchanged.
  2. **New (Go):** `re.search(r"\bgo test\b.*\./\.\.\.", command)` (a `go test` invocation targeting
     the recursive `./...` wildcard) `and "-run " not in command` → return `{"check":
     "verify-full-suite", "batch": batch_label, "card": None, "path": command, "message": "verify
     command invokes 'go test ./...' without a -run <pattern> filter; scope it or document the
     cross-cutting-helper justification in ## Batch Tests"}`.
  3. **New (C#/.NET):** `"dotnet test" in command and "--filter" not in command` → return `{"check":
     "verify-full-suite", "batch": batch_label, "card": None, "path": command, "message": "verify
     command invokes 'dotnet test' without a --filter; scope it or document the cross-cutting-helper
     justification in ## Batch Tests"}`.
  4. **New (Python, bare pytest — only when `_is_python_project(project_root)` is `True`):**
     `re.fullmatch(r"(python -m )?pytest", command.strip())` (the command is exactly `pytest` or
     `python -m pytest`, with no path/pattern arguments at all — deliberately conservative, so a
     scoped invocation like `pytest tests/test_foo.py` or `pytest -k foo` never matches) → return
     `{"check": "verify-full-suite", "batch": batch_label, "card": None, "path": command, "message":
     "verify command invokes bare pytest with no path or -k filter; scope it or document the
     cross-cutting-helper justification in ## Batch Tests"}`.

  Evaluate checks 1-3 unconditionally (they key off distinct command substrings — `run-all.py`,
  `go test ./...`, `dotnet test` — that do not collide across languages) and check 4 only when
  `_is_python_project(project_root)` is `True` (computed once per `_check_verify_full_suite` call,
  same one-time-lookup pattern `_check_verify_not_isolated` already uses, not once per batch). Return
  the first matching check's finding (do not emit more than one finding per command). Keep the
  function's existing per-batch and overview-level iteration structure (the two `for`/`if` blocks
  after `_check_frontmatter`'s definition) completely unchanged — only `_check_frontmatter`'s body
  widens.

  Do NOT change the check's name (`"verify-full-suite"`, unchanged across all four branches above) or
  touch `mill-plan/SKILL.md`'s existing `verify-full-suite` fix-table row or skip-check escape hatch —
  per this task's discussion.md Decision, only the detection widens; the remedy/skip-check contract is
  unchanged and already covers the new languages verbatim (scope the command, or document the
  cross-cutting-helper justification and re-run with `--skip-check verify-full-suite`).

  Update `_check_verify_full_suite`'s own one-line docstring summary — currently "Flag verify:
  commands that invoke run-all.py without a scoping filter." — to: "Flag verify: commands that invoke
  an unscoped full-suite runner: run-all.py without -k/--only (Python/mill), go test ./... without
  -run (Go), dotnet test without --filter (C#), or bare pytest/python -m pytest with no path or -k
  filter (Python, non-mill)."

  In `plugins/mill/unit_tests/test-plan-validate.py`, extend whatever existing test function(s) cover
  `verify-full-suite` (search the file for `verify_full_suite` or `verify-full-suite` to locate them)
  with new fixture cases for each new language heuristic (Go `go test ./...` with and without
  `-run`; C# `dotnet test <project>` with and without `--filter`; Python bare `pytest`/`python -m
  pytest` with and without `-k <pattern>` or an explicit path argument) — mirror the existing
  Python/`run-all.py` fixture cases' exact assertion style (filter `result` by `e["check"] ==
  "verify-full-suite"`, assert count and `path`/`message` content). For the Python bare-pytest case,
  the fixture's `project_root` must actually contain a Python marker file (e.g. create an empty
  `pyproject.toml` under the fixture's `project_root`) so `_is_python_project` returns `True` — add a
  short comment noting why the marker file is required. If this extension takes the form of adding new
  sibling test functions (rather than only appending assertions inside the existing function bodies),
  add each new function's name to the `tests = [...]` list inside `main()` (same explicit-registration
  requirement as Card 8 above) — `main()` has no dynamic test discovery.
- **Commit:** `feat(plan-validate): widen verify-full-suite to Go, C#, and bare pytest`

### Card 10: #868 — gitignore-aware Context: refs in the pre-review validator

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `ReviewError` and `resolve_ref_paths` (used below) are defined in the shared review-common helper
  module — no need to read that module's source; its full call shape is given here, mirroring Card
  8's own established precedent in this same batch for `_compute_transitive_ancestors`/`_plan_dag.py`.
  `ReviewError` is a plain exception class (`class ReviewError(Exception)`) raised with no
  meaningful attributes beyond its message.
  `signature: resolve_ref_paths(tokens: list[str], project_root: Path, root: str | None, *,
  wiki_root: Path | None = None, git_root: Path | None = None, soft_fail_gitignored: bool = False)
  -> list[Path]` — raises `ReviewError` when a token resolves to no candidate path that either exists
  on disk or (when `soft_fail_gitignored` is `True`) is confirmed git-ignored via `git check-ignore`;
  otherwise returns the resolved `Path` list. (The review-common helper module is intentionally
  excluded from this batch's `Context:` — adding the full file, at ~30812 estimated tokens, would push this
  batch's total to ~135746, over the `pipeline.max_batch_context_tokens` cap of 120000; the file is
  large enough that no batch containing this card and that file can pass the cap regardless of how
  the batch is split, since this card's own `Edits:` — `_plan_validate.py` and
  `test-plan-validate.py` — already account for ~104934 of the 120000 budget by themselves.)

  In `plugins/mill/scripts/_plan_validate.py`'s `from _review_common import (...)` block (the
  multi-line import near the top of the file, currently listing `_load_root_from_overview`,
  `compute_creates_union`, `compute_deletes_union`, `compute_moves_union`, `parse_batch_refs`,
  `parse_moves`, `resolve_existing_paths`), add two new names to the import list, keeping the
  existing alphabetical-ish ordering convention: `ReviewError` and `resolve_ref_paths`.

  In `_check_non_existent_path`, split its existing single `general_refs = set(raw_refs) -
  deletes_only` loop (the "General refs (Context/Edits/Creates)" loop, the first of the function's
  two `for` loops) into two separate loops — one for `Context:`-only tokens (new gitignore-aware
  soft-fail path), one for `Edits:`/`Creates:`-only tokens (existing hard-fail path, unchanged
  behavior). Concretely:
  1. Compute `context_tokens = _parse_context_only(batch_path)` and
     `edits_creates_tokens = (_parse_edits_only(batch_path) | _parse_creates_only(batch_path)) -
     deletes_only` (both already-present helpers in this same file — reuse, don't reimplement;
     `general_refs` itself, and the `raw_refs`/`deletes_only` variables it was built from, can be
     removed once both new sets replace its two use-sites, or left in place if still needed
     elsewhere in the function — check before removing).
  2. **Edits:/Creates: loop (unchanged behavior):** for each `t` in `edits_creates_tokens` (skip
     `t.lower() == "none"`): call `resolve_existing_paths([t], project_root, root, wiki_root=wiki_root,
     git_root=git_root)` exactly as today; if empty and `t not in creates_union` and `t not in
     deletes_union` and `t not in moves_targets`: append the existing `non-existent-path` error dict,
     unchanged message text.
  3. **Context: loop (new gitignore-aware behavior):** for each `t` in `context_tokens` (skip
     `t.lower() == "none"`): if `t in creates_union` or `t in deletes_union` or `t in moves_targets`:
     `continue` (unchanged suppression, checked up front since `resolve_ref_paths` has no
     `moves_targets` concept of its own). Otherwise, call `resolve_ref_paths([t], project_root, root,
     wiki_root=wiki_root, git_root=git_root, soft_fail_gitignored=True)` wrapped in `try`/`except
     ReviewError:` — on `ReviewError` (the only failure mode `resolve_ref_paths` raises: the path is
     neither on disk nor confirmed git-ignored), append the SAME `non-existent-path` error dict shape
     the Edits:/Creates: loop uses (same four keys, same message text template
     `f"path '{t}' does not exist on disk and is not a Creates: target in any batch"`) for this
     token. On success (no exception — whether because the path resolved on disk, or because
     `resolve_ref_paths` silently soft-skipped a confirmed-gitignored missing path), do nothing —
     no error.

  Leave the function's second loop (the `Deletes:` refs loop, "Deletes refs: missing on disk is
  suppressed only if in creates_union") completely unchanged.

  Update the function's docstring: in the "Suppression rules mirror the move-endpoint-accounting
  Shared Decision" list, add a new bullet: "- `Context:` refs additionally soft-fail when confirmed
  git-ignored (via `resolve_ref_paths(..., soft_fail_gitignored=True)`) — a `Context:`-only reference
  to a not-yet-existing, gitignored runtime artefact (e.g. a build/run-output file an earlier batch
  produces at runtime, under a `.gitignore`d directory) is not flagged, matching the LLM reviewer's
  own existing leniency for `Context:` refs (`_review_plan.py`, #733/#808). `Edits:`/`Creates:`/
  `Deletes:` refs receive NO such leniency — those name files the batch is expected to produce or
  touch, a hard requirement." (The corresponding Step 1.5 fix-table row edit for `non-existent-path`
  is made in Batch 3, not here — kept out of this batch to stay under the batch-context-token cap;
  see Batch 3's own card.)

  In `plugins/mill/unit_tests/test-plan-validate.py`, extend `test_check_non_existent_path_clean` and
  `test_check_non_existent_path_dirty` (or add new sibling test functions immediately after them,
  matching their existing fixture style) to cover three new scenarios: (a) a missing `Context:` ref
  under a path confirmed git-ignored (create a real `.gitignore` file in the fixture's `project_root`
  ignoring the referenced path/directory, and do NOT create the referenced file itself) → assert zero
  `non-existent-path` findings for that token; (b) a missing `Context:` ref NOT covered by any
  `.gitignore` rule → assert the finding still fires (unchanged hard-fail, regression guard); (c) a
  missing `Edits:` (or `Creates:`) ref that IS confirmed git-ignored → assert the finding STILL fires
  (no leniency outside `Context:` — this is the case #868's own fix rationale explicitly excludes).
  Since `resolve_ref_paths`'s gitignore check shells out to real `git check-ignore`, the fixture's
  `project_root` must be a real (even if minimal) git repository — initialize it with
  `_test_helpers.init_minimal_git_repo` (the existing pygit2-based helper in
  `plugins/mill/unit_tests/_test_helpers.py`; add `from _test_helpers import init_minimal_git_repo`
  to this file's own import block if not already present) and commit or stage the `.gitignore` file
  itself (a `.gitignore` rule only takes effect once the repository recognizes the directory as a git
  worktree; an uninitialized directory will make `git check-ignore` fail/no-op, which
  `resolve_ref_paths` already treats as "not confirmed ignored" per its own `except Exception:
  continue` fallback). If this takes the form of adding new sibling test
  functions (rather than only extending the existing two functions' bodies), add each new function's
  name to the `tests = [...]` list inside `main()` (same explicit-registration requirement as Card 8
  above).

  This test file's module docstring (near the top of the file) currently states "no real LLM, no
  real git, no network." Update it to note the one documented exception this card introduces: append
  ", except the one gitignore-fixture case in `test_check_non_existent_path_*` which shells out to
  real `git check-ignore` via `_test_helpers.init_minimal_git_repo`" to that sentence.
- **Commit:** `fix(plan-validate): soft-fail gitignored Context: refs in non-existent-path check`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only
test-plan-validate.py` covers all three cards' new/modified checks and their new test functions —
scoped to the one file every new test in this batch lives in, per this file's "Verify command scope"
rule (not the full 77-file suite).
