# Batch: parent-branch-identity

```yaml
task: "mill-finalize/mill-merge corrupt or mishandle _mill/status.md and task_dir on stacked branches"
batch: parent-branch-identity
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-parent-branch.py
depends-on: []
```

## Batch Scope

Add the shared `expected_slug` mechanism to `_parent_branch.py` that every other batch in
this plan builds on. This is the root batch — no other batch touches this file, and every
other batch's SKILL.md edits reference the signature this batch establishes. The external
interface the next batches consume: `resolve(status_path, *, interactive=True,
expected_slug=None)` and `resolve_for_codeguide(status_path, *, expected_slug=None)`, both
already documented in `_mill/discussion.md`'s `identity-check-scope` Decision.

## Cards

### Card 1: Add expected_slug identity check to _parent_branch.py

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add `expected_slug: str | None = None` as a keyword-only parameter to
    `_read_parent_from_status(status_path, *, expected_slug=None)`. This function already
    scans the first fenced ` ```yaml ` block line-by-line for a `parent:` row; add a
    second pass over the same scanned lines (or extend the single pass) that also looks
    for a `slug:` row, using the identical strip/quote-stripping logic already applied to
    `parent:`'s value. If `expected_slug` is not `None` AND a `slug:` row is found AND its
    stripped value does not equal `expected_slug`: return `None` — the exact same return
    value this function already produces when `parent:` is missing entirely. If no
    `slug:` row is found in the block (or `expected_slug` is `None`), the check is a
    no-op and the function's existing behavior (return the `parent:` value or `None`)
    is unchanged.
  - Add `expected_slug: str | None = None` as a keyword-only parameter to
    `resolve(status_path, *, interactive=True, expected_slug=None)`. Thread it into the
    internal `_read_parent_from_status(status_path, expected_slug=expected_slug)` call.
    No other change to `resolve`'s prompt-or-raise logic — a mismatch simply makes
    `_read_parent_from_status` return `None`, which `resolve` already handles today as
    "no `parent:` row".
  - Add `expected_slug: str | None = None` as a keyword-only parameter to
    `resolve_for_codeguide(status_path, *, expected_slug=None)`. Thread it into the
    internal `resolve(status_path, interactive=False, expected_slug=expected_slug)` call.
    No change to its `try`/`except ParentBranchError: return None` shape.
  - Update the docstrings of all three functions to document the new parameter and its
    "mismatch is treated exactly like the row/field being absent" semantics. Update the
    module-level docstring's "Public API" summary to include the new keyword arg in each
    signature line.
  - Do not change `ParentBranchError` itself, and do not add any new exception type.
  - Every default is `None` — no caller that omits the new kwarg observes any change in
    behavior. This is the batch's own regression contract, verified by Card 2.
- **Commit:** `fix(mill): add expected_slug identity check to _parent_branch resolvers`

### Card 2: Add expected_slug test coverage to test-parent-branch.py

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-parent-branch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a status.md fixture with both `slug: demo-task` and `parent: main` in its yaml
    block. Assert `resolve(sp, interactive=False, expected_slug="demo-task")` returns
    `"main"` — matching slug passes through unaffected.
  - Using the same fixture, assert `resolve(sp, interactive=False,
    expected_slug="other-task")` raises `ParentBranchError`, and that the exception
    message contains the substring `"No parent:"` — i.e. it is asserted identically to
    the file's existing "resolve raises on missing parent non-interactive" case, proving
    a slug mismatch is indistinguishable from a missing `parent:` row.
  - Add a status.md fixture with `parent: main` but NO `slug:` row at all. Assert
    `resolve(sp, interactive=False, expected_slug="anything")` still returns `"main"` —
    an absent `slug:` row never triggers a mismatch (the check only fires when the field
    is present and differs).
  - Add matching-slug and mismatched-slug cases for `resolve_for_codeguide`: matching
    slug returns `"main"`; mismatched slug returns `None` (not a raised exception --
    `resolve_for_codeguide` already swallows `ParentBranchError`).
  - Every assertion already present in this file before this card (the four `resolve` /
    `resolve_for_codeguide` calls with no `expected_slug` argument) must continue to
    pass completely unmodified — do not alter their fixtures or expected values. This is
    the regression guard for the default-`None`-preserves-behavior contract from Card 1.
- **Commit:** `test(mill): cover expected_slug identity check in _parent_branch tests`

## Batch Tests

`test-parent-branch.py` covers both the pre-existing `_parent_branch` behavior and the
new `expected_slug` matching/mismatched/absent-slug-row cases end-to-end against real
tempfile status.md fixtures (no mocks). No other test file is affected by this batch.
