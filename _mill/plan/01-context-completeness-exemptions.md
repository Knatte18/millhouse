# Batch: context-completeness-exemptions

```yaml
task: '_plan_validate.py context-completeness: path-token exemption list gaps'
batch: context-completeness-exemptions
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch implements all three new `context-completeness` exemptions (`_mill/discussion.md`'s
Decisions section) and wires each into `_check_context_completeness`'s existing per-token exemption
chain. It is its own batch, separate from the batch that adds unit tests for these exemptions
(`02-context-completeness-exemptions-tests.md`), because `_plan_validate.py`
(this batch's sole edited file, ~44k context-token estimate) and `test-plan-validate.py` (that
batch's sole edited file, ~118k) together exceed `pipeline.max_batch_context_tokens` (120000) if
combined into one batch — splitting by file, not by feature, is what keeps each batch under cap; see
`00-overview.md`'s Shared Decisions for why per-file splitting was chosen over any alternative. Cards
1-3 add and wire one exemption mechanism each, in the same order `_mill/discussion.md`'s Decisions
section presents them (ownership, then literal-enumeration, then illustrative-output) — each card's
new `continue` guard is inserted immediately after the previous card's, so cards 1-3 must run in
numeric order.

## Cards

### Card 1: Cross-card ownership exemption

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new module-level verb-form dict and a new exemption function, immediately before the
  existing `def _extract_requirements_text(card_text: str) -> str | None:` function definition:

  ```python
  # Ownership-attribution verb forms (lowercased, word-boundary matched, hand-spelled per verb --
  # base/3rd-person/past/gerund, "rewrite" given the same irregular 5-form treatment "write" gets
  # in _PROHIBITION_VERB_FORMS): a same-line "batch|card <N> <verb>" phrase names another card/batch
  # as the owner of the token, not a dependency this card itself reads.
  _OWNERSHIP_VERB_FORMS = {
      "own": ("own", "owns", "owned", "owning"),
      "fix": ("fix", "fixes", "fixed", "fixing"),
      "correct": ("correct", "corrects", "corrected", "correcting"),
      "rewrite": ("rewrite", "rewrites", "rewrote", "rewriting", "rewritten"),
      "address": ("address", "addresses", "addressed", "addressing"),
      "handle": ("handle", "handles", "handled", "handling"),
      "resolve": ("resolve", "resolves", "resolved", "resolving"),
      "cover": ("cover", "covers", "covered", "covering"),
      "edit": ("edit", "edits", "edited", "editing"),
      "update": ("update", "updates", "updated", "updating"),
  }

  _OWNERSHIP_RE = re.compile(
      r"\b(?:batch|card)\s+\d+(?:'s)?\s+(?:"
      + "|".join(
          re.escape(form)
          for forms in _OWNERSHIP_VERB_FORMS.values()
          for form in forms
      )
      + r")\b"
  )


  def _is_cross_card_ownership_exempt(lowered_line: str) -> bool:
      """Return True when ``lowered_line`` (already lowercased) contains a same-line
      "batch|card <N> <ownership-verb>" phrase (optionally possessive, e.g. "batch 8's fix"),
      independent of the token's own position -- mirrors ``_is_prohibition_exempt``'s line-wide (not
      clause-scoped) granularity, not ``_is_contrast_citation_exempt``'s clause-wide one, because the
      motivating real-world phrasing ("...`x.cs`, which batch 8 fixes.") puts a comma between the
      token and the ownership phrase, which `_clause_bounds` would treat as a clause boundary.
      Accepted tradeoff: an unrelated "batch N fixes" mention elsewhere on an unusually long
      Requirements: line exempts every backtick token on that line, not just the one the phrase
      refers to -- the same false-negative-adjacent tradeoff `_is_prohibition_exempt`'s own
      line-wide match already accepts.
      """
      return bool(_OWNERSHIP_RE.search(lowered_line))
  ```

  Wire it into `_check_context_completeness`'s per-token exemption chain by inserting a new
  `continue` guard immediately after the existing:

  ```python
                    # Contrast-citation exemption: this occurrence shares a clause with "rather
                    # than"/"instead of", naming it as the chosen or rejected half of a comparison.
                    if _is_contrast_citation_exempt(lowered_line, match.start(1), match.end(1)):
                        continue
  ```

  and immediately before the existing `if is_path_shaped:` line, with matching indentation:

  ```python
                      # Cross-card ownership exemption: the line names another card/batch as the
                      # owner of this token, not a dependency this card itself reads.
                      if _is_cross_card_ownership_exempt(lowered_line):
                          continue
  ```

  Add a new item `11.` to `_check_context_completeness`'s own docstring numbered exemption list
  (the list currently ending at item `10. Quoted material: ...`), worded:
  `11. Cross-card ownership: a same-line phrase naming another card/batch as the owner of this token
  (e.g. "batch 8 fixes \`x.py\`", "card 23 corrects ... \`y.py\`") is not a dependency the card itself
  reads.`
- **Commit:** `feat(plan-validate): add cross-card ownership context-completeness exemption`

### Card 2: Literal-value enumeration exemption

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new exemption function, immediately after Card 1's `_is_cross_card_ownership_exempt`
  function body and before `def _extract_requirements_text`:

  ```python
  def _is_literal_enumeration_exempt(line: str, token_start: int, token_end: int) -> bool:
      """Return True when the token occurrence at ``[token_start, token_end)`` in ``line`` sits on a
      line carrying 3 or more backtick-quoted tokens total, at least one of which (other than this
      occurrence itself, matched by span, not by string equality, so a repeated literal value on the
      same line is judged independently at each occurrence) is neither path-shaped
      (``"/" in token or token.endswith(_PATH_CANDIDATE_EXTENSIONS)``) nor passes
      ``_symbol_candidate_shape`` -- the presence of a clearly-non-path/non-symbol sibling in the
      same enumeration is the signal that the whole line lists literal test-input values, not
      dependencies. A genuine multi-file dependency enumeration ("reads `a.py`, `b.py`, and `c.py`")
      contains only path-shaped tokens and never trips this rule. The 3-token threshold sits safely
      above ordinary 2-token contrastive prose ("`x.py` and `y.py`"), which is common in genuine
      dependency sentences and must never be swept in.

      Accepted tradeoff: a genuine dependency line that also names one non-path/non-symbol literal
      (e.g. a CLI flag or sentinel string alongside real file paths) is wrongly swept in and its real
      path tokens suppressed -- the same kind of tradeoff `_is_prohibition_exempt`'s and
      `_CITATION_MARKERS`' own docstrings already accept for their own line-wide mechanisms.
      """
      matches = list(_BACKTICK_RE.finditer(line))
      if len(matches) < 3:
          return False
      for m in matches:
          if m.start(1) == token_start and m.end(1) == token_end:
              continue
          other = m.group(1)
          other_is_path_shaped = "/" in other or other.endswith(_PATH_CANDIDATE_EXTENSIONS)
          if not other_is_path_shaped and _symbol_candidate_shape(other) is None:
              return True
      return False
  ```

  This reuses the existing per-line backtick regex `_check_context_completeness` already builds as a
  local variable `backtick_re = re.compile(r"\`([^\`]+)\`")` at the top of its own body -- promote
  that local variable to a new module-level constant `_BACKTICK_RE` with the identical pattern
  (defined immediately above `_OWNERSHIP_VERB_FORMS` from Card 1, purely for a stable, predictable
  location among this batch's other new module-level constants -- Card 1's `_is_cross_card_ownership_exempt`
  itself never calls `_BACKTICK_RE`; only this card's own `_is_literal_enumeration_exempt` does), and
  replace the local `backtick_re = re.compile(...)`
  assignment inside `_check_context_completeness` with `backtick_re = _BACKTICK_RE` so the existing
  per-token loop's own `backtick_re.finditer(line)` call keeps working unchanged.

  Wire it into `_check_context_completeness`'s per-token exemption chain by inserting a new
  `continue` guard immediately after Card 1's newly-added ownership-exemption guard and before the
  `if is_path_shaped:` line:

  ```python
                      # Literal-value enumeration exemption: 3+ backtick tokens on this line, at
                      # least one neither path- nor symbol-shaped, marks the whole line as a literal
                      # test-input enumeration rather than a dependency list.
                      if _is_literal_enumeration_exempt(line, match.start(1), match.end(1)):
                          continue
  ```

  Add a new item `12.` to the same docstring numbered exemption list, immediately after item `11.`
  from Card 1, worded:
  `12. Literal-value enumeration (path branch and symbol branch): a line with 3+ backtick tokens
  where at least one other token is neither path- nor symbol-shaped is treated as a literal
  test-input enumeration, not a dependency list.`
- **Commit:** `feat(plan-validate): add literal-value enumeration context-completeness exemption`

### Card 3: Illustrative-output exemption

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a new module-level verb-form dict, its compiled regex, and a new exemption function,
  immediately after Card 2's `_is_literal_enumeration_exempt` function body and before
  `def _extract_requirements_text`:

  ```python
  # Output/rendering verb forms (lowercased, word-boundary matched, hand-spelled per verb --
  # base/3rd-person/past/gerund, same shape as _PROHIBITION_VERB_FORMS): a line naming a
  # rendered/emitted/printed/displayed/output value describes that string as a described program
  # output, not a file the card reads.
  _OUTPUT_VERB_FORMS = {
      "emit": ("emit", "emits", "emitted", "emitting"),
      "render": ("render", "renders", "rendered", "rendering"),
      "output": ("output", "outputs", "outputted", "outputting"),
      "print": ("print", "prints", "printed", "printing"),
      "display": ("display", "displays", "displayed", "displaying"),
  }

  _OUTPUT_VERB_RE = re.compile(
      "|".join(
          r"\b" + re.escape(form) + r"\b"
          for forms in _OUTPUT_VERB_FORMS.values()
          for form in forms
      )
  )


  def _is_illustrative_output_exempt(lowered_line: str) -> bool:
      """Return True when ``lowered_line`` (already lowercased) contains any `_OUTPUT_VERB_FORMS`
      form anywhere on the line, independent of the token's own position -- structurally a
      single-marker line-wide presence test, like the `_CITATION_MARKERS` substring check, not a
      two-set AND-pairing like `_is_prohibition_exempt`'s negation-word-plus-verb-form gate. Exists
      because a line such as "an answer emitting the bare `README.md`, never `./README.md`" names
      the token as the function's rendered *output value*, not a file it reads.
      """
      return bool(_OUTPUT_VERB_RE.search(lowered_line))
  ```

  Wire it into `_check_context_completeness`'s per-token exemption chain by inserting a new
  `continue` guard immediately after Card 2's newly-added literal-enumeration-exemption guard and
  before the `if is_path_shaped:` line:

  ```python
                      # Illustrative-output exemption: the line describes a rendered/emitted output
                      # value, not a file read dependency.
                      if _is_illustrative_output_exempt(lowered_line):
                          continue
  ```

  Add a new item `13.` to the same docstring numbered exemption list, immediately after item `12.`
  from Card 2, worded:
  `13. Illustrative-output framing: a line naming a rendered/emitted/printed/displayed/output value
  (e.g. "emitting the bare \`x.md\`") cites the string as a described output, not a read dependency.`
- **Commit:** `feat(plan-validate): add illustrative-output context-completeness exemption`

## Batch Tests

`verify:` runs `test-plan-validate.py` directly (a single test file, not the unbounded `run-all.py`)
so this batch's edits to `_check_context_completeness` are checked against the file's existing 200+
tests before batch 2 adds this batch's own new tests on top — a regression backstop confirming none
of the ten pre-existing exemptions broke. Batch 2
(`02-context-completeness-exemptions-tests.md`) adds the new tests that actually exercise cards 1-3's
three new exemptions; this batch's own `verify:` cannot exercise them yet, since they don't exist
until batch 2 runs.
