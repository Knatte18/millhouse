# Batch: core-taxonomy

```yaml
task: "Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch"
batch: "core-taxonomy"
number: 1
cards: 8
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-common.py test-review-finalize.py"
depends-on: []
```

## Batch Scope

This batch delivers the entire taxonomy engine inside `_review_common.py` and brings its two direct test files to the new contract in the same commit range, so the suite is never left red.
It adds the `Finding` dataclass, the class/severity constants, `extract_findings`, `resolve_blocking_classes`, the ceiling plus demotion rewrite plus verdict derivation inside `finalize_scope`, the widened regexes on the two legacy counting helpers, `GAPS_FOUND` back-compat in `parse_verdict`, and the `findings` field on `ReviewResult`.
Every later batch consumes exactly three things from here: the module-level names `extract_findings`, `resolve_blocking_classes`, and the `blocking_classes` keyword argument on `finalize_scope`, plus the `findings` key in `ReviewResult.to_dict()`.
No other batch may re-implement the ceiling; see the `ceiling-applied-once-at-write-time` Shared Decision.

Batch-local decision: `finalize_scope`'s new `blocking_classes` parameter is keyword-only and defaults to `None`, which means "apply no ceiling".
`None` is the correct default because the historical/test call sites that do not pass it must keep their current counting behaviour, and because a stage that legitimately blocks on every class is expressible as the full class set rather than as a sentinel.
Every production call site passes it explicitly; batches 2, 3, and 4 add those arguments, and `test-review-class-taxonomy.py` asserts the ceiling is reached through each backend's own `finalize` entry point rather than only through `finalize_scope` directly.

## Cards

### Card 1: Taxonomy constants and the Finding dataclass

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add module-level constants near the existing `ReviewResult` dataclass: `BLOCKING_SEVERITY = "BLOCKING"`, `NIT_SEVERITY = "NIT"`, and `RECOGNIZED_CLASSES = ("design", "scope", "decision", "consistency")`.
  Add a `@dataclass` named `Finding` with fields `severity: str`, `cls: str | None`, `title: str`, `demoted: bool = False`, and a method `to_dict(self) -> dict[str, Any]` returning `{"severity": ..., "class": ..., "title": ..., "demoted": ...}` -- note the serialised key is `class` while the Python attribute is `cls`, because `class` is a reserved word.
  The dataclass carries no field naming which mechanism the finding came from: card 4's rewrite keys on `title` and updates every representation of a demoted title, so an origin tag would be both unused and wrong for a title that appears in both mechanisms.
  Document in the `Finding` docstring that `cls is None` means the heading carried no class or an unrecognised one, and that such a finding is exempt from the ceiling.
- **Commit:** `feat(review): add Finding dataclass and class taxonomy constants`

### Card 2: extract_findings single-pass extractor

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `extract_findings(raw_text: str) -> list[Finding]` to `_review_common.py`, placed immediately after `count_unrecognized_severity_findings`.
  It scans the markdown-heading mechanism with a MULTILINE case-sensitive pattern of the shape `^###\s+\[(?P<sev>[A-Z0-9-]+)(?::(?P<cls>[a-z-]+))?\]\s+(?P<title>.*)$`, and independently scans every fenced ` ```yaml ` block for a `findings:` list whose entries are dicts, reading each entry's `severity`, `class`, and `title` fields.
  Both scans always run -- neither is gated on the other's result -- per the `dual-mechanism-scan-preserved` Shared Decision; a malformed yaml block is skipped silently exactly as `parse_blocking_count` already does.
  Severity classification per finding: a severity equal to `BLOCKING_SEVERITY` or `NIT_SEVERITY` (uppercased for the YAML path) is kept as-is; any other severity is forced to `BLOCKING_SEVERITY`, preserving today's house rule that an off-vocabulary severity folds into the blocking bucket.
  Class classification per finding: a class in `RECOGNIZED_CLASSES` is kept; a missing or unrecognised class becomes `None` and emits one ASCII-only stderr line of the shape `[_review_common] warning: finding has unknown or missing class -- <title>` (one line per such finding).
  Results from the two scans are concatenated heading-scan-first and then deduplicated **across mechanisms only**: a title produced by the yaml scan is dropped when and only when the heading scan already produced that same title.
  Two findings sharing a title within a single mechanism are both kept -- heading-vs-heading and yaml-vs-yaml alike.
  There is no same-mechanism dedup of any kind.
  Scope the dedup this way rather than as a flat first-occurrence-wins pass over the concatenation: a reviewer emitting two formulaic headings with the same title (e.g. "Missing test coverage" twice) is producing two genuinely distinct findings, and collapsing them would drop one from `findings` and from both scalars, and would leave card 4 with a `### [BLOCKING:<cls>]` heading on disk that no surviving `Finding` rewrites -- the exact file/envelope divergence the `demotion-rewritten-into-review-file` Shared Decision exists to prevent.
  The cross-mechanism collapse is the only one the `dual-mechanism-scan-preserved` Shared Decision calls for: its purpose is to stop one finding being counted twice for appearing in both representations, not to merge distinct findings within one.
  Set `demoted` to `True` for a finding that carries the demotion marker card 4 writes -- for the heading mechanism, a `**Demoted-from:** BLOCKING` line appearing among the finding's field lines before the next `###` heading; for the yaml mechanism, a `demoted_from` field on the entry -- and `False` otherwise.
  `extract_findings` still never applies the ceiling: it only reports a demotion that is already recorded in the text.
  This distinction matters at the two `_review_plan.py` re-read sites (batch 3 card 14), which read files already written in demoted form; without marker detection those sites would report `demoted: false` for genuinely demoted findings and the envelope's `findings` list would disagree with itself depending on whether an entry came fresh from `finalize_scope` or via carryforward.
  On the fresh path the marker does not exist yet when `extract_findings` runs -- `apply_blocking_ceiling` sets `demoted` there -- so the two paths agree.
