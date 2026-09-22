# Batch: load-directive-sites-and-test

```yaml
task: 'Fix prose skill: staleness rule and missing loads'
batch: load-directive-sites-and-test
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-load-directive-convention.py
depends-on: []
```

## Batch Scope

This batch fixes the one remaining load-directive site in the shipped surface and adds the regression guard that stops the defect returning.

A sweep of `plugins/*/skills/**/SKILL.md` and `plugins/mill/templates/*.md` for `mill:conversation` finds six hits.
Four are load directives: `mill-start`, `mill-plan`, and `mill-go-base` already name `mill:prose` first and are correct;
`plugins/mill/skills/handoff/SKILL.md` names `mill:conversation` alone and is the defect.
The other two — `mill-self-report`'s citation of the numbered-options rule and `workflow`'s routing-table row — are referential, carry no load verb, and are the cases the test's discrimination rule must not fire on.
No template currently mentions `mill:conversation` at all, so the template half of the walk passes vacuously today and exists to catch a future one.

Card 7 lands before card 8 so the test never fails for a reason the next commit removes.

## Cards

### Card 7: Make `handoff`'s emitted first line load `prose` before `conversation`

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/handoff/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/handoff/SKILL.md`, the line reading

  ```
The document's first line instructs the next agent to load `mill:conversation` before reading the rest of the document.
```

  must become

  ```
The document's first line instructs the next agent to load `mill:prose`, then `mill:conversation` before reading the rest of the document.
```

  The wording "load `mill:prose`, then `mill:conversation`" is fixed and matches the Step 0 directive in `plugins/mill/skills/mill-start/SKILL.md` verbatim apart from capitalisation;
  card 8's convention test anchors on exactly this phrasing, so a paraphrase such as "load `mill:prose` and also `mill:conversation`" fails the test.

  Leave the earlier line in the same file that mentions "`conversation`'s file-writing rule" exactly as it is.
  That is a referential mention with no load verb, and the test is built to ignore it.
  Do not edit `plugins/mill/skills/mill-start/SKILL.md`, which is listed above only as the wording reference.
- **Commit:** `fix(handoff): load prose before conversation in the emitted document`

### Card 8: Add the load-directive convention test

- **Context:**
  - `plugins/mill/skills/handoff/SKILL.md`
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/workflow/SKILL.md`
  - `plugins/mill/skills/mill-self-report/SKILL.md`
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-language-skills-directive.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-load-directive-convention.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-load-directive-convention.py`, following the plain-function-plus-`main()` structure and the `HUB = Path(__file__).resolve().parent.parent.parent.parent` root derivation that `plugins/mill/unit_tests/test-language-skills-directive.py` already uses, so `plugins/mill/unit_tests/run-all.py` picks it up unchanged.

  Expose the rule as a pure function taking the file's text and returning a failure reason string or `None`, so the behaviour can be exercised against fixtures without depending on which real files happen to exist:

  ```
  def check_text(text: str) -> str | None:
  ```

  Its three steps, in order:

  1. **Discrimination.** The file is in scope only if some line contains the literal `mill:conversation` **and** a load verb on the same line. Recognise the load verbs `Load`, `load`, `loads`, and `loading` on a word boundary. Do not treat `follow`, `see`, `per`, or `use` as load verbs — `mill-start/SKILL.md` and `mill-self-report/SKILL.md` both cite `mill:conversation` with those words and must stay out of scope. A file with no such line returns `None`.
  2. **Co-presence.** An in-scope file whose text does not contain `mill:prose` anywhere fails, with a reason naming the offending line.
  3. **Order.** An in-scope file must also contain at least one line matching the canonical directive pattern

     ```
     [Ll]oad\s+`mill:prose`\s*,?\s*(?:then|and)\s+`mill:conversation`
     ```

     A file that satisfies co-presence but produces no canonical line fails — this is what makes a directive naming `mill:conversation` ahead of `mill:prose` a failure rather than a pass. Anchoring on the canonical wording instead of a per-line positional comparison is required, not stylistic: see the overview's `convention-test-anchors-on-canonical-wording` Shared Decision for why every alternative fails a file that is currently correct.

  Write fixture-driven tests for five scenarios, each building its text in memory or in a `tempfile.TemporaryDirectory()` rather than reading a repo file:

  - a correct canonical directive passes;
  - a load directive naming `mill:conversation` with no `mill:prose` anywhere fails;
  - a referential mention of `mill:conversation` with no load verb passes;
  - a load directive naming `mill:conversation` before `mill:prose` fails;
  - a correct canonical directive followed later in the same text by a bare referential mention of `mill:conversation` passes — this is the case that separates the order check from the discrimination rule.

  Add one tree-walk test that runs `check_text` over every file matched by `plugins/*/skills/**/SKILL.md` and `plugins/mill/templates/*.md`, relative to `HUB`, and fails with the offending paths and reasons collected into one message.
  Do not walk `.claude/skills/`, which is repo-local and not shipped, and do not walk `plugins/mill/scripts/*.py` — script-level prompt builders are covered by `plugins/mill/unit_tests/test-language-skills-directive.py`, which asserts rendered content rather than pattern-matching source.

  Do not assert on the wording of any style block or on any other prose content;
  the only thing this file tests is the load-directive convention.
- **Commit:** `test: add load-directive convention guard for prose before conversation`

## Batch Tests

`verify:` runs the new `plugins/mill/unit_tests/test-load-directive-convention.py` alone.
The `--only` token is the file card 8 creates, so the `verify-unrelated-test-file` check exempts it as directly touched.

The five fixture tests cover the discrimination rule and the order rule in isolation;
the tree-walk test covers the real shipped surface and is what turns card 7's fix into a permanent guard.
Running the two cards in order means the tree-walk test is green the first time it executes.
