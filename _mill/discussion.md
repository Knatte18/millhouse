# Discussion: _plan_validate false positives block plan authoring

```yaml
task: _plan_validate false positives block plan authoring
slug: mill-plan-validate-false-positives
status: discussing
parent: main
```

## Problem

`_plan_validate.py` runs two checks — `context-completeness` and
`requirements-quote-indent-drift` — during `/mill-plan` authoring
(both at the mill-plan self-gate and at `millpy-review-plan.py`'s
step 1.5). Both checks are currently over-eager and produce false
positives that block otherwise-correct plans, forcing authors to
reword or de-backtick perfectly good prose to dodge the checker. Six
GitHub issues (#766, #760, #756, #750, #761, #754), filed across four
different mill-plan sessions between 2026-07-30 and 2026-08-01, each
capture a distinct repro of one of these false positives. This task
fixes the two checks' heuristics so all six repro cases pass cleanly
while true positives (genuine missing-Context references, genuine
quote drift) remain caught.

## Scope

**In:**
- `_check_context_completeness` (`plugins/mill/scripts/_plan_validate.py`): stop
  treating an on-disk *directory* as a resolvable file reference, so a
  backtick-wrapped directory/package-prose mention is never flagged
  regardless of Context:/Edits:/etc. membership.
- `_check_requirements_quote_indent_drift`: normalize the extracted
  fence body to drop the closing-fence-delimiter's own trailing
  indentation artifact before any byte-exact or `N`-strip matching.
- Regression unit tests in `plugins/mill/unit_tests/test-plan-validate.py`
  covering all six issues' repro cases.

**Out:**
- Any change to the shared `resolve_existing_paths` helper in
  `_review_common.py` — it stays existence-based (files + directories)
  for its other callers; only `_check_context_completeness`'s own
  resolvability test changes.
- Directory-shape filtering for `creates_union`/`deletes_union`/`moves_targets`
  string-set membership checks — no source issue hits a false positive
  through that path.
- Re-anchoring the `_RE_FENCE_BODY` regex itself (closing ` ``` `
  start-of-line requirement) — the normalization fix below already
  neutralizes the known false positives without touching the regex's
  matching semantics.
- Any other `_plan_validate.py` check not named above (e.g.
  `all-files-touched-mismatch`, `non-existent-path`) — out of scope,
  no reported false positives.
- Nested/embedded triple-backtick fences inside a quoted Requirements
  fence — not reported by any of the six issues; the existing
  non-greedy `_RE_FENCE_BODY` regex's behavior there is unchanged.

## Decisions

### directory-vs-file resolvability in context-completeness

- Decision: in `_check_context_completeness`, after calling
  `resolve_existing_paths(...)`, filter the result to files only —
  `existing_files = [p for p in existing if p.is_file()]` — and use
  `bool(existing_files)` (instead of `bool(existing)`) in the
  `resolvable` boolean:
  ```python
  resolvable = (
      bool(existing_files)
      or stripped_token in creates_union
      or stripped_token in deletes_union
      or stripped_token in moves_targets
  )
  ```
  This is the only code change needed in this check.
- Rationale: `Context:` is documented as a list of *files* the
  implementer reads; a directory can never legitimately go in that
  list, so a directory token can never be "missing" from it. Filtering
  on `is_file()` makes this deterministic regardless of incidental
  on-disk state (fixes #750's `.scratch/`-created-mid-run
  nondeterminism as a side effect — a directory is never a file
  whether or not it exists) and covers every directory-shaped repro in
  #766, #756, and #760 (`internal/gitrepo`, `crucible/`,
  `internal/fabricengine`, `internal/initengine/`, `internal/loomengine`)
  without needing a separate trailing-slash or basename heuristic.
  Verified empirically that `//` (the #760 case) also falls out of
  this fix for free: `Path(project_root) / '//'` resolves to a
  filesystem-root-like directory path under pathlib's absolute-operand
  join semantics, so `.is_file()` is `False` for it too — no separate
  punctuation-shape filter is needed.
- Rejected:
  - A directory allow-list mechanism (extra field/syntax, no source
    issue asks for it).
  - A hardcoded `.scratch/`-only exemption (too narrow — doesn't fix
    #766/#756/#760's directory cases, which aren't gitignore-related).

### quote-indent-drift fence-body normalization

- Decision: in `_check_requirements_quote_indent_drift`, immediately
  after `fence_bodies = _RE_FENCE_BODY.findall(requirements_text)`,
  normalize each `fence_body` before it is used anywhere else in the
  loop:
  ```python
  fence_body = re.sub(r"\n[ \t]*\Z", "", fence_body)
  ```
  Apply this once per fence (e.g. inside the
  `for fence_idx, fence_body in enumerate(fence_bodies, start=1):` loop,
  before the existing "already byte-exact" check). The normalized
  value is what both the byte-exact pre-check and the
  `for n in range(1, 41):` strip-search loop operate on — no other
  logic in the function changes.
- Rationale: `_RE_FENCE_BODY` (`` r"```[^\n]*\n(.*?)```" ``) captures
  everything between the opening fence's newline and the literal
  closing `` ``` ``, which — because the regex isn't line-anchored —
  always includes the closing delimiter's own leading whitespace (0+
  spaces from Markdown list-continuation indentation) as a trailing
  fragment of the captured body. That trailing fragment is never real
  quoted content; it is markdown structure. Stripping it explains and
  fixes both source issues with one change:
  - **#754** (closing-fence indentation on a table's last row):
    the trailing whitespace-only fragment previously broke the
    byte-exact pre-check for genuinely-unchanged content, falling
    through to the `N`-search where an unrelated adjacent-content
    coincidence could spuriously match. With the fragment stripped,
    byte-exact content now byte-exact-matches directly at the
    pre-check, before the `N`-search ever runs.
  - **#761** (mid-line quoted fragment): for a single-content-line
    fence with zero real indentation, the previously-uncleaned body
    carried a trailing `\n` (with no leading-whitespace continuation,
    since the closing fence had none) that could never byte-match
    a mid-line source fragment (the source has no real newline there).
    That forced a fall-through to the `N`-search, where `N=1`
    "succeeded" only as a side effect of `_strip_n_leading_spaces`'s
    `splitlines()`-based reconstruction silently dropping the same
    trailing newline. With the newline stripped up front, the
    byte-exact pre-check now succeeds directly at `N=0` for a true
    zero-indent mid-line quote, and no spurious `N=1` is ever reported.
  - Traced both mechanisms directly against current
    `plugins/mill/scripts/_plan_validate.py` source (`_RE_FENCE_BODY`
    at line 109, `_check_requirements_quote_indent_drift` at line
    1698) — neither issue is fixed by the prior
    `1eb3f98b` commit ("Requirements find/replace fences lose
    byte-exactness under list-nested indentation"), which addressed a
    different symptom (list-continuation indentation *within* the
    quoted content, already covered by the existing `N`-search itself
    and by `test_check_requirements_quote_indent_drift_dirty_list_continuation_indent`).
  - The regex `\n[ \t]*\Z` is guaranteed to match at the end of every
    `fence_body` the current extraction produces, because the body
    always ends with `(last real content)\n(closing-fence's own
    leading whitespace, possibly empty)` — there is no case where this
    substitution is a no-op that accidentally deletes real trailing
    content, since the closing fence delimiter itself is never part of
    the captured group.
- Rejected:
  - Two independent special-cases (one for single-line bodies, one
    re-anchoring the regex) — more surface area for the same
    root cause; harder to reason about as one change.
  - Re-anchoring `_RE_FENCE_BODY` to require `^\s*` + MULTILINE for the
    closing delimiter — touches regex matching semantics more broadly
    (nested-fence, language-tag edge cases) than either issue needs;
    the normalization fix alone fully resolves both without touching
    the regex.
  - Full line-based rewrite of fence extraction (walking `card_lines`
    directly instead of a regex `findall`) — larger surface, no
    correctness gap left to justify it once the normalization fix is
    in place.

### creates_union/deletes_union/moves_targets stay existence-based

- Decision: no directory-shape filtering added to the
  `stripped_token in creates_union` / `deletes_union` / `moves_targets`
  membership checks in `_check_context_completeness`.
- Rationale: those three sets are plan-declared file targets by
  convention (`Creates:`/`Deletes:`/`Moves:` fields document files, not
  directories); none of the six source issues report a false positive
  routed through this path.
- Rejected: applying the same is-directory heuristic there for
  symmetry — no observed bug to fix, adds untested surface area.

## Technical context

- File: `plugins/mill/scripts/_plan_validate.py` (2778 lines).
  - `_check_context_completeness` at line 1471; resolvability logic at
    lines 1553–1566.
  - `resolve_existing_paths` lives in `_review_common.py:963` (shared
    helper — existence-based, files and directories both count as
    "existing"; do not change its behavior).
  - `_RE_FENCE_BODY` at line 109: `` re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL) ``.
  - `_check_requirements_quote_indent_drift` at line 1698; fence-body
    extraction and matching loop at lines 1763–1820.
  - `_strip_n_leading_spaces` at line 1593 — per-line fixed-N strip,
    deliberately not `textwrap.dedent` (see its docstring, referencing
    a prior `trigger-heuristic-near-miss` decision). Unaffected by this
    task's changes; consumes whatever `fence_body` string it's given.
- Both checks are invoked from `run()` around line 2741–2746 with the
  same `batch_files`, `project_root`, `root`, `creates_union`,
  `deletes_union`, `moves_targets`, `wiki_root`, `git_root` arguments
  already threaded through — no signature or call-site changes needed
  for either fix.
- Existing test file: `plugins/mill/unit_tests/test-plan-validate.py`
  already has extensive coverage for both checks —
  `test_check_context_completeness_*` (from line 1548) and
  `test_check_requirements_quote_indent_drift_*` (from line 2049,
  including `_dirty_list_continuation_indent`,
  `_dirty_nonzero_baseline_indent`, and
  `_dirty_fence_contains_nested_heading` true-positive regression
  cases). New tests belong in this same file, following its existing
  helper patterns (temp batch-file fixtures, `_plan_validate` module
  import at line 34). Run via `run-all.py` per repo convention.
- Verified empirically during discussion (not asserted from the issue
  text alone): `Path(project_root) / '//'` under Python's `pathlib`
  resolves to an absolute path (right-hand operand starting with `/`
  overrides the join), landing on a directory-like path whose
  `.is_file()` is `False` — confirms the directory-vs-file fix also
  covers #760's `//` repro without a separate token-shape filter.

## Testing

- `_check_context_completeness` (TDD candidates, add to
  `test-plan-validate.py`):
  - Directory-only backtick token in Requirements prose (e.g.
    `` `internal/gitrepo` `` where `internal/gitrepo/` exists on disk
    as a directory, no file of that exact name) → clean, no finding.
  - Same directory token, but the directory does NOT exist on disk at
    all (simulating the pre-`.scratch/`-creation state from #750) →
    also clean — same code path, confirms determinism regardless of
    on-disk presence.
  - `` `//` `` token in Requirements prose → clean, no finding.
  - Existing `_dirty_missing` test (real *file* reference, not in any
    ref field) must still fail — regression guard that the
    `is_file()` filter didn't over-broaden the exemption to real files.
- `_check_requirements_quote_indent_drift` (TDD candidates):
  - Fence quoting a mid-line fragment of a longer source line, fence
    itself at zero indentation, closing ` ``` ` also at zero indentation
    → clean, no finding (regression case for #761; currently reports
    spurious `N=1`).
  - Fence as the last row of a markdown table with correct,
    byte-exact quoted content, where the closing ` ``` ` carries
    list-continuation indentation → clean, no finding (regression case
    for #754; currently reports spurious `N=2`-or-similar via
    incidental adjacent-content match).
  - Re-run all existing `test_check_requirements_quote_indent_drift_dirty_*`
    cases unchanged (list-continuation indent, nonzero baseline
    indent, multi-fence, CRLF-source/LF-fence, nested-heading,
    multi-edits-tie-break) — the normalization must not turn any
    genuine drift case into a false negative.

## Q&A log

- **Q:** context-completeness — how should the check distinguish a
  directory reference from a file reference? **A:** [auto-pick] Filter
  `resolve_existing_paths`'s result to `is_file()` in
  `_check_context_completeness`'s own resolvability test; leave the
  shared helper untouched. **Why:** minimal, deterministic, and
  verified to also cover the `//` token case for free — no separate
  punctuation-shape heuristic needed.
- **Q:** should `creates_union`/`deletes_union`/`moves_targets`
  membership also get directory-shape filtering? **A:** [auto-pick] No
  change. **Why:** no source issue reports a false positive through
  that path; those fields are conventionally file-only.
- **Q:** quote-indent-drift — single unified fix or two special-cases
  for #754 and #761? **A:** [auto-pick] Single normalization —
  `re.sub(r"\n[ \t]*\Z", "", fence_body)` right after extraction, used
  by both the byte-exact pre-check and the `N`-search loop. **Why:**
  both issues share one root cause (the closing fence's own
  indentation leaking into the captured body); one mechanically
  justified change is easier to verify than two special-cases.
- **Q:** should `_RE_FENCE_BODY` also be re-anchored (line-start
  closing delimiter)? **A:** [auto-pick] No. **Why:** the
  normalization fix already resolves both known issues without
  touching the regex's broader matching semantics (nested fences,
  language tags) — no reported bug justifies that additional risk.
- **Q:** verification approach? **A:** [auto-pick] New regression unit
  tests in the existing `test-plan-validate.py`, covering all six
  issues' repro cases, run via `run-all.py`. **Why:** both checks are
  pure functions over synthetic batch-file text — no integration test
  needed, and the file already has an established pattern for exactly
  this kind of test.
