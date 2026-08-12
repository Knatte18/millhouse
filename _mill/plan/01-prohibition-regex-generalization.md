# Batch: prohibition-regex-generalization

```yaml
task: '_plan_validate: context-completeness fires on forbidding/explanatory file mentions'
batch: prohibition-regex-generalization
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

Replace `_plan_validate.py`'s enumerated `_PROHIBITION_MARKERS` phrase-tuple list (9 fixed phrases) with a negation-word-set + verb-word-set regex predicate, and add a plan-authoring guidance note to `mill-plan/SKILL.md` steering `mill-plan`'s own Requirements-prose phrasing away from the two known limitations (nested-bullet prohibitions, double negatives) this redesign does not fix. This is one batch because both cards implement the same `_mill/discussion.md` decision (see `00-overview.md`'s Shared Decisions) and the SKILL.md note directly documents the code's own known limitations — splitting them would force the doc card to re-read the code card's output for no benefit. The next batch (`regression-tests`) depends on this batch's `_plan_validate.py` change and adds its test coverage.

## Cards

### Card 1: Replace `_PROHIBITION_MARKERS` with negation+verb word-set regex predicate

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_plan_validate.py`, delete the `_PROHIBITION_MARKERS` tuple definition (currently the 9-phrase tuple immediately following the `# context-completeness check (#742)` section header, just above `_CITATION_MARKERS`). Replace it with the following three module-level names, inserted in the same location (immediately before `_CITATION_MARKERS`, which stays untouched):

  ```python
  # Negation words/phrases (lowercased, word-boundary matched): a Requirements: sentence needs at
  # least one of these AND at least one verb form from _PROHIBITION_VERB_FORMS to be
  # prohibition-exempt.
  _PROHIBITION_NEGATIONS = (
      "do not", "don't",
      "does not", "doesn't",
      "never",
      "must not",
      "cannot", "can't",
      "shall not",
      "won't",
      "forbid", "forbids", "forbidden",
      "not",
  )

  # Verb base forms mapped to their full inflected-form set (base, third-person, past, gerund, plus
  # hand-added irregulars) -- a Requirements: sentence pairs one of these forms with a negation from
  # _PROHIBITION_NEGATIONS to be prohibition-exempt. Silent-e-drop (change/use/reference/include/
  # update/remove/delete/rename/move/create/cite), y->i (modify), sibilant -es (touch), and write's
  # fully suppletive forms (wrote/written) are derived by hand per standard English orthography, not
  # by naive suffix concatenation. "read" collapses to 3 forms (base/-s/-ing) since its past tense is
  # spelled identically to its base form -- "readed" is not a word.
  _PROHIBITION_VERB_FORMS = {
      "touch": ("touch", "touches", "touched", "touching"),
      "change": ("change", "changes", "changed", "changing"),
      "modify": ("modify", "modifies", "modified", "modifying"),
      "edit": ("edit", "edits", "edited", "editing"),
      "add": ("add", "adds", "added", "adding"),
      "link": ("link", "links", "linked", "linking"),
      "read": ("read", "reads", "reading"),
      "use": ("use", "uses", "used", "using"),
      "reference": ("reference", "references", "referenced", "referencing"),
      "include": ("include", "includes", "included", "including"),
      "update": ("update", "updates", "updated", "updating"),
      "remove": ("remove", "removes", "removed", "removing"),
      "delete": ("delete", "deletes", "deleted", "deleting"),
      "alter": ("alter", "alters", "altered", "altering"),
      "rename": ("rename", "renames", "renamed", "renaming"),
      "move": ("move", "moves", "moved", "moving"),
      "create": ("create", "creates", "created", "creating"),
      "write": ("write", "writes", "wrote", "writing", "written"),
      "mention": ("mention", "mentions", "mentioned", "mentioning"),
      "cite": ("cite", "cites", "cited", "citing"),
  }

  _PROHIBITION_NEGATION_RE = re.compile(
      "|".join(r"\b" + re.escape(w) + r"\b" for w in _PROHIBITION_NEGATIONS)
  )
  _PROHIBITION_VERB_RE = re.compile(
      "|".join(
          r"\b" + re.escape(form) + r"\b"
          for forms in _PROHIBITION_VERB_FORMS.values()
          for form in forms
      )
  )


  def _is_prohibition_exempt(lowered_line: str) -> bool:
      """Return True when ``lowered_line`` (already lowercased) pairs a negation word/phrase from
      _PROHIBITION_NEGATIONS with a verb form from _PROHIBITION_VERB_FORMS anywhere on the line
      (line-wide match, not positionally adjacent -- same granularity as the citation-marker check).

      Known limitations (not handled -- see _mill/discussion.md):
      - Nested-bullet/multi-line prohibitions (negation on a parent bullet, path on a child bullet)
        are not detected -- this check is scoped to a single physical line.
      - Double-negative phrasing ("do not skip touching `foo.py`", "do not forget to read `bar.py`")
        is misdetected as exempt even though the path SHOULD be touched/read -- this is a lexical
        word-set match, not a semantic parse.
      """
      return bool(_PROHIBITION_NEGATION_RE.search(lowered_line)) and bool(
          _PROHIBITION_VERB_RE.search(lowered_line)
      )
  ```

  Then, in `_check_context_completeness`, locate the prohibition-marker exemption block (the `lowered_line = line.lower()` assignment immediately followed by `if any(marker in lowered_line for marker in _PROHIBITION_MARKERS): continue`, directly above the citation-marker exemption block). Keep the `lowered_line = line.lower()` assignment (the citation-marker check below it still consumes `lowered_line` unchanged) but replace the `if any(...)` line with:

  ```python
                      if _is_prohibition_exempt(lowered_line):
                          continue
  ```

  Do not modify `_CITATION_MARKERS` or the citation-marker exemption block that follows — out of scope per `_mill/discussion.md`'s Decisions.

  Do not remove or rename `_PATH_CANDIDATE_EXTENSIONS`, `_extract_requirements_text`, or `_card_own_reference_set` — only the prohibition-marker predicate and its call site change.
