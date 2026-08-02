# Batch: fix-plan-validate-false-positives

```yaml
task: _plan_validate false positives block plan authoring
batch: fix-plan-validate-false-positives
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch fixes both over-eager `_plan_validate.py` checks named in
`_mill/discussion.md` (`context-completeness` and
`requirements-quote-indent-drift`) and adds regression coverage for all
six source GitHub issues (#766, #760, #756, #750, #761, #754) in one
pass, since both fixes land in the same file pair (`_plan_validate.py`
+ its `test-plan-validate.py` companion) and neither depends on the
other's code path. There is no external interface for a later batch to
consume — this is the only batch in the plan.

## Cards

### Card 1: directory-vs-file resolvability in context-completeness

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Replace the `resolvable` computation inside `_check_context_completeness`'s
  `for token in backtick_re.findall(line):` loop (function starts at the
  `def _check_context_completeness(` line) so a resolved-but-directory
  token can never satisfy `resolvable`. `Context:` is documented as a
  list of *files* the implementer reads, so a directory can never
  legitimately belong there — it can never be "missing" from it either.

  Insert one new line (`existing_files = [p for p in existing if
  p.is_file()]`) between the existing `existing = resolve_existing_paths(...)`
  call and the existing `resolvable = (...)` block, and change
  `resolvable`'s first disjunct from `bool(existing)` to
  `bool(existing_files)`. No other line in `_check_context_completeness`
  changes.

  Old:
```python
                    existing = resolve_existing_paths(
                        [stripped_token], project_root, root,
                        wiki_root=wiki_root, git_root=git_root,
                    )
                    resolvable = (
                        bool(existing)
                        or stripped_token in creates_union
                        or stripped_token in deletes_union
                        or stripped_token in moves_targets
                    )
```
  New:
```python
                    existing = resolve_existing_paths(
                        [stripped_token], project_root, root,
                        wiki_root=wiki_root, git_root=git_root,
                    )
                    existing_files = [p for p in existing if p.is_file()]
                    resolvable = (
                        bool(existing_files)
                        or stripped_token in creates_union
                        or stripped_token in deletes_union
                        or stripped_token in moves_targets
                    )
```

  `resolve_existing_paths` (`plugins/mill/scripts/_review_common.py:963`)
  stays untouched — it is existence-based (files and directories both
  count as "existing") for its other callers; only this check's own
  resolvability test changes. Do not add directory-shape filtering to
  the `stripped_token in creates_union` / `deletes_union` /
  `moves_targets` membership checks below — those three sets are
  plan-declared file targets by convention and are out of scope for
  this fix.
- **Commit:** `fix(plan-validate): treat directories as unresolvable in context-completeness`

### Card 2: strip closing-fence trailing whitespace in quote-indent-drift

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_check_requirements_quote_indent_drift`, normalize each extracted
  `fence_body` immediately after it is bound by the `for fence_idx,
  fence_body in enumerate(fence_bodies, start=1):` loop, before the
  existing "already byte-exact" check runs. `_RE_FENCE_BODY` (module
  constant, `` re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL) ``) is not
  line-anchored, so it always captures the closing fence delimiter's
  own leading whitespace (0+ spaces of Markdown list-continuation
  indentation) as a trailing fragment of the captured body — that
  fragment is markdown structure, never real quoted content, and both
  the byte-exact pre-check and the `N`-strip search loop must operate
  on the normalized value.

  Insert one new line as the first statement inside the
  `for fence_idx, fence_body in enumerate(fence_bodies, start=1):` loop
  body, reassigning `fence_body`:
  ```python
  fence_body = re.sub(r"\n[ \t]*\Z", "", fence_body)
  ```

  Old:
```python
            for fence_idx, fence_body in enumerate(fence_bodies, start=1):
                # Already byte-exact -- nothing to flag. This also correctly
                # no-ops for a fence with zero leading whitespace, since
                # every N >= 1 strip on such a fence is a no-op that reduces
                # to this same already-checked raw content.
                if any(
```
  New:
```python
            for fence_idx, fence_body in enumerate(fence_bodies, start=1):
                fence_body = re.sub(r"\n[ \t]*\Z", "", fence_body)
                # Already byte-exact -- nothing to flag. This also correctly
                # no-ops for a fence with zero leading whitespace, since
                # every N >= 1 strip on such a fence is a no-op that reduces
                # to this same already-checked raw content.
                if any(
```

  No other line in `_check_requirements_quote_indent_drift` changes —
  `_RE_FENCE_BODY` itself is not re-anchored, and
  `_strip_n_leading_spaces` (unaffected, consumes whatever string it is
  given) is not touched.
- **Commit:** `fix(plan-validate): strip closing-fence trailing whitespace from quote-indent-drift fence bodies`

