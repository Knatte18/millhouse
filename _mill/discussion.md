# Discussion: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation

```yaml
task: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation
slug: mill-plan-requirements-byte-exactness-gap
status: discussing
parent: main
```

## Problem

When `/mill-plan` writes a docs-editing card's `Requirements:` field and quotes exact
source text inside a fenced code block nested under the `- **Requirements:**` list
item, natural Markdown list-continuation indentation (authoring the fence indented to
align with the enclosing list item, e.g. a 2-space continuation indent) gets baked into
the fence's literal byte content. The quoted "find" text then no longer byte-matches
the real source file, which silently breaks any literal `old_string` Edit-tool match an
implementer would attempt against it.

This was self-discovered during a `/mill-plan` run (source: GitHub issue #749,
consolidated into this wiki task, issue now closed). `_plan_validate.run`'s pre-review
gate — the mechanical check that already runs automatically before every review round —
has no check that catches this class of error. It was caught only by luck: an
independent holistic plan reviewer happened to diff the quoted text against the actual
source file. There is no guarantee a future occurrence gets caught the same way, since
review is LLM judgment, not a deterministic gate.

## Scope

**In:**
- A new mechanical check in `plugins/mill/scripts/_plan_validate.py`, wired into
  `run()`, that detects a card's `Requirements:` fenced block whose content only
  byte-matches its target `Edits:` file after a uniform per-line dedent (the exact
  signature of the list-continuation-indentation bug).
- A corresponding row in `/mill-plan`'s Step 1.5 fix table (`plugins/mill/skills/mill-plan/SKILL.md`)
  describing the mechanical fix: dedent the fence in place.
- An extension to the existing `Requirements:` bullet under `mill-plan/SKILL.md`'s
  `## Principles` section, explicitly warning that source-verbatim fences in
  `Requirements:` must be dedented to column 0 regardless of surrounding list nesting.
- Unit tests in `plugins/mill/unit_tests/test-plan-validate.py` following the existing
  `test_check_<name>_clean` / `test_check_<name>_dirty` pairing convention.

**Out:**
- No change to how `mill-plan` *authors* fences in the first place beyond the doc
  warning — this task does not add fence-authoring automation (e.g. auto-inserting
  quoted text programmatically). The planner (Opus) still hand-writes Requirements:
  prose and fences; the new check is a backstop, not a generator.
- No change to `millpy-review-plan.py`'s LLM reviewer prompts/templates — the holistic
  reviewer already catches this class of bug by diffing; this task adds a deterministic
  pre-review gate, it does not touch the review-prompt layer.
- No generalization to `Context:`/other fields' fenced blocks — scope is `Requirements:`
  fences specifically, since that's the field this bug class was observed in and the
  one whose fences are plausibly meant as literal `old_string` quotes.
