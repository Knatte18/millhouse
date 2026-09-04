# Batch: fix-table-docs

```yaml
task: '_plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps'
batch: 'fix-table-docs'
number: 3
cards: 1
verify: null
depends-on: [2]
```

## Batch Scope

Documentation-only batch: the Step 1.5 fix table in `plugins/mill/skills/mill-plan/SKILL.md` gains a
row for the new `verify-batch-mismatch` check, a rewritten `requirements-quote-indent-drift` row
covering both drift directions, and cross-references on the `context-completeness` and
`batch-oversized` rows documenting the inline-signature remedy. Separated from batches 1 and 2
because it shares no file with them and has no runnable surface of its own. It consumes the check
keys and message strings batches 1 and 2 established; it introduces no interface. Batch-local
decision beyond the overview's Shared Decisions: none.

## Cards

### Card 9: Fix-table rows for the new and widened checks

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Make four edits to the Step 1.5 fix table (the markdown table whose header row is
  `| check | mechanical fix |`), matching the surrounding rows' single-line, pipe-delimited format
  exactly -- each row is one physical line, however long.
  (1) Add a new `verify-batch-mismatch` row, placed immediately before the existing
  `verify-not-isolated` row so it sits with the other `verify-*` rows. Its mechanical fix: the
  payload's `batch:` field names the batch whose per-batch file frontmatter `verify:` disagrees with
  the overview Batch Index entry for that same batch, and the `message:` field shows both sides'
  command and cwd key; edit whichever side is stale so both name the identical command and the
  identical `cwd:` key, mirroring the `depends-on-batch-mismatch` row's "edit whichever side is
  stale" remedy. State that a message reading "overview Batch Index verify: is malformed" instead
  means the index entry's own `verify:` mapping is unparseable -- fix that mapping per the
  `verify-malformed-cwd` row's guidance, then re-run.
  (2) Rewrite the `requirements-quote-indent-drift` row so it branches on the payload `message:`
  field's direction: a message reading "after stripping N leading spaces per line" keeps today's
  remedy verbatim (strip exactly N leading space characters from each line of the identified fence,
  preserving whatever baseline indentation remains); a message reading "after adding N leading spaces
  per line" means the fence is flattened relative to its source, so add exactly N leading space
  characters to each non-blank line of the fence body. In both cases the goal is identical: the fence
  body must end up a literal byte-exact substring of the `Edits:` file named in the payload's `path:`
  field.
  (3) Extend the `context-completeness` row with the inline-signature escape hatch: when the cited
  file is large and the card needs only a symbol's exact signature rather than the file's contents,
  the documented remedy is to inline the full signature in the `Requirements:` prose and put the
  phrase `signature inlined` or `no file read needed` on the same physical line as the backtick-
  wrapped path, which the check's citation-marker exemption then honours -- instead of adding a large
  file to `Context:` purely to satisfy this check and pushing the batch over the context cap.
  (4) Extend the `batch-oversized` row with a cross-reference to that same escape hatch: before
  concluding a batch cannot be split, check whether a large `Context:` entry exists only to satisfy
  `context-completeness` for a signature citation, in which case the inline-signature marker removes
  the entry and the overage with it. Keep the row's existing "splitting a batch is a structural
  change, not a mechanical fix -- halt" remedy for every other case.
  Change no other row and add no new section.
- **Commit:** `docs(mill-plan): document verify-batch-mismatch and inline-signature remedies`

## Batch Tests

`verify: null` -- this batch edits one SKILL.md file and has no runnable surface. Its correctness is
established by the plan review and code review of the prose itself; no unit test exercises the fix
table.