### Card 3: regression tests for both false-positive fixes

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add five new test functions to `test-plan-validate.py`, following the
  file's existing per-check test conventions (`tempfile.TemporaryDirectory`
  fixture, `_make_overview`/`_make_batch_file`/`_write_plan` helpers,
  `_plan_validate.run(plan_dir, project_root)`, filter `result` by
  `e["check"] == ...`, assert + PASS/FAIL print + return 0/1, matching
  every existing test in this file byte-for-byte in structural shape).

  Insert the first three functions directly after
  `test_check_context_completeness_dirty_line_range_suffix_missing` and
  before `test_check_requirements_quote_indent_drift_clean_exact_match`:

```python
def test_check_context_completeness_clean_directory_reference() -> int:
    """Directory-only backtick token that exists on disk as a directory (no file of that name) -> clean, no finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "internal" / "gitrepo").mkdir(parents=True)
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  See `internal/gitrepo` for the existing repo-handling conventions.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_directory_reference")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_directory_reference: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_directory_reference_not_on_disk() -> int:
    """Same directory-shaped token, nothing exists at that path on disk -> also clean (deterministic regardless of on-disk state)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  See `internal/gitrepo` for the existing repo-handling conventions.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_directory_reference_not_on_disk")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_clean_directory_reference_not_on_disk: {exc}",
                file=sys.stderr,
            )
            return 1
```

  Then add a third function, `test_check_context_completeness_clean_double_slash_token`,
  mirroring `test_check_context_completeness_clean_directory_reference`'s
  structure exactly (same imports/helpers already in scope, same
  `tempfile.TemporaryDirectory` fixture shape, same `try`/`assert`/PASS/FAIL
  return-0/1 shape) with these differences: no `internal/gitrepo` directory
  is created under `project_root` (only `project_root/src/a.py`, as in
  `test_check_context_completeness_clean_directory_reference_not_on_disk`);
  the batch's `requirements=` value is a one-line sentence naming the
  root-path token — a single pair of backtick delimiters wrapping exactly
  two consecutive forward-slash characters, in the same "See &lt;token&gt;
  for ..." phrasing used by the two prior functions' fixtures; the
  docstring's own summary sentence names the same token the same way. (This
  card's own Requirements: prose deliberately does not spell that token out
  literally here, backtick-wrapped, in this plan file — doing so would trip
  this very check, described in Card 1, against `_plan_validate.py`'s
  CURRENT unfixed behavior at self-validation time, since that token always
  resolves to the filesystem root and so always "exists".) Assert 0
  `context-completeness` errors, and use the function name
  `test_check_context_completeness_clean_double_slash_token` with a PASS/FAIL
  message matching that name, exactly as every other function in this file
  does.

  Insert the remaining two functions directly after
  `test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break`
  and before the `# skip_checks filtering (Card 7 / #188)` section
  comment:

```python
def test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer() -> int:
    """Mid-line fragment quote, fence at zero indent, closer also zero indent -> clean (#761: previously reported a spurious N=1 via _strip_n_leading_spaces's splitlines() side effect of dropping the fence's own trailing newline)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "value = compute(x, y) + offset\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "```\n"
                "compute(x, y)\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer() -> int:
    """Byte-exact quoted content, closing fence carries list-continuation indentation -> clean (#754: previously fell through to the N-search and matched via incidental adjacent-content coincidence instead of the byte-exact pre-check)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "alpha\nbeta\ngamma\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "```\n"
                "beta\n"
                "gamma\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer: {exc}",
                file=sys.stderr,
            )
            return 1
```

  Finally, register all five new function names in `main()`'s `tests =
  [...]` list: add `test_check_context_completeness_clean_directory_reference,`,
  `test_check_context_completeness_clean_directory_reference_not_on_disk,`,
  and `test_check_context_completeness_clean_double_slash_token,`
  directly after the existing
  `test_check_context_completeness_dirty_line_range_suffix_missing,`
  line; add
  `test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer,`
  and
  `test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer,`
  directly after the existing
  `test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break,`
  line, before the `# skip_checks filtering (Card 7 / #188)` comment.
- **Commit:** `test(plan-validate): add regression tests for context-completeness and quote-indent-drift false positives`

## Batch Tests

`verify:` runs the full `test-plan-validate.py` file (unbounded within
that single file, not `run-all.py`), because Cards 1 and 2 edit two
different checks inside the same shared `_plan_validate.py` module and
the full file's existing suite (context-completeness, quote-indent-drift,
and every other check in the file) is the correct regression scope to
confirm neither fix regresses an existing true-positive/true-negative
case. Card 3 adds five new tests to this same file, so a single run
covers old + new coverage together. This does not touch `run-all.py` or
any other test file in `plugins/mill/unit_tests/`, so scoping to this
one file (rather than the repo-wide `run-all.py`) is correct per the
per-batch verify-scoping convention.
