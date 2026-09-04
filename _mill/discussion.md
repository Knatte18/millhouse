# Discussion: _plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps

```yaml
task: '_plan_validate.py: Batch Index/batch-file verify: drift, flattened-fence, and large-file-citation gaps'
slug: plan-validate-batch-index-drift-and-misc-checks
status: discussing
parent: main
```

## Problem

Four GitHub issues (#965, #908, #915, #920) report three independent gaps in the static plan
pre-validator `plugins/mill/scripts/_plan_validate.py`:

1. **verify: drift (#965, #908).** `00-overview.md`'s `## Batches` index and each per-batch file's
   own fenced-yaml frontmatter each carry a `verify:` value. `_plan_dag.parse_verify_field` reads
   the *batch file's* copy as authoritative (mill-go's per-batch finalize, `mill-merge-in`'s verify
   replay), while a human or LLM reading the plan reads the *overview's* copy. The validator has a
   `depends-on-batch-mismatch` check comparing the two copies of `depends-on:`, but no equivalent
   for `verify:`. Observed live twice: in `mill-go-windows-baseline-teardown-winerror145` the
   overview listed real commands for all four batches while every batch file said `verify: null`,
   so mill-go ran zero verify commands and reported success anyway (three plan-review rounds missed
   it); in loomyard's `final-summary-artifact` the overview's batch-2 command silently lacked a
   `go vet -tags integration ./...` clause the batch file carried, so the weaker command would have
   run.

2. **Flattened Requirements fences (#915).** `requirements-quote-indent-drift` only ever *removes*
   leading spaces (`_strip_n_leading_spaces`, N = 1..40) when hunting for a byte-match against the
   card's `Edits:` files. A fence flattened to column 0 while the true source is nested (e.g. under
   a `- **Direct path:**` bullet, carrying a 2-space base indent) can never match at any N >= 0, so
   the check silently passes on a plan whose implementer `Edit` calls will fail at `old_string`
   lookup time. Caught two plan-review rounds late by the LLM reviewer, as a demoted NIT.

3. **Large-file signature citation (#920).** A card needing only a large sibling file's exact
   function signature has no documented way to cite it. Adding the file to `Context:` is the
   `batch-oversized` fix table's only documented remedy, and it pushed one real batch from ~104934
   to ~135746 estimated tokens, past the 120000 cap, with no batch split able to help (the card's
   own `Edits:` already consumed ~104934). The only working alternative -- inlining the signature in
   prose while deliberately avoiding a backtick-wrapped path-shaped token so `context-completeness`
   does not fire -- is undocumented, and the natural phrasing trips the check immediately.

**Why now:** all four issues are already triaged and folded into this single task; each is a silent
gate failure, where the validator returns zero findings on a plan that is genuinely broken.

## Scope

**In:**

- New `verify-batch-mismatch` check in `plugins/mill/scripts/_plan_validate.py`, comparing each
  batch's overview Batch Index `verify:` against that batch file's own frontmatter `verify:`.
- Symmetric under-indent (add-N) detection inside the existing
  `_check_requirements_quote_indent_drift`, with a directional message.
- Two new entries in `_CITATION_MARKERS` exempting an inline-signature citation from
  `context-completeness`.
- Module docstring check-list updates in `_plan_validate.py` (both the header list and `run()`'s
  docstring), adding **only** the two new entries -- see the `docstring-backfill-out-of-scope`
  Decision.
- The "Check coverage" docstring at the top of `plugins/mill/unit_tests/test-plan-validate.py`
  (line ~26) gains `verify-batch-mismatch`.
- `plugins/mill/skills/mill-plan/SKILL.md` Step 1.5 fix-table: a new `verify-batch-mismatch` row, a
  rewritten `requirements-quote-indent-drift` row covering both directions, and cross-references on
  the `batch-oversized` and `context-completeness` rows documenting the inline-signature remedy.
- Unit tests appended to `plugins/mill/unit_tests/test-plan-validate.py` (and registered in its
  `main()` test list).

**Out:**

- `_plan_dag.py` behaviour. The batch file stays authoritative for verify execution; this task adds
  a *gate*, it does not change which side wins at runtime.
- `parse_verify_field`'s schema (string / `{cwd, command}` mapping) -- unchanged.
- Raising or changing `pipeline.max_batch_context_tokens`, or altering `_check_batch_oversized`'s
  token estimator. #920 is resolved by an exemption plus documentation, not by moving the cap.
- Any change to `_check_context_completeness`'s core resolution logic beyond appending markers.
- Splitting the 7369-line `test-plan-validate.py` into smaller files.
- Backfilling the check names already missing from `run()`'s docstring and from
  `test-plan-validate.py`'s "Check coverage" docstring -- see the `docstring-backfill-out-of-scope`
  Decision.
- Reopening or re-triaging the four source issues (all already CLOSED).

## Decisions

### verify-batch-mismatch-standalone-check

- Decision: add a new standalone check named `verify-batch-mismatch`, structurally mirroring
  `_check_depends_on_batch_mismatch` (same `(batch_files, overview_text)`-plus-roots argument shape,
  same `{check, batch, card, path, message}` error dict, `card: None`, `path: None`, `batch` naming
  the diverging batch, one finding per diverging batch).
- Rationale: #965 explicitly asks for a check "mirroring `depends-on-batch-mismatch`'s shape and its
  'edit whichever side is stale' fix-table remedy". A separate check name gives the fix table one
  unambiguous row and lets `skip_checks` disable it independently.
- Rejected: generalizing `depends-on-batch-mismatch` into a multi-field drift check (would change an
  existing check's message shape and its fix-table row for no gain); a doc-only remedy (both issues
  report the gate silently passing -- documentation does not gate).

### verify-comparison-normalized-command-plus-cwd-key

- Decision: normalize each side's `verify:` through `_plan_dag.parse_verify_field` to obtain the
  command string, and separately compare the *raw* `cwd:` key (the literal `"hub"` / `"git_root"`
  string, or `None` for the plain-string form) taken straight from the raw yaml value. Two batches
  agree only when both the normalized command and the raw cwd key match. Pass `project_root` for
  both the `hub_root` and `git_root` arguments of `parse_verify_field`, exactly as the sibling
  `_check_verify_not_isolated` / `_check_verify_malformed_cwd` already do.
- Rationale: normalizing the command absorbs irrelevant differences (surrounding whitespace,
  `verify:` absent vs explicit `null` vs empty string -- all three normalize to `None`, which is the
  correct "nothing to run" equivalence). The raw cwd key must be compared separately *because* both
  roots are passed as `project_root`: `cwd: hub` and `cwd: git_root` would otherwise resolve to the
  same `Path` and their drift would be invisible. Comparing the raw key is also layout-independent
  -- it does not need a real nested layout to be meaningful.
- Rejected: comparing command strings only (misses cwd drift, which changes what the command
  actually runs against); raw `==` on the yaml values (would fire spuriously on `verify:` absent vs
  `verify: null`, and on trailing whitespace).

### verify-batch-mismatch-reports-malformed-index-entry

- Decision: when `parse_verify_field` raises `ValueError` on the **overview Batch Index entry's**
  `verify:`, emit a `verify-batch-mismatch` finding whose message states the batch name and the
  exception text (e.g. `overview Batch Index verify: is malformed: <exc>`). When it raises on the
  **batch file's own frontmatter**, skip that batch silently.
- Rationale: `_check_verify_malformed_cwd` is documented as the *sole* reporter for malformed
  frontmatter `verify:` -- it reads batch files and the overview's own top-level frontmatter, but it
  never inspects the `batches:` index entries. A malformed index-entry `verify:` is therefore
  reported by nothing today. Reporting it here fills the hole without double-reporting anything.
- Rejected: skipping both sides silently (leaves the index-entry hole open); reporting both sides
  (duplicates `verify-malformed-cwd` for the frontmatter side, violating its documented sole-reporter
  contract).

### verify-batch-mismatch-mapping-scope

- Decision: compare only those Batch Index entries whose `file:` field's `Path(...).stem` matches an
  actual batch file stem in `batch_files`, reusing `_check_depends_on_batch_mismatch`'s exact
  stem-to-path mapping construction. Index entries with no matching file, and batch files with no
  index entry, produce no `verify-batch-mismatch` finding.
- Rationale: an unmapped entry is a different defect already owned by other checks
  (`depends-on-unknown`, `missing-overview`, and the DAG parse path). Duplicating that reporting here
  would double-report a structural error.
- Rejected: also flagging unmapped entries (out of this check's concern).

### verify-batch-mismatch-parse-failure-degradation

- Decision: on `PlanDAGError` from `extract_batch_index(overview_text)`, return `[]` -- copy
  `_check_depends_on_batch_mismatch`'s existing `try/except PlanDAGError: return []` comment and
  behaviour (`depends-on-unknown` has already recorded the parse error). Batch-file frontmatter is
  read via `_plan_dag._read_batch_frontmatter`, which already degrades to `{}` on a malformed or
  missing yaml block rather than raising.
- Rationale: consistency with the sibling check; a plan whose overview index will not parse produces
  one parse finding, not N derived ones.
- Rejected: raising; re-implementing the yaml-block scan inline (the sibling check's hand-rolled
  fence scan is legacy -- `_read_batch_frontmatter` is the shared helper and is what the newer verify
  checks already use).

### indent-drift-extended-not-renamed

- Decision: keep the check name `requirements-quote-indent-drift` and extend
  `_check_requirements_quote_indent_drift` with a symmetric "add N leading spaces" search. The
  emitted message states the direction explicitly: the existing over-indent message stays byte-for-byte
  as it is today (`... matches '<token>' after stripping <n> leading spaces per line (found N=<n>)`),
  and the new under-indent case reads `... matches '<token>' after adding <n> leading spaces per line
  (found N=<n>)`.
- Rationale: #915 frames this as the same defect ("the check should also detect the reverse case").
  The name already says "drift", not "over-indent". Keeping one name keeps one fix-table row and one
  `skip_checks` entry, and avoids re-classifying an existing check that plan-review configs may
  already reference. Preserving the existing message verbatim means no currently-passing test or
  fixer instruction changes behaviour for the over-indent direction.
- Rejected: a new `requirements-quote-under-indent` check (two names for one defect class, two
  fix-table rows); delta re-anchoring off the first non-blank line (a single anchor line can match
  many places in a file, and a fence whose first line is blank or is itself indented differently
  breaks the anchor -- the exhaustive N search is both simpler and strictly more accurate).

### add-n-blank-line-handling

- Decision: `_add_n_leading_spaces(text, n)` prepends `n` spaces to every **non-blank** line, leaving
  blank lines (empty or whitespace-only after `.rstrip()`) untouched. For each N the search first
  tries this non-blank-only variant; if it does not match, it tries an all-lines variant that
  prepends `n` spaces to every line including blank ones. The first match, in ascending N and with
  non-blank-only tried before all-lines at the same N, wins and stops the search.
- Rationale: a nested source block in a real Markdown or Python file almost always has genuinely
  empty separator lines (editors strip trailing whitespace), so the non-blank-only variant reproduces
  the true source in the common case. The all-lines variant covers the minority of sources that keep
  whitespace-only indented lines. Both variants are cheap (<= 80 extra substring tests per fence) and
  a false negative here is exactly the bug being fixed.
- Rejected: all-lines only (misses the common case entirely); non-blank-only (leaves a residual
  blind spot for whitespace-preserving sources).

### indent-drift-search-order

- Decision: the per-fence search order is (1) raw fence body already a literal substring of a
  resolved `Edits:` file -> clean, no finding (unchanged); (2) strip search N = 1..40 (unchanged, and
  unchanged in its message and its first-match-wins tie-break over `ordered_resolved_tokens`); (3)
  only if the strip search found nothing, the add search N = 1..40 with the two blank-line variants.
  A fence matching nothing in any of the three passes stays silently skipped, exactly as today (it is
  an illustrative new-state snippet, not a drifted quote).
- Rationale: running the strip pass first preserves today's behaviour and messages byte-for-byte for
  every plan that currently produces a finding. A fence cannot legitimately match in both directions
  at once, so ordering is only about which message wins in a pathological case, and preserving the
  incumbent is the safer choice.
- Rejected: interleaving the two searches by N (changes existing findings' messages for no benefit).

### context-completeness-inline-signature-exemption

- Decision: resolve #920 with both halves of its "expected": (a) append two markers to
  `_CITATION_MARKERS` in `_plan_validate.py` -- `"signature inlined"` and `"no file read needed"` --
  so a `Requirements:` line that inlines a symbol's full signature can also name its defining file in
  backticks without tripping `context-completeness`; (b) document the marker and the underlying
  interaction in `mill-plan/SKILL.md`'s Step 1.5 fix table.
- Rationale: `_CITATION_MARKERS` is already the established, documented exemption mechanism
  (lowercased substring match against the physical line carrying the backtick token), so this is an
  additive two-line change with no new machinery. Documentation alone would leave planners with the
  undocumented backtick-avoidance workaround the issue explicitly calls out as accidental.
- Rejected: docs only (leaves the natural phrasing broken); exemption only (leaves the
  `batch-oversized` <-> `context-completeness` interaction undiscoverable); a new structural
  exemption syntax (over-engineered for a two-marker gap).

### citation-marker-wording

- Decision: exactly two new markers, `"signature inlined"` and `"no file read needed"`, matched the
  same way every existing marker is (lowercased substring, same physical line as the backtick token).
  The SKILL.md guidance instructs the planner to write the marker on the same line as the cited path,
  e.g. `` ... calls `resolve_ref_paths(refs, project_root, root, *, wiki_root=None, git_root=None)`
  as defined in `_review_common.py` -- signature inlined, no file read needed. ``
- Rationale: two phrasings cover both natural ways a planner states the intent; more markers would
  widen the exemption surface and risk masking genuine missing-context findings. Both phrases are
  specific enough that they cannot appear by accident in unrelated prose.
- Rejected: a single marker (one phrasing is easy to miss); a broad marker like `"inlined"` (too
  likely to appear incidentally and silently suppress a real finding).

### tests-extend-existing-file

- Decision: append the new tests to `plugins/mill/unit_tests/test-plan-validate.py` and register each
  new function in that file's `main()` `tests = [...]` list (the registry is manual -- an unregistered
  test silently never runs).
- Rationale: every `_plan_validate` test already lives there, with established tmp-plan-fixture
  helpers to reuse. The file's size is a separate concern, deliberately out of scope here.
- Rejected: a new test file (splits the check's tests across two files with no offsetting benefit).

### docstring-backfill-out-of-scope

- Decision: the plan adds exactly the new entries to the three docstrings it touches --
  `verify-batch-mismatch` to `_plan_validate.py`'s header check list and to `run()`'s docstring
  check enumeration, the widened both-directions wording to the header list's
  `requirements-quote-indent-drift` entry, and `verify-batch-mismatch` to
  `test-plan-validate.py`'s "Check coverage" docstring. Check names that are *already* missing from
  those docstrings before this task starts (`run()`'s docstring omits `depends-on-batch-mismatch`,
  `context-completeness`, `requirements-quote-indent-drift`, `plugin-manifest-context-missing`,
  `verify-not-isolated`, `verify-full-suite`, `verify-malformed-cwd`; the test file's docstring is
  likewise incomplete) are left exactly as they are.
- Rationale: the pre-existing staleness is a separate, larger clean-up with its own review surface;
  folding it in would widen a targeted three-gap fix into an unrelated docs sweep and inflate the
  diff a plan reviewer has to check. Stating it explicitly removes the guess.
- Rejected: backfilling every omission while the file is open (scope creep, and the omissions are
  not what any of the four issues report); leaving the question unstated (the plan writer would have
  to guess, which is what the review flagged).

## Technical context

- `plugins/mill/scripts/_plan_validate.py` (3039 lines) is the whole checker. Structure: module
  docstring listing every check key (must be updated for `verify-batch-mismatch` and for the
  indent-drift check's widened description), then one `_check_*` function per check, then the public
  `run()` which calls each in a fixed order, sorts by `(batch, card, check)`, and finally filters
  `skip_checks`.
- `_check_depends_on_batch_mismatch` (line ~1193) is the structural template for the new check: it
  calls `extract_batch_index(overview_text)` inside `try/except PlanDAGError -> return []`, builds
  `number_to_name`, maps each index entry's `Path(entry["file"]).stem` against
  `{bf.stem: bf for bf in batch_files}`, then compares per batch. Its own frontmatter read is a
  hand-rolled fence scan; the new check should use `_plan_dag._read_batch_frontmatter(path)` instead,
  which is what `_check_verify_not_isolated` and `_check_verify_malformed_cwd` already use and which
  returns `{}` on any structural problem.
- `_plan_dag.parse_verify_field(frontmatter, hub_root, git_root) -> tuple[str | None, Path | None]`
  is the single normalizer: `None` / absent / blank string -> `(None, None)`; plain string ->
  `(stripped, None)`; `{cwd: hub|git_root, command: <str>}` -> `(stripped, resolved_root)`; anything
  else raises `ValueError`. It takes a *frontmatter dict*, so a Batch Index entry (itself a dict with
  a `verify:` key) can be passed to it directly.
- `_check_verify_malformed_cwd` (line ~2498) documents itself as the sole reporter for malformed
  frontmatter `verify:`; `_check_verify_not_isolated` and `_check_verify_full_suite` both swallow the
  same `ValueError` to avoid double-reporting. Neither inspects Batch Index entries.
- `_check_requirements_quote_indent_drift` (line ~1885) uses: `_card_edits_tokens(card_text)` for the
  card's own `Edits:` tokens in declaration order; `_requirements_fence_aware_body(card_lines)` for
  the fence-aware `Requirements:` body; `_RE_FENCE_BODY` (```` ```[^\n]*\n(.*?)``` ````, DOTALL) for
  the fences; `re.sub(r"\n[ \t]*\Z", "", fence_body)` to drop the trailing newline; and
  `_strip_n_leading_spaces` (line ~1787) for the fixed per-line strip. The new
  `_add_n_leading_spaces` belongs directly beside it and must carry the same style of docstring
  explaining why it is a fixed per-line add rather than a re-indent.
- `_CITATION_MARKERS` (line ~1565) is a module-level tuple of lowercased substrings, consumed at the
  `any(marker in lowered_line for marker in _CITATION_MARKERS)` guard inside
  `_check_context_completeness`. The tuple carries an explanatory comment above it that should be
  extended, not replaced.
- `plugins/mill/skills/mill-plan/SKILL.md` Step 1.5 fix table: `depends-on-batch-mismatch` at line
  ~365, `context-completeness` ~376, `requirements-quote-indent-drift` ~377, `verify-mixed-cwd` ~382,
  `batch-oversized` ~385. The table is alphabetically loose but grouped; put the new
  `verify-batch-mismatch` row with the other `verify-*` rows.
- `plugins/mill/unit_tests/test-plan-validate.py` is 7369 lines with a manual `tests = [...]`
  registry in `main()`. Its module docstring (line ~26) lists the covered check names and should gain
  `verify-batch-mismatch` (adding only that name -- see `docstring-backfill-out-of-scope`).
- The two source repos in the issues (loomyard, millhouse) are only provenance -- no cross-repo work.

## Constraints

- ASCII-only in `print()`/`_log()` output and, by house style, in new comments and docstrings
  (`--` for em-dash, `->` for arrows) -- Windows cp1252 crashes on non-ASCII stdout.
- `verify:` commands in plan files must start with a literal `PYTHONPATH= ` prefix for this Python
  project (`_check_verify_not_isolated` enforces it) -- the plan's own batch `verify:` commands must
  therefore read
  `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py`.
- `run-all.py --only` takes test-file basenames; unknown names fail.
- No new third-party dependencies; `yaml` and stdlib only, as today.
- Existing check messages must not change for inputs that already produce findings.
- `test-plan-validate.py` is ~330 KB; a batch whose `Edits:` includes it plus `_plan_validate.py`
  (~120 KB) is near the `pipeline.max_batch_context_tokens` cap, so the plan should not pile further
  large files into the same batch.

## Testing

All tests go in `plugins/mill/unit_tests/test-plan-validate.py`, following its existing
tmp-plan-fixture style (write a small `00-overview.md` plus batch files into a temp plan dir, call
`_plan_validate.run(...)`, filter the result by `check`), and each must be added to `main()`'s
registry.

`verify-batch-mismatch` -- TDD candidate, this is a brand-new check:

- overview index and batch file carry identical plain-string `verify:` -> no finding.
- overview names a real command, batch file says `verify: null` (issue #908's exact shape) -> exactly
  one finding naming that batch.
- both sides carry a command, differing only by an extra clause (issue #965's shape) -> one finding.
- both absent / both null / one absent and one explicit `null` -> no finding (all normalize to
  "nothing to run").
- one side plain string `X`, other side `{cwd: git_root, command: X}` -> one finding (the raw cwd
  keys `None` vs `"git_root"` differ).
- both sides `{cwd: hub, command: X}` -> no finding; `cwd: hub` vs `cwd: git_root` with the same
  command -> one finding.
- malformed index-entry `verify:` (mapping with no `command:`) -> one `verify-batch-mismatch` finding
  carrying the exception text, and no `verify-malformed-cwd` finding for that entry.
- malformed batch-file frontmatter `verify:` -> zero `verify-batch-mismatch` findings and exactly one
  `verify-malformed-cwd` finding (no double-report).
- unparseable overview `## Batches` block -> zero `verify-batch-mismatch` findings.
- an index entry whose `file:` names a nonexistent batch file -> zero `verify-batch-mismatch`
  findings.

`requirements-quote-indent-drift` under-indent extension:

- fence flattened to column 0 quoting a source excerpt with a 2-space base indent (issue #915's
  shape) -> one finding whose message says "after adding 2 leading spaces per line".
- source excerpt containing a genuinely empty separator line, fence flattened -> still detected (the
  non-blank-only add variant).
- source excerpt whose separator line is whitespace-only-with-indent -> still detected (the all-lines
  add variant).
- regression: an existing over-indent fixture still produces the identical "after stripping N" message
  it produces today.
- regression: a byte-exact fence -> no finding.
- an illustrative fence matching neither direction at any N in 1..40 -> no finding.

`context-completeness` marker exemption:

- a `Requirements:` line naming a backtick path plus the text `signature inlined` -> no finding.
- same with `no file read needed` -> no finding.
- the same line without either marker -> still one finding (proves the exemption is the reason, not
  an unrelated change).

Full-file regression: `run-all.py --only test-plan-validate.py` must stay green, and the repo-wide
`run-all.py` at the done gate.

## Q&A log

- **Q:** What shape should the verify-drift check take? **A:** [auto-pick] New standalone check `verify-batch-mismatch` mirroring `depends-on-batch-mismatch`. **Why:** #965 asks for exactly that mirror, and a separate name gives one fix-table row and an independent `skip_checks` entry.
- **Q:** How should the two `verify:` values be compared? **A:** [auto-pick] Normalize the command via `parse_verify_field`, compare the raw `cwd:` key separately. **Why:** normalization absorbs absent/null/whitespace noise, and the raw cwd key is required because both roots are passed as `project_root` and would otherwise collapse to one `Path`.
- **Q:** What about a malformed `verify:` inside a Batch Index entry? **A:** [auto-pick] Report it as `verify-batch-mismatch`. **Why:** `verify-malformed-cwd` never inspects index entries, so nothing reports it today; the batch-file side stays silent to honour that check's sole-reporter contract.
- **Q:** Which batches get compared? **A:** [auto-pick] Only index entries whose `file:` stem maps to a real batch file. **Why:** unmapped entries are a structural defect other checks already own.
- **Q:** How should under-indented fences be detected? **A:** [auto-pick] Extend `requirements-quote-indent-drift` with a symmetric add-N search and a directional message. **Why:** same defect class, one name, one fix-table row; existing over-indent messages stay byte-for-byte identical.
- **Q:** How are blank lines handled when adding indent? **A:** [auto-pick] Non-blank-only variant first, then an all-lines variant; first match wins. **Why:** real sources usually have truly empty separator lines, but the minority that do not must not become a new blind spot.
- **Q:** In what order do the three passes run? **A:** [auto-pick] raw substring, then strip N=1..40, then add N=1..40. **Why:** preserves today's behaviour and messages for every plan that currently produces a finding.
- **Q:** How is #920 resolved? **A:** [auto-pick] Both an exemption marker and fix-table documentation. **Why:** docs alone leave the natural phrasing broken; the exemption alone leaves the `batch-oversized` <-> `context-completeness` interaction undiscoverable.
- **Q:** Which exemption markers? **A:** [auto-pick] `signature inlined` and `no file read needed`. **Why:** two phrasings cover both natural wordings while staying specific enough not to fire accidentally.
- **Q:** Where do the tests live? **A:** [auto-pick] Extend `test-plan-validate.py` and its `main()` registry. **Why:** every `_plan_validate` test is already there with reusable fixtures; splitting the file is out of scope.
