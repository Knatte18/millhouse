# Batch: validator-checks

```yaml
task: '_plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps'
batch: 'validator-checks'
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

All three behavioural changes to `plugins/mill/scripts/_plan_validate.py`: the new
`verify-batch-mismatch` check and its wiring into `run()`, the symmetric under-indent detection
inside `_check_requirements_quote_indent_drift`, and the two new `_CITATION_MARKERS` entries. One
batch because all five cards edit the same module and share the same reading context; splitting them
would make three batches each re-load the same file. The external interface the next batch consumes
is the set of emitted `check` keys and message strings: `verify-batch-mismatch` (new), the new
"after adding N leading spaces per line" message on the existing
`requirements-quote-indent-drift` key, and the two new citation markers. Batch-local decision beyond
the overview's Shared Decisions: none.

## Cards

### Card 1: Add the `_check_verify_batch_mismatch` check function

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new module-level function
  `_check_verify_batch_mismatch(batch_files: list[Path], overview_text: str, project_root: Path) -> list[dict]`.
  Place it immediately after `_check_depends_on_batch_mismatch` and before the
  `# Check 6 -- reads-not-backtick-path` banner comment block that follows it.
  Behaviour, mirroring `_check_depends_on_batch_mismatch`'s structure:
  (1) call `extract_batch_index(overview_text)` inside `try: ... except PlanDAGError: return []`,
  carrying the same "Check 4 has already recorded the parse error; don't double-report" rationale in
  a comment;
  (2) build `stem_to_path = {bf.stem: bf for bf in batch_files}` and iterate the returned entries,
  skipping any entry whose `Path(entry.get("file", "")).stem` is not a key of `stem_to_path`;
  (3) for the overview side, call `_plan_dag.parse_verify_field(entry, project_root, project_root)`
  on the index entry dict itself (it is a mapping carrying its own `verify:` key, which is exactly
  what that normalizer takes) and keep the returned command; on `ValueError as exc`, append a finding
  with message `f"overview Batch Index verify: is malformed: {exc}"` and continue to the next entry
  -- this check is the only reporter for a malformed index-entry `verify:`, because
  `_check_verify_malformed_cwd` inspects batch-file and overview *frontmatter* only, never index
  entries;
  (4) for the batch side, read the batch file's frontmatter via
  `_plan_dag._read_batch_frontmatter(path)` (never a hand-rolled fence scan) and call the same
  normalizer on it; on `ValueError`, `continue` silently, because `_check_verify_malformed_cwd` is
  the documented sole reporter for that case and duplicating it here would double-report;
  (5) derive each side's raw cwd key independently of the normalizer: the value of the `cwd` key when
  that side's raw `verify:` value is a dict, else `None`. The raw key must be compared rather than
  the normalizer's resolved `Path`, because both root arguments are passed as `project_root`, so
  `cwd: hub` and `cwd: git_root` would otherwise resolve to the same path and their drift would be
  invisible;
  (6) when the `(command, raw_cwd_key)` pair differs between the two sides, append one finding with
  `check` `"verify-batch-mismatch"`, `batch` set to the index entry's `name`, `card` `None`, `path`
  `None`, and a message naming both sides' command and cwd key, in the same
  "per-batch file ... disagrees with overview Batch Index ..." phrasing
  `_check_depends_on_batch_mismatch` uses.
  Absent, explicit-null, and blank-string `verify:` all normalize to `None` through the shared
  normalizer, so those three spellings compare equal to one another and produce no finding.
  Give the function a module-style docstring covering the sole-reporter split for malformed values,
  the raw-cwd-key rationale, and the `{check, batch, card, path, message}` error-dict shape. ASCII
  only in all new comments and docstrings.
- **Commit:** `feat(plan-validate): add verify-batch-mismatch check`

