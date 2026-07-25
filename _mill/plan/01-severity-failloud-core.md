# Batch: severity-failloud-core

```yaml
task: mill-plan review severity counting and validation schema gaps
batch: severity-failloud-core
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
depends-on: []
```

## Batch Scope

Adds the shared fail-loud helper that closes the severity-vocabulary blind spot at its root: `_review_common.py`, imported by every one of the three review types' `finalize_scope()` path. This batch delivers the helper itself and wires it into `finalize_scope()`, so plan review, code review, and discussion review (all three go through `finalize_scope`) immediately stop silently dropping unrecognized-severity findings from `blocking_count`/`nit_count`. The next batch (`02-severity-failloud-legacy-callsites`) applies the same helper to `_review_plan.py`'s separate, duplicated subprocess-dispatch call sites, which do NOT go through `finalize_scope()`.

External interface the next batch consumes: the new function `count_unrecognized_severity_findings(raw_output: str, *, blocking_severity: str, nit_severity: str) -> int` in `_review_common.py`.

## Cards

### Card 1: Add the fail-loud unrecognized-severity helper to `_review_common.py`

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new public function `count_unrecognized_severity_findings(raw_output: str, *, blocking_severity: str, nit_severity: str) -> int` immediately after `parse_blocking_count` (currently ending at line 1626, immediately before `write_review_file`). The function counts findings whose severity label matches neither `blocking_severity` nor `nit_severity`, scanning BOTH of the following mechanisms unconditionally (never gating one on the other's result — see Shared Decision "unrecognized-severity scan covers both output formats, unconditionally"):
  1. Markdown headings: reuse the same regex shape as `parse_blocking_count` (`^###\s+\[<label>\]\s+`, `re.MULTILINE`, case-sensitive). Scan every `### [XXX]` heading in `raw_output`; for each, if the bracketed label (case-sensitive) is neither `blocking_severity` nor `nit_severity`, increment the count.
  2. YAML-fenced `findings:` blocks: reuse the same fenced-block-scanning approach `parse_blocking_count` already uses for its own YAML fallback (search for ` ```yaml ` opening fences, collect body lines until the closing ` ``` `, `yaml.safe_load` the body, skip blocks that fail to parse or lack a `findings:` list). For every entry in every such `findings:` list, if the entry is a dict with a `severity` field whose value (uppercased) is neither `blocking_severity.upper()` nor `nit_severity.upper()` (case-insensitive, matching `parse_blocking_count`'s existing YAML-path case-insensitivity), increment the count.
  Sum both mechanisms' counts and return the total (explicitly not deduplicated — see the "Accepted risk" paragraph in `_mill/discussion.md`'s Technical context section: a finding expressed as both a heading and a mirroring YAML entry is deliberately counted twice; do not add dedup logic). Add a one-line docstring explaining the "always scans both, never conditional" rule and citing that it is deliberate (not a bug) per the mixed-format edge case in `_mill/discussion.md`. Add `count_unrecognized_severity_findings()` to the module's "Public API" docstring list at the top of the file (after the `parse_blocking_count()` line, before `write_review_file()`), one line, same style as the existing entries (e.g. `count_unrecognized_severity_findings() — count findings whose severity matches neither of the two recognized labels, scanning both headings and YAML fallback`).
- **Commit:** `feat(review): add fail-loud unrecognized-severity counting helper`

### Card 2: Wire the fail-loud helper into `finalize_scope()`

- **Context:** none (covered by Card 1's Edits)
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `finalize_scope` (currently lines 1744-1799), after the existing `blocking_count = parse_blocking_count(raw_text, severity=blocking_severity)` and `nit_count = parse_blocking_count(raw_text, severity=nit_severity)` lines, add a call to `count_unrecognized_severity_findings(raw_text, blocking_severity=blocking_severity, nit_severity=nit_severity)` and add its result into `blocking_count` (e.g. `blocking_count += count_unrecognized_severity_findings(...)`). This applies uniformly to all three review types since `finalize_scope` already branches `blocking_severity`/`nit_severity` per `review_type` (`GAP`/`NOTE` for discussion, `BLOCKING`/`NIT` otherwise) — no `review_type`-specific branching is needed for the new call, it uses whichever `blocking_severity`/`nit_severity` pair `finalize_scope` already resolved. Do not modify the returned dict's key names (`blocking_count` stays the field name for all three review types, matching existing `ReviewResult`/finalize() usage in `_review_plan.py`, `_review_code.py`, and `_review_discussion.py`, none of which need any changes as a result of this card — they all consume `finalize_scope`'s return dict unchanged).
- **Commit:** `feat(review): fold unrecognized-severity findings into blocking_count via finalize_scope`

### Card 3: Add unit tests for the fail-loud helper and its `finalize_scope` wiring

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add new test blocks to `main()` in `test-review-common.py`, inserted immediately after the existing `parse_blocking_count` YAML-fallback test block (the block ending around "PASS: parse_blocking_count yaml severity is case-insensitive", before the "parse_blocking_count divergence warning" section) so the new tests sit next to the function they extend. Cover, for `count_unrecognized_severity_findings(raw_output, blocking_severity="BLOCKING", nit_severity="NIT")` unless noted otherwise:
  1. Empty input -> 0, no crash.
  2. One `### [MAJOR]` heading -> 1.
  3. One `### [MEDIUM]`, one `### [HIGH]`, one `### [MINOR]` heading (three separate small tests or one combined) -> each counts identically to MAJOR (no special-casing by word).
  4. A `### [BLOCKING]` heading -> 0 from this helper (it is a known severity, not unrecognized; the existing `parse_blocking_count(severity="BLOCKING")` call already counts it elsewhere).
  5. A `### [NIT]` heading -> 0 from this helper.
  6. Mixed-case `### [Major]` and `### [major]` -> 0 (case-sensitive heading matching, consistent with `parse_blocking_count`'s existing case-sensitive heading behavior).
  7. A fenced ` ```yaml ` `findings:` block (no markdown headings at all) with one entry `severity: MAJOR` and no matching `### [MAJOR]` heading anywhere -> 1.
  8. Same as case 7 but `severity: major` (lowercase) -> 1 (case-insensitive YAML-path matching, mirroring `parse_blocking_count`'s existing YAML case-insensitivity).
  9. A document containing BOTH a `### [MAJOR]` heading AND a real `### [NIT]` heading, where the YAML `findings:` fallback would never fire under `parse_blocking_count`'s own per-severity logic (heading_count > 0 for NIT) -- verify the new helper still finds the `[MAJOR]` heading (proves the unconditional-scan Shared Decision: the helper does not skip the heading scan just because NIT used headings).
  10. Same document as case 9, but with an ADDITIONAL unrecognized severity expressed ONLY as a YAML `findings:` entry (no corresponding heading) -- verify the helper's count includes both the `[MAJOR]` heading AND the YAML-only entry (proves the "unconditionally scans both mechanisms, not gated on which mechanism the known severities used" Shared Decision).
  11. A discussion-typed call (`blocking_severity="GAP", nit_severity="NOTE"`) with a stray `### [MAJOR]` heading -> 1, proving the helper works for the GAP/NOTE pair too (not hardcoded to BLOCKING/NIT).
  12. A double-counting case: a document with both a `### [MAJOR]` heading AND a mirroring YAML `findings:` entry with `severity: MAJOR` for what a human would consider "the same finding" -> assert the count is 2 (not deduplicated), with a code comment citing this is the accepted, documented behavior (per `_mill/discussion.md`'s "Accepted risk" note), not a bug to fix later.
  Then add one `finalize_scope()` integration-style test: call `finalize_scope` (already imported at the top of this test file) with `review_type="plan"` and raw text containing one `### [BLOCKING]`, one `### [MAJOR]`, and one `### [NIT]` heading (plus a valid `verdict:` yaml block and `reviewed_file:`/`date:` fields matching what other existing `finalize_scope` calls in this file already construct -- follow an existing `finalize_scope` test's raw-text fixture shape in this file as the template) -> assert `result["blocking_count"] == 2` and `result["nit_count"] == 1`. Place this test near the end of the file's `parse_blocking_count`/severity-related section, after the new helper's own tests. Update `errors` accumulation and PASS/FAIL print statements following this file's existing convention (ASCII-only per project `CLAUDE.md`).
- **Commit:** `test(review): cover fail-loud unrecognized-severity helper and finalize_scope wiring`

## Batch Tests

`verify:` runs the full `test-review-common.py` file (not scoped via `--only`) because this batch's Card 1 adds a new function to `_review_common.py`, a cross-cutting helper module imported by every Layer 02 review backend (`_review_discussion.py`, `_review_plan.py`, `_review_code.py`, and the API scripts, per the module's own docstring) — `test-review-common.py` is the single test file covering that whole shared module, so running it in full (rather than a narrower `--only` subset) is the correct verify scope for a change to `_review_common.py` itself, not an unbounded over-scoping choice.
