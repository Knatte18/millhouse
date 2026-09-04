# Batch: validator-tests

```yaml
task: '_plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps'
batch: 'validator-tests'
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [1]
```

## Batch Scope

Unit coverage for the three behaviours batch 1 added, plus the one-line "Check coverage" docstring
update at the top of the test file. One batch because every card appends to the same file and shares
the same fixture helpers already defined there. It consumes batch 1's external interface directly:
the `verify-batch-mismatch` check key, the two directional `requirements-quote-indent-drift`
messages, and the two new citation markers. Batch-local decision beyond the overview's Shared
Decisions: each new test function must be appended to the manual `tests = [...]` registry inside
`main()` -- that registry is not auto-discovered, so an unregistered test silently never runs.

## Cards

### Card 6: Unit tests for `verify-batch-mismatch`

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Append test functions covering the new `verify-batch-mismatch` check, following
  the file's established style: build a temporary plan directory with a `00-overview.md` plus batch
  files, call `_plan_validate.run(...)`, filter the returned list by `e["check"]`, print a `FAIL`
  line and return `1` on mismatch, return `0` on success. Reuse whichever tmp-plan fixture helper the
  file already defines for the sibling `depends-on-batch-mismatch` and `verify-mixed-cwd` tests
  rather than writing a new fixture. Cover, one test function per scenario: identical plain-string
  `verify:` on both sides is clean; the overview naming a real command while the batch file carries
  `verify: null` produces exactly one finding naming that batch; two commands differing by a trailing
  clause produce one finding; `verify:` absent on one side and explicitly `null` on the other is
  clean, as is both-absent and both-null; a plain string on one side against a
  `{cwd: git_root, command: <same string>}` mapping on the other produces one finding, because the
  raw cwd keys differ; the same mapping form with the same `cwd` on both sides is clean while
  `cwd: hub` against `cwd: git_root` with an identical command produces one finding; an index entry
  whose `verify:` is a mapping with no `command:` produces exactly one `verify-batch-mismatch`
  finding whose message contains the normalizer's error text and no `verify-malformed-cwd` finding
  for that entry; a batch file whose own frontmatter `verify:` is that same malformed mapping
  produces zero `verify-batch-mismatch` findings and exactly one `verify-malformed-cwd` finding; an
  overview whose `## Batches` fenced yaml is unparseable produces zero `verify-batch-mismatch`
  findings; and an index entry whose `file:` names a batch file that does not exist produces zero
  `verify-batch-mismatch` findings. Register every new function in `main()`'s `tests` list.
- **Commit:** `test(plan-validate): cover verify-batch-mismatch`

### Card 7: Unit tests for under-indented Requirements fences

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Append test functions for the under-indent direction of
  `requirements-quote-indent-drift`, reusing the fixture helper the existing over-indent tests in
  this file already use. Each fixture writes a real target file on disk, lists it in the card's
  `Edits:`, and quotes part of it in the card's `Requirements:` fence. Cover: a source excerpt with a
  two-space base indent quoted by a fence flattened to column zero produces one finding whose message
  states it matched after adding 2 leading spaces per line; the same shape where the source excerpt
  contains a genuinely empty separator line is still detected, exercising the default non-blank-only
  add variant; the same shape where the source's separator line is whitespace-only with its own
  indent is still detected, exercising the `include_blank=True` variant; an existing over-indented
  fence still produces the unchanged "after stripping N leading spaces per line" message, asserted on
  the message text so a regression in the frozen wording fails the test; a byte-exact fence produces
  no finding; and an illustrative fence matching in neither direction at any N produces no finding.
  Register every new function in `main()`'s `tests` list.
- **Commit:** `test(plan-validate): cover under-indented requirements fences`

### Card 8: Unit tests for the inline-signature citation markers

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Append test functions for the two new citation markers, reusing the fixture
  helper the existing `context-completeness` tests in this file already use. Cover: a card whose
  `Requirements:` line names a real, resolvable, backtick-wrapped file path absent from that card's
  own reference fields together with the text `signature inlined` produces no
  `context-completeness` finding; the same line carrying `no file read needed` instead produces no
  finding; and the identical line with neither marker still produces exactly one finding, which is
  what proves the exemption rather than an unrelated change is responsible. Register every new
  function in `main()`'s `tests` list. Separately, add `verify-batch-mismatch` to the "Check
  coverage" list in this file's own module docstring near the top -- add only that one name, leaving
  the names already missing from that list untouched per the overview's docstring-backfill decision.
- **Commit:** `test(plan-validate): cover inline-signature citation markers`

## Batch Tests

`verify:` runs `test-plan-validate.py` directly, which is both the file this batch edits and the only
test file covering `_plan_validate.py`. It therefore doubles as the batch's own assertion suite and
as a regression gate over every pre-existing check. Running the single file directly rather than
through `run-all.py --only` keeps the command to one process for a single-file scope.