### Card 2: Wire `verify-batch-mismatch` into `run()` and the docstrings

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `run()`, add
  `errors.extend(_check_verify_batch_mismatch(batch_files, overview_text, project_root))`
  on the line immediately after the existing `_check_depends_on_batch_mismatch(...)` call, so the two
  sibling drift checks stay adjacent. In the module header docstring's "Checks performed (check
  keys)" list, add a `verify-batch-mismatch` entry directly after the existing
  `depends-on-batch-mismatch` entry, describing it as "a batch's overview Batch Index `verify:`
  disagrees with that batch file's own frontmatter `verify:` (command or cwd)", following the same
  two-space continuation-indent style the neighbouring entries use. In `run()`'s own docstring,
  append `verify-batch-mismatch` to the prose enumeration of check names it already carries. Add only
  that one name to `run()`'s docstring -- the several check names already missing from it are
  deliberately left untouched (see the overview's docstring-backfill decision).
- **Commit:** `feat(plan-validate): wire verify-batch-mismatch into run()`

### Card 3: Add the `_add_n_leading_spaces` helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `_add_n_leading_spaces(text: str, n: int, *, include_blank: bool = False) -> str`
  directly after `_strip_n_leading_spaces` and before `_card_edits_tokens`. It splits `text` via
  `.splitlines()`, prepends exactly `n` space characters to each line, and rejoins with `"\n"`. When
  `include_blank` is `False` (the default), a line whose `.strip()` is empty is emitted unchanged
  rather than padded. Give it a docstring stating that it is the exact inverse of
  `_strip_n_leading_spaces` -- a fixed per-line add, not a re-indent -- and explaining the
  `include_blank` split: a real nested source excerpt usually has genuinely empty separator lines
  (editors strip trailing whitespace), so the default reproduces the true source, while
  `include_blank=True` covers a source that keeps whitespace-only indented lines. ASCII only.
- **Commit:** `feat(plan-validate): add _add_n_leading_spaces helper`

### Card 4: Detect under-indented Requirements fences

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extend `_check_requirements_quote_indent_drift`'s per-fence loop with a third
  pass. The two existing passes are unchanged in behaviour and in emitted text: the raw-substring
  early `continue` stays exactly as it is, and the ascending `for n in range(1, 41)` strip search
  keeps its current first-match-wins walk over `ordered_resolved_tokens` and its current message,
  which must remain byte-for-byte
  "card {card_num}'s Requirements: fence {fence_idx} matches '{matched_token}' after stripping {n}
  leading spaces per line (found N={n})".
  Restructure so the strip pass records whether it matched (e.g. a local `matched` flag set beside
  the `errors.append`), and when it did, move on to the next fence unchanged. Only when the strip
  pass found nothing, run an add pass over the same ascending `for n in range(1, 41)`: for each `n`,
  first test `_add_n_leading_spaces(fence_body, n)` and, if that does not match, test
  `_add_n_leading_spaces(fence_body, n, include_blank=True)`, each time walking
  `ordered_resolved_tokens` in declaration order and testing substring membership in
  `resolved_contents[token]`. The first match in that order wins, appends one finding with `check`
  `"requirements-quote-indent-drift"`, the same `batch`/`card`/`path` fields the strip pass uses, and
  the message
  "card {card_num}'s Requirements: fence {fence_idx} matches '{matched_token}' after adding {n}
  leading spaces per line (found N={n})",
  then stops the add search for that fence. A fence matching in neither direction at any `n` in range
  stays silently skipped, exactly as today -- it is an illustrative new-state snippet, not a drifted
  quote.
  Update the function's own docstring to describe both directions, why the strip pass runs first
  (a fence cannot legitimately match both ways, so preserving the incumbent ordering keeps every
  currently-emitted message stable), and the non-blank-then-all-lines variant order. Also widen the
  module header docstring's `requirements-quote-indent-drift` entry so it describes drift in either
  direction rather than a strip-only match. ASCII only.
- **Commit:** `fix(plan-validate): detect under-indented Requirements fences`

### Card 5: Exempt inline-signature citations from context-completeness

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Append two entries to the `_CITATION_MARKERS` tuple: `"signature inlined"` and
  `"no file read needed"`. They are matched by the existing lowercased-substring guard inside
  `_check_context_completeness`, so no call-site change is needed. Extend the explanatory comment
  above the tuple with one sentence stating that the two new markers cover the case where a
  `Requirements:` line inlines a cited symbol's full signature and therefore needs no file read,
  which is why naming the defining file on that line is not an unlisted read dependency. Extend
  exemption item 2 in `_check_context_completeness`'s own docstring the same way, so the docstring
  and the tuple stay consistent. Do not widen the marker set further and do not change the matching
  mechanism. ASCII only.
- **Commit:** `feat(plan-validate): exempt inline-signature citations from context-completeness`

## Batch Tests

`verify:` runs the whole `test-plan-validate.py` unit-test file, which is the single test file
covering `_plan_validate.py`. At this batch it acts as a regression gate: every existing check's
findings and message strings must stay unchanged while three new behaviours are added. The unit tests
asserting the *new* behaviour land in batch 2, which re-runs the same file. The file is invoked
directly (it exposes its own `main()` under `if __name__ == "__main__":`) rather than through
`run-all.py --only`, which keeps the command to one process for a single-file scope.
