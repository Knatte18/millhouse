# Batch: structural-exemption-tests

```yaml
task: '_plan_validate.py context-completeness check: false positives across gitignored/quoted/negated/citation/cross-reference prose'
batch: structural-exemption-tests
number: 2
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: [1]
```

## Batch Scope

This batch adds unit coverage for the four path-shape exemptions batch 1 introduced — directory-intent, out-of-repo, gitignored, forward cross-card Creates — plus one signature-compatibility test for the new keyword-only parameter. It is one batch because all five cards edit the same test file and share one fixture idiom. Batch 3 consumes nothing from it beyond the convention that a new test function must also be registered in the `tests` list inside `main`.

Batch-local decisions beyond the overview's Shared Decisions:

- Every card writes both a clean case and a dirty case. A card that adds only clean cases is incomplete, because the clean case alone cannot detect an over-broad exemption.
- Fixture path spellings in these tests must not collide with real repository files, or the fixture will resolve against the checkout and test the wrong thing. Use `fixtures/alpha.py` and `fixtures/beta.md` as the stand-in spellings; neither exists in this repository.
- Copy the surrounding file's established fixture idiom rather than inventing one: build a temporary plan directory, write an overview plus one or more batch files into it, call the validator's public entry point, filter the returned list by check name, and assert the expected count. Roughly fifty sibling `test_check_context_completeness_*` functions in the same file already demonstrate this shape, and the file is in this batch's `Edits:`, so they are directly readable.

## Cards

### Card 9: Directory-intent exemption tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three test functions covering the trailing-slash directory-intent exemption, and register each in the `tests` list inside `main` at the bottom of the file. First, a clean case whose card Requirements backticks a trailing-slash token naming a real directory inside the fixture tree, asserting zero context-completeness findings. Second, a clean case whose trailing-slash token names a path that exists on disk as a regular file rather than a directory, asserting zero findings — this is the case the pre-existing on-disk-type filter does not cover, and it is the one the repository's own linked-worktree layout produces, where the repository's own dot-git entry is a regular file (no file read needed). Third, a dirty case using the same path with the trailing slash removed and the token absent from the card's own reference fields, asserting exactly one context-completeness finding. Follow the naming convention of the surrounding tests, using the `test_check_context_completeness_` prefix with a `_clean_` or `_dirty_` segment.
- **Commit:** `test(plan-validate): cover trailing-slash directory-intent exemption`

### Card 10: Out-of-repo literal exemption tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add five test functions covering the out-of-repo exemption, registering each in the `tests` list inside `main`. Three clean cases: a card Requirements backticking an absolute POSIX-rooted token; one backticking a home-relative token beginning with a tilde; and one backticking a relative token that escapes the fixture roots through parent-directory segments and resolves to a real file outside them. Each asserts zero context-completeness findings. One dirty case: an ordinary in-repo relative token that resolves inside the fixture root and is absent from the card's own reference fields, asserting exactly one finding. One further dirty case, which is the regression this exemption most easily breaks: a token spelled with the literal `wiki/` prefix, resolving under a wiki root that lies outside both the project root and the git root, and absent from the card's own reference fields — assert exactly one finding, proving the wiki carve-out holds and that a legitimate wiki dependency is still reported. Use `wiki/alpha.md` as that spelling and create the corresponding file under the fixture's wiki root; the validator's public entry point accepts the wiki root as a keyword argument, which the surrounding tests already demonstrate.
- **Commit:** `test(plan-validate): cover out-of-repo exemption and wiki carve-out`

### Card 11: Gitignored exemption tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add three test functions covering the git-ignored exemption, registering each in the `tests` list inside `main`. These are the only tests in this batch that need a real repository, because the exemption shells out to git's own ignore matcher and a stubbed matcher would verify nothing: initialise a git repository inside the temporary fixture directory, write a gitignore file that ignores a scratch directory, and create the file under it. First, a clean case whose card Requirements backticks the ignored path with the file present on disk, asserting zero context-completeness findings. Second, a dirty case with an identically-shaped non-ignored file present on disk in the same fixture and absent from the card's own reference fields, asserting exactly one finding. Third, a clean case with the ignored path absent from disk, asserting zero findings — this one passes before the change as well, and exists to pin that the verdict no longer depends on whether the file happens to exist on the running machine. Keep every fixture under the repository's own scratch conventions and never under a system temporary directory.
- **Commit:** `test(plan-validate): cover git-ignored path exemption`

### Card 12: Forward cross-card Creates exemption tests

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add six test functions covering the forward cross-card Creates exemption, registering each in the `tests` list inside `main`. One clean case: an earlier card's Requirements backticks `fixtures/alpha.py`, which is not on disk and is a later card's Creates target, asserting zero context-completeness findings. One dirty case in the opposite direction: the declaring card comes first and the referencing card comes later, asserting exactly one finding — the genuine dependency this exemption must never suppress. One dirty case for the lowest-key rule: the same token is declared as a Creates target by two cards, and a third card positioned between them references it, asserting exactly one finding. One dirty case for the on-disk narrowing: the token is a later card's Creates target but the file already exists on disk, asserting exactly one finding. One clean case and one dirty mirror for the composite ordering key, written as two separate test functions per this file's one-fixture-one-assertion convention: build a two-batch fixture where the first batch by filename holds the higher card numbers and the second holds the lower ones, which the card-numbering check permits because it enforces only within-batch sequencing and cross-batch uniqueness (no file read needed) — with the declaration in the second batch file and the reference in the first, assert zero findings; with the arrangement reversed, assert exactly one. That pair is what pins that batch order and not the bare card number decides direction.
- **Commit:** `test(plan-validate): cover forward cross-card Creates exemption and ordering key`

### Card 13: Direct-call signature compatibility test

- **Context:**
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add one test function that calls the check function directly rather than through the validator's public entry point, and register it in the `tests` list inside `main`. Its positional parameter list is, in order: the batch file list, the project root, the optional root sub-path, the plan-wide Creates union, the Deletes union, the Moves source set, and the Moves target set; the keyword-only parameters are the wiki root, the git root, and the new Creates-to-card-key mapping added by batch 1 (signature inlined, no file read needed). Call it with the positional list and without the new mapping keyword, and assert that a card referencing another card's Creates target still produces exactly one finding — proving the parameter's default is the no-exemption behavior. State in the test's docstring that no direct-call test existed before this one, so this is new coverage pinning the default rather than preservation of an existing contract. Import the check function using the same module-import idiom the file already uses for the validator's public entry point.
- **Commit:** `test(plan-validate): pin direct-call signature and forward-map default`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-plan-validate.py` directly, which is both the file this batch edits and the file that exercises the changed check. A pass means the eighteen new test functions — three from card 9, five from card 10, three from card 11, six from card 12, and one from card 13 — hold against batch 1's implementation and that no existing test regressed. The dirty cases carry most of the value here: card 10's `wiki/`-prefixed case and card 12's reversed-direction, duplicate-declaration, on-disk, and reversed-batch-order cases are each aimed at a specific way an exemption could be written too broadly, and a failure in any of them means batch 1's rule needs narrowing rather than the test needs relaxing. Card 11 is the only card that shells out to real git, which is deliberate: a stubbed ignore matcher would assert nothing about the behavior under test.