- **Commit:** `feat(review): add single-pass extract_findings over headings and yaml`

### Card 3: resolve_blocking_classes config reader

- **Context:**
  - `mill-config.yaml`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `resolve_blocking_classes(cfg: dict, review_type: str, scope: str | None) -> frozenset[str]` to `_review_common.py`, placed in the dispatch-helpers section immediately after `aggregate_verdict`.
  Map `review_type` to a role key: `"discussion"` -> `"discussion-review"`, `"plan"` -> `"plan-review"`, `"code"` -> `"code-review"`.
  Map `scope` to a scope key: `None` or the literal `"holistic"` -> `"holistic"`, any other value -> `"batch"`.
  Read `cfg["roles"][<role>][<scope_key>]["blocking_classes"]` defensively -- every level may be missing or `None` -- and return `frozenset(value)` when it is a non-empty list of strings.
  When the key is absent, `None`, or not a list, return the documented default as a module-level constant `DEFAULT_BLOCKING_CLASSES` keyed by role name: `discussion-review` -> `frozenset({"design"})`, `plan-review` -> `frozenset({"design", "scope"})`, `code-review` -> `frozenset({"design", "scope", "decision", "consistency"})`.
  Never raise on a missing key; an unknown `review_type` falls back to `frozenset(RECOGNIZED_CLASSES)` so an unrecognised caller can never accidentally demote everything.
- **Commit:** `feat(review): add resolve_blocking_classes with per-stage defaults`

### Card 4: Ceiling application and demotion rewrite

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `apply_blocking_ceiling(findings: list[Finding], blocking_classes: frozenset[str]) -> list[Finding]` to `_review_common.py`.
  For each finding whose `severity` is `BLOCKING_SEVERITY` and whose `cls` is a non-`None` value not present in `blocking_classes`, set `severity` to `NIT_SEVERITY` and `demoted` to `True`.
  A finding whose `cls` is `None` is never demoted, per the `unknown-class-preserves-stated-severity` Shared Decision.
  A finding already at `NIT_SEVERITY` is never promoted, per the `ceiling-demotes-only` Shared Decision.
  Add `rewrite_demoted_findings(raw_text: str, findings: list[Finding]) -> str` to `_review_common.py`.
  It must rewrite **both** representations, because `extract_findings` reads both and a demotion visible in only one of them reproduces exactly the file/envelope divergence the `demotion-rewritten-into-review-file` Shared Decision exists to prevent.
  For each finding with `demoted is True`, keyed on the pair (`title`, `cls`) rather than on `title` alone, rewriting **every** occurrence that matches that pair rather than the first one only:
  (a) if a `### [BLOCKING:<cls>] <title>` heading line exists in `raw_text`, replace the severity token so the line becomes `### [NIT:<cls>] <title>`, then insert a new line `**Demoted-from:** BLOCKING` as the first non-blank line after that heading, preserving the blank line the templates place between a heading and its first field line;
  (b) if a fenced ` ```yaml ` block carries a `findings:` entry whose `title` equals that title and whose `severity` is `BLOCKING` case-insensitively, rewrite that entry's `severity:` field value to `NIT` and add a `demoted_from: BLOCKING` field to the same entry.
  Both branches run for every demoted finding, so a title present in both mechanisms is corrected in both.
  Matching on (`title`, `cls`) and rewriting every matching occurrence is what makes duplicate titles safe: two `### [BLOCKING:scope] Missing test coverage` headings are both out-of-ceiling and both demoted, so both must be rewritten, while a same-titled `### [BLOCKING:design]` heading does not match the `[BLOCKING:scope]` pair and is correctly left alone.
  This needs no positional bookkeeping and no count of how many `Finding` entries share a title.
  Rewrite the yaml entry by line-level edit within the located block rather than by re-serialising the parsed structure -- a `yaml.safe_dump` round-trip would reorder keys, restyle quoting, and drop comments across the whole block.
  Anchor every match at line start, and leave every line of `raw_text` not covered by (a) or (b) byte-identical.
