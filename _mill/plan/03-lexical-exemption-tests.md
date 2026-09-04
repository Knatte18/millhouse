# Batch: lexical-exemption-tests

```yaml
task: '_plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose'
batch: lexical-exemption-tests
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [2]
```

## Batch Scope

This batch adds unit coverage for the three line-level exemptions and the escape marker batch 1 introduced — negation phrasing, contrast citation, quoted material together with the fence-aware extraction swap, and the mentioned-not-read marker. It depends on batch 2 rather than directly on batch 1 because both batches edit the same test file and must therefore run sequentially, not because it consumes anything batch 2 produces.

Batch-local decisions beyond the overview's Shared Decisions:

- Same clean-plus-dirty rule as batch 2, and for the same reason.
- These four exemptions run before the path and symbol branches split, so each clean case should use a path-shaped token for clarity; there is no need to duplicate every case against a symbol token, because the exemption cannot distinguish them.
- Use `fixtures/alpha.py` and `fixtures/beta.md` as fixture spellings, as batch 2 does, and create them inside the fixture tree when a case needs the token to resolve.

## Cards

### Card 14: Negation-phrase exemption tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add four test functions covering the non-dependency negation phrase matcher, registering each in the `tests` list inside `main`. Three clean cases, one per supported template, each with the token resolving inside the fixture tree and absent from the card's own reference fields, asserting zero context-completeness findings: a Requirements line of the form "so no `fixtures/alpha.py` is involved"; one of the form "runs without `fixtures/alpha.py`"; and one of the form "`fixtures/alpha.py` is not needed". One dirty case: a Requirements line that contains the word "no" elsewhere in the sentence and also names the token as a genuine read dependency, matching none of the three templates, asserting exactly one finding. That dirty case is the whole reason the matcher is positional rather than a widened line-wide word set, so its assertion must not be relaxed to make an implementation pass.
- **Commit:** `test(plan-validate): cover non-dependency negation phrase exemption`

### Card 15: Contrast-citation exemption tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add four test functions covering the contrast-citation exemption, registering each in the `tests` list inside `main`. One clean case for the both-sides rule: a Requirements line of the form "named `fixtures/alpha.py` rather than the more obvious `fixtures/beta.md`", with both files present in the fixture tree and neither in the card's own reference fields, asserting zero context-completeness findings — both tokens must be exempt, so a result of one finding fails the card. One clean case using the second marker, "instead of", in the same shape. One dirty case for the clause boundary: a Requirements line of the form "Read `fixtures/alpha.py`, rather than guessing at the signature", where a comma separates the token from the marker, asserting exactly one finding. One further dirty case with the marker present on the line but the token in a clearly separate sentence, also asserting exactly one finding. The two dirty cases are what justify the positional requirement over a plain line-wide substring match, so neither may be weakened to accommodate an implementation.
- **Commit:** `test(plan-validate): cover contrast-citation exemption adjacency rule`

### Card 16: Quoted-material and fence-aware extraction tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add six test functions covering quoted-material containment and the fence-aware extraction swap, registering each in the `tests` list inside `main`. Two clean cases: a token named only inside a fenced block within the card's Requirements, and a token named only on a blockquote line whose first non-whitespace character is a greater-than sign — each asserting zero context-completeness findings with the token resolving in the fixture tree and absent from the card's own reference fields. Two dirty cases: the same token named on an ordinary prose line in the same card, and a token named on a prose line positioned after a fenced block has closed, each asserting exactly one finding — the second proves the fence state is toggled off rather than latched on. Two cases for the extraction swap: one clean case whose Requirements fence quotes a bold field-header-shaped bullet line and then, still inside the same fence, names a resolvable token, asserting zero findings, which proves the body was not truncated at the fake boundary; and one dirty case where a genuine bold field header follows the closed fence and a resolvable token appears on a line beyond it, asserting zero context-completeness findings because that line lies outside the Requirements field entirely — pair it with an assertion that a token on a line before that header still produces its finding, so the test cannot pass by swallowing the whole card.
- **Commit:** `test(plan-validate): cover quoted-material exemption and fence-aware extraction`

### Card 17: Escape-marker tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add two test functions covering the explicit escape marker, registering each in the `tests` list inside `main`. One clean case: a Requirements line naming a resolvable token absent from the card's own reference fields and carrying the phrase "mentioned, not read" on the same physical line, asserting zero context-completeness findings. One dirty case: the identical line with that phrase removed, asserting exactly one finding. Keep both fixtures otherwise byte-identical so the marker is the only variable under test.
- **Commit:** `test(plan-validate): cover mentioned-not-read escape marker`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-plan-validate.py` directly, the file this batch edits and the file that exercises the changed check. A pass means the sixteen new test functions hold against batch 1's implementation and that batch 2's tests plus the pre-existing suite still pass. The dirty cases are the load-bearing assertions in every card here: card 14's non-template negation line, card 15's comma-separated and separate-sentence lines, and card 16's after-the-fence line each target a specific way a lexical rule could be written too loosely. A failure in any of them means batch 1's rule is over-broad and must be narrowed; relaxing the assertion instead would reintroduce the false negatives this task's design explicitly rejects.
