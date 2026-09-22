# Batch: dispatch-directive

```yaml
task: 'Fix prose skill: staleness rule and missing loads'
batch: dispatch-directive
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-language-skills-directive.py
depends-on: []
```

## Batch Scope

This batch makes `prose` reach the two dispatched agents that can load it: the per-batch implementer and the per-batch fixer.
Both briefs render `<LANGUAGE_SKILLS>` and both list `Skill` in their `## Tools` section, so naming the skill in `_agent_dispatch.language_skills_directive()` is the whole fix — neither template is edited.

Card 5 lands the assertions first and card 6 lands the function change, so the tree is red between the two commits by design (see the overview's `tdd-cards-leave-the-tree-red-between-commits` Shared Decision).
`verify:` runs at the batch boundary, where the batch is green.

The change also forces a second, easily-missed edit: the function's no-recognized-language branch currently renders the singular sentence "load and follow this skill (non-optional): {skills[0]}", which would silently drop `code-quality` once the unconditional list holds two entries.

## Cards

### Card 5: Assert `prose` in every `language_skills_directive` behaviour test

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a `` assert "`prose`" in directive `` check to each of the six behaviour tests in `plugins/mill/unit_tests/test-language-skills-directive.py` — `test_go_files_only`, `test_python_files_only`, `test_csharp_files_only`, `test_mixed_languages`, `test_no_recognized_languages`, and `test_context_excluded` — placing it beside each test's existing `` assert "`code-quality`" in directive `` line and giving it a matching failure message.
  Also add the assertion to `test_move_only_batch_detects_go_language`, which carries the same `code-quality` assertion.

  In `test_mixed_languages`, add a once-only count assertion mirroring the existing `code-quality` one:

  ```
      count_prose = directive.count("`prose`")
      assert count_prose == 1, f"prose should appear once, got {count_prose}"
  ```

  Assert the backtick-wrapped form `` `prose` `` rather than the bare word, so the check cannot be satisfied by the word "prose" appearing in surrounding directive prose.

  Fix `test_no_recognized_languages`' docstring, which currently claims "detects code-quality only": it must name both unconditional skills.
  Update the module docstring's `Covers:` list on the same point — its "Non-recognized languages (md, yaml): code-quality only" line is now wrong for the same reason.

  Leave `test_context_excluded`'s `` assert "Go" not in directive `` untouched;
  the added skill name contains no `Go` substring, so it still holds.
  Do not edit `plugins/mill/scripts/_agent_dispatch.py` in this card — card 6 owns that change, and these assertions are expected to fail until it lands.
- **Commit:** `test(dispatch): assert prose in language-skills directive (failing until card 6)`

### Card 6: Add `prose` to `language_skills_directive`'s unconditional skills

- **Context:**
  - `plugins/mill/templates/implementer-brief.md`
  - `plugins/mill/templates/fixer-batch-brief.md`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `language_skills_directive()` in `plugins/mill/scripts/_agent_dispatch.py`, seed the skills list with `prose` ahead of `code-quality`:

  ```
      skills = ["`prose`", "`code-quality`"]
  ```

  `prose` goes in the unconditional group, never in a per-language group — it is language-agnostic, exactly like `code-quality`, while the `{prefix}-comments` / `{prefix}-testing` entries appended below it vary by file suffix.
  Do not add `conversation`: it governs live chat with an operator, which a dispatched implementer never has.

  Fix the no-recognized-language branch, which now renders a wrong sentence and drops a skill. It currently reads:

  ```
        prose = f"Before editing any file, load and follow this skill (non-optional): {skills[0]}"
```

  It must render every entry in the list and use the plural noun:

  ```
        prose = f"Before editing any file, load and follow these skills (non-optional): {', '.join(skills)}"
```

  The detected-language branch above it already joins the full list and needs no change.

  Update two docstrings to match.
  `language_skills_directive`'s own docstring says "plus ``code-quality`` for all batches" — it must name both unconditional skills.
  The module docstring's summary line for the same function says "naming the required language skills plus code-quality" — same correction.

  Neither `plugins/mill/templates/implementer-brief.md` nor `plugins/mill/templates/fixer-batch-brief.md` is edited: both render `<LANGUAGE_SKILLS>` and inherit the change from the function.
  They are listed above so the implementer can confirm that inheritance holds before concluding the card.
- **Commit:** `feat(dispatch): name prose in the language-skills directive`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-language-skills-directive.py`, the only test covering `language_skills_directive()`.
The `--only` token is the test file card 5 edits, so the `verify-unrelated-test-file` check exempts it as directly touched.

The file's nine tests cover every scenario the change can affect: `prose` present for a Go-only, Python-only, C#-only, mixed, and Move-only batch;
present for a batch with no recognized language, where it and `code-quality` are the entire list;
present exactly once in a mixed batch;
and still rendering into both `implementer-brief.md` and `fixer-batch-brief.md` via the two render tests, which also re-confirm `Skill` appears in each brief's `## Tools` section.