- **Commit:** `feat(review): add blocking-class ceiling and dual-mechanism demotion rewrite`

### Card 5: Widen legacy regexes and retire the verdict fork

- **Context:**
  - `plugins/mill/scripts/_nit_gate.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `parse_blocking_count`, change the compiled pattern from `r"^###\s+\[" + re.escape(severity) + r"\]\s+"` to `r"^###\s+\[" + re.escape(severity) + r"(?::[a-z-]+)?\]\s+"` so `### [NIT:consistency]` is counted for `severity="NIT"`.
  In its fenced-yaml fallback, leave the `severity`-field comparison unchanged -- a `class:` field alongside it must not affect the count.
  Update the docstring to state that the optional class suffix is matched and that this function remains in use only for historical re-read sites, the new-review path going through `extract_findings`.
  In `count_unrecognized_severity_findings`, change `heading_pattern` from `r"^###\s+\[([A-Z0-9-]+)\]\s+"` to `r"^###\s+\[([A-Z0-9-]+)(?::[a-z-]+)?\]\s+"` so a classed heading is judged on its severity token alone, and add a docstring sentence stating that this function has no unknown-*class* responsibility -- that lives in `extract_findings` -- which is what prevents the double count.
  In `parse_verdict`, keep `"GAPS_FOUND"` in both closed-set checks (the fenced-block path and the unfenced-fallback path) but normalise it to `"REQUEST_CHANGES"` before returning, at both sites.
  Rewrite the `GAPS_FOUND` docstring bullet to describe it as a historical v1 discussion-review value that is accepted for archive readability and never emitted again, and update the invalid-value error message so it still names the four accepted input tokens.
- **Commit:** `refactor(review): widen severity regexes for class suffix, normalise GAPS_FOUND`

### Card 6: ReviewResult.findings

- **Context:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `findings: list[dict] = field(default_factory=list)` to the `ReviewResult` dataclass and emit it from `to_dict()` under the key `"findings"`, placed after `"nit_count"` and before `"reviews"`.
  Document in the `ReviewResult` docstring that `blocking_count` and `nit_count` are derived values consistent with `findings`, and that `findings` aggregates across sub-reviews by concatenation exactly as the scalars aggregate by summation.
  Do not change the existing field order of `type`, `round`, `verdict`, `reviews`, `blocking_count`, `nit_count` in the dataclass signature -- append the new field after `nit_count` so existing positional construction is unaffected.
- **Commit:** `feat(review): add findings list to ReviewResult envelope`

### Card 7: Rewire finalize_scope onto the single pass

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a keyword-only parameter `blocking_classes: frozenset[str] | None = None` to `finalize_scope`.
  Replace the body between `apply_actual_model_override` and the return with this order: call `parse_verdict(raw_text)`; call `extract_findings(raw_text)`; when `blocking_classes` is not `None`, call `apply_blocking_ceiling` on the extracted list and then `rewrite_demoted_findings` on `raw_text`; call `write_review_file` with the possibly-rewritten text; derive `blocking_count` as the number of findings whose `severity` is `BLOCKING_SEVERITY` and `nit_count` as the number whose `severity` is `NIT_SEVERITY`.
  Delete the `if review_type == "discussion": blocking_severity, nit_severity = "GAP", "NOTE"` fork and both `parse_blocking_count` calls and the `count_unrecognized_severity_findings` call from this function -- `extract_findings` now covers all three responsibilities in one pass.
  Recompute the returned verdict per the `verdict-derives-from-surviving-blocking-count` Shared Decision: when `parse_verdict` returned `"NEED_CONTEXT"`, return it unchanged; otherwise return `"REQUEST_CHANGES"` if `blocking_count > 0` else `"APPROVE"`.
  Add `"findings"` to the returned dict as `[f.to_dict() for f in findings]`, alongside the existing `scope`, `verdict`, `file`, `blocking_count`, `nit_count` keys.
  Update the docstring to describe the new parameter, the recomputed verdict, the demotion rewrite ordering relative to `apply_actual_model_override` and `write_review_file`, and the new returned key.