- No handling of non-triple-backtick fence styles (e.g. `~~~`) — this codebase's
  convention is backtick fences only (see root `CLAUDE.md`: "Generated markdown: fenced
  \`\`\`yaml for metadata").

## Decisions

### fix-scope-both

- Decision: Implement both a mechanical validator check (backstop, automated) and a
  SKILL.md documentation warning (guidance, write-time).
- Rationale: This repo's established pattern pairs every `_plan_validate` check with a
  fix-table row and (where relevant) planner-facing guidance — see the existing
  `verify-not-isolated`/`move-mechanic-missing`/etc. checks, each of which has both a
  mechanical fix description and, in several cases, template/SKILL.md prose describing
  the expected shape up front. A doc-only fix relies entirely on the planner LLM
  remembering the rule every time — the planner (Opus) already produced this exact bug
  once despite generally careful output, so a doc-only fix has no automated backstop. A
  validator-only fix gives the planner no signal until the gate fires after the fact.
- Rejected: Doc-only (insufficient backstop, given the bug already slipped past the
  planner once). Validator-only (no write-time guidance, so the planner would rely
  entirely on the gate catching it rather than avoiding it).

### match-target-edits-only

- Decision: The check compares a card's `Requirements:` fence content against that
  card's own `Edits:` files only — not `Context:`, not other cards' files, not the
  whole batch's file union.
- Rationale: A `Requirements:` fence meant as `old_string` bait for the Edit tool is
  only meaningful against a file this card actually edits. `Context:`-only files are
  read-but-not-changed, so a literal-match requirement there is a weaker/irrelevant
  signal — Requirements fences quoting Context: files are far more likely to be
  illustrative excerpts, not find/replace targets.
- Rejected: `Edits:` ∪ `Context:` (weaker signal, more false positives). Whole-batch
  file union (too broad, defeats the point of scoping to the card that owns the fence).

### trigger-heuristic-near-miss

- Decision: The check fires ONLY when a fence's whitespace-dedented content (common
  leading whitespace stripped per non-blank line, equivalent to Python's
  `textwrap.dedent`) IS a literal substring of at least one of the card's `Edits:`
  files, BUT the RAW (un-dedented) fence content is NOT a literal substring of that same
  file. This is a near-miss / "would match if not for a uniform indent" test.
- Rationale: This is the exact signature of the list-continuation-indentation bug: the
  quoted text is correct except for a uniform baked-in indent. It has a very low
  false-positive rate — a fence that shows genuinely new/illustrative code (not a
  literal quote of existing source) will not match the source file even after dedent,
  so it is silently skipped rather than flagged. A fence with zero leading whitespace to
  strip in the first place can never trigger this check at all (dedent is a no-op, so
  raw == dedented, and the "raw does not match" / "dedented does match" pair can never
  both hold), which is exactly the class of fence the check should ignore since it has
  no drift to catch.
- Rejected: Fire on ANY fence that isn't a literal substring of `Edits:` files,
  regardless of near-miss (noisy — flags every fence showing new/desired-state code,
  which is a common and legitimate authoring pattern). Fire only when the fence is
  immediately preceded by a line containing the word "Find" (too fragile — that
  convention is not documented or enforced anywhere in this codebase, and issue #749's
  own repro does not require that literal word, so this trigger would miss real
  occurrences).

### mechanical-fix-dedent-in-place

- Decision: When the check fires, mill-plan's mechanical fix is: dedent the fence's
  body to column 0 (strip the common per-line leading whitespace amount) directly in
  the plan batch file, leaving the fence delimiters and surrounding list structure
  otherwise untouched.
- Rationale: Purely mechanical, deterministic text transform — no planning judgment
  required, consistent with how other purely-formatting fix-table rows work (e.g.
  `verify-not-isolated`'s literal-prefix prepend, `move-format`'s re-formatting).
- Rejected: Halt (treat as structural) — unnecessary ceremony for a deterministic
  transform. Re-fetch fresh bytes from the source file and replace the whole fence body
  — riskier, since it could silently overwrite a deliberate partial-quote/elision the
  planner intended to keep (e.g. an ellipsized excerpt), whereas dedent only removes
  whitespace and never changes the planner's chosen text content.

### doc-placement-principles-bullet

- Decision: The SKILL.md guidance is added to the existing `Requirements:` bullet under
  mill-plan/SKILL.md's `## Principles` section (the bullet starting "`Requirements:`
  must use stable identifiers").
- Rationale: That bullet is already the canonical home for `Requirements:`-authoring
  rules; keeping the new warning there means the planner sees it in the same place it
  already looks for Requirements:-field rules, without adding a new subsection under
  Phase: Plan for what is fundamentally a one-sentence rule (contrast with `## Rename
  mechanic`, which needed a full subsection because it prescribes multiple ordered
  steps).
- Rejected: New standalone subsection under Phase: Plan (unwarranted ceremony for a
  single-sentence rule). Fix-table-only (buries the guidance where the planner won't
  see it until after the check has already failed once).

### check-name

- Decision: Name the new check `requirements-quote-indent-drift`.
- Rationale: Follows this file's kebab-case, descriptive naming convention shared by
  every other check (`context-completeness`, `verify-not-isolated`, `move-mechanic-missing`,
  etc.) and names both the field it inspects (`requirements-quote`) and the specific
  defect class it detects (`indent-drift`), distinguishing it from unrelated fence or
  formatting checks.
- Rejected: none seriously considered — this is a naming-convention-following choice,
  not a design trade-off.

## Technical context

- `plugins/mill/scripts/_plan_validate.py` is the module to edit. Its `run()` function
  (around line 2403) is the single call site that aggregates every check; each check is
  a `_check_<name>(...)` function returning `list[dict]` with keys
  `{check, batch, card, path, message}`, appended via `errors.extend(...)`.
- `_extract_requirements_text(card_text)` (around line 1384) already isolates a card's
  `Requirements:` field body (the header line plus every subsequent line up to the next
  `- **<Field>:**` header or end of card). Reuse this — do not re-implement
  Requirements-field extraction.
- `_parse_cards(batch_text)` (around line 120) yields `(card_num, card_lines)` pairs per
  batch file; this is the existing per-card iteration primitive used by every other
  per-card check (e.g. `_check_context_completeness` at line 1462 iterates
  `_parse_cards(text)` then calls `_extract_requirements_text` per card — follow this
  exact pattern).
- Per-card `Edits:` extraction: `_RE_REFS_HEADER = re.compile(r"^-\s*\*\*(Context|Edits|Creates|Deletes):\*\*(?P<inline>.*)$")`
  (line 79) captures the field name in group 1; `_RE_REFS_SUB = re.compile(r"^\s+-\s*(.+)$")`
  (line 94) matches multi-line sub-bullets. There is no existing per-card
  Edits:-only extractor (`_parse_edits_only` at line 153 operates on a whole batch
  file, not a single card's text) — a new small helper is needed that walks a single
  card's lines, matches `_RE_REFS_HEADER` with `m.group(1) == "Edits"`, and collects
  either the inline value or the following `_RE_REFS_SUB` sub-bullets, extracting
  backtick tokens with `re.findall(r"`([^`]+)`", ...)` (same token-extraction idiom used
  throughout the file, e.g. in `_card_own_reference_set` at line 1408).
- `resolve_existing_paths` (imported from `_review_common` at the top of
  `_plan_validate.py`, line ~71) resolves a backtick token to an actual on-disk path,
  respecting `root`/`wiki_root`/`git_root` the same way every other check does — use it
  to resolve each `Edits:` token to a real file before reading its content for the
  substring comparison. Do not hand-roll path resolution.
- Fence extraction: no existing fence-parsing helper exists anywhere in
  `_plan_validate.py` (confirmed by grep) — write a small regex,
  e.g. `re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)`, applied to the
  `requirements_text` string returned by `_extract_requirements_text`. A single
  Requirements: field may contain more than one fence — iterate over all matches, not
  just the first.
- Dedent: use `textwrap.dedent` (stdlib, not yet imported in this file — add the
  import) on the fence body captured by the regex above. This correctly ignores
  whitespace-only lines when computing the common-prefix amount while still stripping
  that amount from every line, which is the standard/expected dedent semantics.
- Line-ending normalization: normalize both the fence body and the target file's
  content by replacing `"\r\n"` with `"\n"` before the substring comparisons, so a
  Windows checkout (CRLF) does not produce a false negative against a plan file
  authored with LF fences (or vice versa).
- Error dict shape must stay exactly `{check, batch, card, path, message}` (no new
  keys — this is the documented return contract of `run()`, and `millpy-bg`/the
  Agent-mode envelope pass these dicts through verbatim as the `errors` array). Put the
  offending fence's first line (or first ~40 chars) into `message` so mill-plan's
  mechanical-fix step can locate which fence to dedent when a card has more than one.
  `path` should be the `Edits:` file path the dedented content matched against.
- `mill-plan/SKILL.md`'s Step 1.5 fix table (around line 141-165) is a markdown table;
  the new row's mechanical-fix column should read something like: "Locate the card's
  `Requirements:` fence identified by the error payload's `message` (its first line/
  snippet). Dedent the fence body to column 0 (strip the common per-line leading
  whitespace) so its content is a literal byte-exact substring of the target `Edits:`
  file named in the payload's `path` field." — follow the exact prose style/verb
  choices of neighboring rows (e.g. `verify-not-isolated`'s row).
- `mill-plan/SKILL.md`'s `## Principles` section, `Requirements:` bullet (around line
  278), currently ends "...forces the implementer to explore, defeating the cold-start
  guarantee." Append a sentence there (or a new adjacent bullet) warning that any
  fenced block quoting exact source text inside `Requirements:` must be dedented to
  column 0 regardless of surrounding list-item nesting, since Markdown
  list-continuation indentation gets baked into the fence's literal byte content and
  breaks literal `old_string` Edit-tool matches.
- `plugins/mill/unit_tests/test-plan-validate.py` already has the fixture conventions
  to follow: `_make_batch_file(...)` (line 96) and `_make_batch_file_cards(...)` (line
  169) build batch-file text with `tempfile.TemporaryDirectory()`; tests are paired
  `test_check_<name>_clean` (no error expected) / `test_check_<name>_dirty` (error
  expected), each returning an `int` (0/1) per this file's existing test-runner
  convention. New tests must also write the target `Edits:` file's on-disk content
  into the tempdir (via `resolve_existing_paths`' expected layout) since this check,
  unlike some purely-textual checks, reads actual file bytes to compare against.

## Constraints

No `CONSTRAINTS.md` exists at the hub root (checked via
`_constraints.read_if_exists()` during exploration — absent). No other constraints
were surfaced during discussion beyond the scope/decisions above.

## Testing

- `plugins/mill/unit_tests/test-plan-validate.py`, following the existing
  `test_check_<name>_clean`/`test_check_<name>_dirty` pairing:
  - `test_check_requirements_quote_indent_drift_clean_exact_match`: fence content is
    already a byte-exact substring of the target `Edits:` file (no indent to strip) →
    no error.
  - `test_check_requirements_quote_indent_drift_clean_illustrative_snippet`: fence
    shows new/desired-state code that does not match the target file even after
    dedent → no error (proves the near-miss heuristic does not false-positive on
    legitimate illustrative fences).
  - `test_check_requirements_quote_indent_drift_clean_no_edits_field`: card's `Edits:`
    is `none`/empty → check is a no-op for that card (nothing to compare against).
  - `test_check_requirements_quote_indent_drift_dirty_list_continuation_indent`: fence
    is authored with a uniform list-continuation indent baked into every line; raw
    content is NOT a substring of the target file, dedented content IS → error fires,
    with `path` pointing at the matched `Edits:` file and `message` identifying the
    offending fence.
  - `test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card`: a card
    with two `Requirements:` fences, only one of which has the drift bug → exactly one
    error, correctly identifying the drifted fence (not the clean one).
  - A CRLF-normalization case: target file content uses `\r\n`, fence body uses `\n`
    (or vice versa) with a list-continuation indent otherwise matching the
    dirty case → error still fires (proves line-ending normalization works), OR
    conversely a case proving normalization prevents a false negative.
- TDD candidate: `_check_requirements_quote_indent_drift` itself is the natural
  TDD-first unit — write the clean/dirty test pairs before the implementation, mirroring
  how every other check in this file already has its own clean/dirty pair.
- No integration-test coverage needed — this is pure text/logic validation with no git
  or LLM interaction, matching every other `_check_*` function's test coverage in this
  file (all covered by `unit_tests`, none by `integration_tests`).

## Q&A log

- **Q:** Which fix(es) to implement — SKILL.md doc guidance, a mechanical validator
  check, or both? **A:** [auto-pick] Both. **Why:** matches this repo's established
  pattern (every validator check pairs a fix-table row with guidance); a doc-only fix
  has no automated backstop given the planner already produced this exact bug once.
- **Q:** Which files does a quoted `Requirements:` fence get checked against? **A:**
  [auto-pick] The card's own `Edits:` files only. **Why:** a fence meant as Edit-tool
  `old_string` bait is only meaningful against files this card actually edits;
  `Context:`-only files are read-but-not-changed, a weaker/irrelevant signal.
- **Q:** What heuristic decides a fence is "suspicious" without flagging every
  legitimate illustrative code snippet? **A:** [auto-pick] Near-miss detection — fire
  only when the whitespace-dedented fence content matches the target file but the raw
  content does not. **Why:** this is the exact signature of the list-continuation-
  indentation bug and inherently cannot false-positive on fences with zero leading
  whitespace to strip (dedent becomes a no-op) or on genuinely new/illustrative code
  (which won't match even after dedent).
- **Q:** What is the mechanical fix when the check fires? **A:** [auto-pick] Dedent the
  fence body to column 0 in place. **Why:** deterministic text transform, no planning
  judgment required, consistent with other purely-formatting fix-table rows.
- **Q:** Where does the SKILL.md guidance go? **A:** [auto-pick] Extend the existing
  `Requirements:` bullet under `## Principles` in mill-plan/SKILL.md. **Why:** already
  the canonical home for Requirements:-authoring rules; avoids unwarranted ceremony of
  a new subsection for a one-sentence rule.