- **Commit:** `fix(plan-validate): generalize context-completeness prohibition detection to negation+verb word sets`

### Card 2: Document the redesign's known limitations in `mill-plan/SKILL.md`'s plan-authoring conventions

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/skills/mill-plan/SKILL.md`'s `## Principles` section, add one new bullet immediately after the existing `**Express renames as \`Moves:\` pairs**` bullet (the last bullet in that section, ending "...using stable identifiers.") and before the `## Board discipline` heading:

  ```markdown
  - **Phrase Requirements: prohibitions on one line; avoid double negatives** — `_plan_validate.py`'s `context-completeness` check exempts a prohibition via a same-line, lexical word-set match (a negation word/phrase paired with a verb form, anywhere on one physical line), not a structural or semantic parse.
    Write "Do not touch `foo.py`" on a single line (negation, verb, and path together) rather than a nested-bullet form (negation on a parent bullet, path on a child bullet) — the check never looks across bullet lines.
    Avoid double-negative phrasing such as "do not skip touching `foo.py`" or "do not forget to read `bar.py`" — the check misreads these as prohibited (a false exemption) even though the path SHOULD be touched/read.
    State prohibitions directly instead.
  ```

  This bullet documents the two known limitations from this task's discussion notes (nested-bullet/multi-line prohibitions, double-negative phrasing) so `mill-plan`'s own future Requirements-prose generation avoids triggering either gap in practice.
- **Commit:** `docs(mill-plan): steer Requirements prose around context-completeness prohibition-check limitations`

## Batch Tests

`verify:` re-runs the full existing `test-plan-validate.py` suite (no `--only` scoping — this single file already covers the whole `_plan_validate` module, so scoping would just be `--only test-plan-validate.py`, equivalent to running the file directly). This batch's own new tests are added in the next batch (`regression-tests`); this batch's verify instead confirms the regex-generalization in Card 1 does not regress any of the pre-existing `context-completeness` tests — in particular `test_check_context_completeness_clean_prohibition_marker` (the `"forbid"` + gerund-`touching` baseline) and `test_check_context_completeness_clean_prohibition_marker_change_modify` (`"do not change"` / `"must not modify"`), both of which exercise the exact predicate this card rewrites.