- **Commit:** `refactor(review): finalize_scope applies ceiling and derives verdict`

### Card 8: Taxonomy tests and existing-test migration

- **Context:**
  - `plugins/mill/unit_tests/test-nit-gate.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
  - `plugins/mill/unit_tests/test-review-finalize.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-review-class-taxonomy.py` following the existing in-file test-runner style of `test-review-finalize.py` (no real git, no real LLM, tempfile fixtures only, scratch under `.scratch/` if any file is needed outside `tempfile`).
  It must cover, at minimum: the ceiling table for all three stages via `resolve_blocking_classes` plus `finalize_scope`, asserting exactly which of one finding per class survive as `BLOCKING`; demote-only, asserting `[NIT:design]` at the discussion stage stays `NIT`; the demotion rewrite asserted against the text read back from the written file on disk, checking both the rewritten `### [NIT:scope]` heading and the inserted `**Demoted-from:** BLOCKING` line; a YAML-only demoted finding -- one present solely as a fenced `findings:` entry with `severity: BLOCKING` and an out-of-ceiling class -- asserting the written file's entry reads `severity: NIT` with a `demoted_from: BLOCKING` field, since a demotion reflected only in the envelope is the file/envelope divergence the `demotion-rewritten-into-review-file` Shared Decision forbids; a title present in **both** mechanisms and demoted, asserting both the heading and the yaml entry are rewritten while `findings` still contains exactly one entry for it; a re-read round trip, feeding the text written by a demoting `finalize_scope` call back into a bare `extract_findings` call and asserting the returned finding reports `demoted: true` from the marker alone, in both the heading and the yaml mechanism; verdict derivation, asserting `[BLOCKING:scope]`-only at the discussion stage yields `APPROVE` with `nit_count == 1` and `blocking_count == 0`; unknown-class handling for `[BLOCKING:perf]`, bare `[BLOCKING]`, `[NIT:perf]`, and bare `[NIT]`, asserting stated severity is preserved and no demotion occurred; the no-double-count regression asserting `[NIT:perf]` contributes exactly `1` to `nit_count`, `0` to `blocking_count`, and appears exactly once in `findings`, with all three asserted in the same test; the mixed-format document with markdown headings for one severity and a fenced `findings:` YAML block for the other, with an unknown class hidden in whichever mechanism the known labels did not use; deduplication of a title present in both mechanisms; two same-mechanism headings sharing one title, asserting **both** survive in `findings` and both contribute to the scalars -- and, when both are out-of-ceiling, that the written file carries two rewritten `### [NIT:<cls>]` headings and no residual `BLOCKING` one, which is the file/envelope divergence a flat title dedup would cause; the same duplicate-title case expressed entirely within the **yaml** mechanism -- two fenced `findings:` entries sharing one title and no heading for either -- asserting both survive and, when demoted, both entries are rewritten, since a heading-only version of this test would not catch a same-mechanism dedup applied to the yaml scan; `resolve_blocking_classes` falling back to each documented per-stage default when `blocking_classes` is absent from `cfg`; and `parse_verdict` normalising a historical `GAPS_FOUND` to `REQUEST_CHANGES`.
  In `test-review-common.py` and `test-review-finalize.py`, update every assertion that depends on the removed discussion-specific `GAP`/`NOTE` severity fork, on the reviewer's verdict being returned verbatim by `finalize_scope`, or on the exact key set of `finalize_scope`'s returned dict.
  Do not weaken an existing assertion to make it pass -- where the expected value genuinely changed, change the expected value and leave the assertion shape intact.
- **Commit:** `test(review): cover class taxonomy and migrate existing review tests`

## Batch Tests

`verify:` runs `test-review-class-taxonomy.py` (new, the primary coverage for every Decision in this batch), `test-review-common.py` (the largest consumer of `parse_verdict`, `parse_blocking_count`, and `count_unrecognized_severity_findings`), and `test-review-finalize.py` (the direct `finalize_scope` contract test).
The scope is deliberately these three files and not an unbounded `run-all.py`: the three flow tests, `test-nit-gate.py`, and the template tests all assert behaviour that later batches change, and running them here would report failures this batch is not responsible for.
Card 8's TDD candidates -- the ceiling table, demote-only, verdict derivation, unknown-class handling, and the no-double-count regression -- are fully specified in `## Requirements` and should be written before cards 2, 4, and 7 are implemented.
