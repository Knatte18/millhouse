# Discussion: _plan_validate.py: hardcoded tag-name check and fenced-code-block-unaware card parsing

```yaml
task: _plan_validate.py: hardcoded tag-name check and fenced-code-block-unaware card parsing
slug: mill-plan-validate-heuristic-gaps-2
status: discussing
parent: main
```

## Problem

`_plan_validate.py` (`plugins/mill/scripts/_plan_validate.py`) has two independent heuristic
bugs, both found live in other repos' mill-plan runs — continuing the same theme as the earlier
`mill-plan-validate-false-positives` task: checks that make an assumption too narrow for the
repos they actually run against, so they either stay silently wrong (false negative) or fire
when they shouldn't (false positive).

**Bug 1 (false negative, GitHub #780):** the `verify-excludes-edited-tagged-test` check
hardcodes the single tag name `"integration"` when scanning a Go test file's leading
`//go:build` constraint (`_go_file_is_integration_tagged`, line ~1950) and when scanning a
batch's `verify:` command for a matching `-tags` flag (`_verify_command_has_integration_tag`,
line ~1979). A repo using other custom test-tier tags — e.g. loomyard's `scout` and `smoke`,
per its own CONSTRAINTS.md "Test Tier Purity Invariant" — passes the validator with 0 errors
even when the batch's `verify:` command never compiles the tagged files it edits. The gap was
only caught by the LLM plan reviewer at round 3 in the reporting session, not by this validator
check, which is the entire point of the check existing.

**Bug 2 (false positive, GitHub #776):** `_parse_cards` (line 126) ends a card block at *any*
line starting with `### `, with no awareness of fenced-code-block depth. When a card's
`Requirements:` field legitimately quotes a `### ` heading inside a fenced block (e.g.
instructing the implementer to write that exact heading into a target file), the parser
prematurely ends the card there — producing a spurious `card-missing-field` (`Commit:`) error
even though the field is present later in the same card, just after the fence. This already
forced one plan author to work around it by describing the heading in prose instead of quoting
it literally.

## Scope

**In:**
- `_go_file_is_integration_tagged` / `_verify_command_has_integration_tag` /
  `_check_verify_excludes_edited_tagged_test`: generalize from a single hardcoded tag name to
  discovering the actual custom tag(s) from the file's own `//go:build` expression.
- `_parse_cards`: track fenced-code-block depth so a `### ` line inside an open fence never
  starts or ends a card block.
- Unit tests for both fixes, following existing conventions in
  `plugins/mill/unit_tests/test-plan-validate.py`.

**Out:**
- Full Go build-constraint boolean evaluation (correct `&&`/`||`/`!` semantics). The existing
  check already tolerates this imprecision (e.g. `//go:build !integration` today still matches
  `\bintegration\b` despite the negated semantics); this task does not raise that bar.
- A configurable/external list of custom tag names. The fix discovers tags from the file itself
  instead of maintaining any list of known custom tags (the root cause of bug 1).
- Any other `_plan_validate.py` heuristic not named in issues #780 / #776.
- Changes to `_requirements_fence_aware_body`'s own logic — it is already correct and is reused
  here only as the precedent/pattern for `_parse_cards`'s fix.

## Decisions

### bug1-tag-discovery-via-denylist

- Decision: Replace the single hardcoded `"integration"` check with: extract all identifiers
  from the `//go:build` expression (`re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr)` — boolean
  operators `&&`, `||`, `!`, and parens are not word characters so they're skipped for free),
  then exclude a hardcoded denylist of standard Go build tags:
  - GOOS values: `aix android darwin dragonfly freebsd hurd illumos ios js linux nacl netbsd
    openbsd plan9 solaris wasip1 windows zos`
  - GOARCH values: `386 amd64 amd64p32 arm armbe arm64 arm64be loong64 mips mipsle mips64
    mips64le mips64p32 mips64p32le ppc ppc64 ppc64le riscv riscv64 s390 s390x sparc sparc64
    wasm`
  - Reserved words: `cgo race msan asan unix boringcrypto gc gccgo purego ignore`
  - Release-version tags matching `^go[1-9]\d*\.\d+$` (e.g. `go1.21`)

  Remaining identifiers are "custom tags." A file is tagged if it has ≥1 custom tag.
- Rationale: the issue explicitly asks for discovery from the file's own expression rather than
  a bigger fixed list of known custom tag names — a bigger fixed list just reproduces the same
  bug class the next time a repo invents a new tag name. A denylist is required once we
  generalize: without it, a plain `//go:build linux` file would suddenly require `-tags linux`
  in `verify:`, which is wrong (GOOS/GOARCH tags are satisfied automatically, never via
  `-tags`) and would be a brand-new false positive shipped by this very fix.
- Rejected: (a) expanding the hardcoded set to `{integration, smoke, scout}` — doesn't
  generalize, still wrong for the next repo's tag name; (b) treating every identifier as custom
  with no denylist — simplest, but creates the GOOS/GOARCH false-positive described above.

### bug1-any-tag-match-semantics

- Decision: When a file has multiple custom tags (rare, via boolean composition, e.g.
  `//go:build scout && smoke`), the check is satisfied if **any** of the file's custom tags
  appears in the `verify:` command's `-tags` flag value (comma/whitespace-split token match,
  same mechanism as the current `_verify_command_has_integration_tag`, generalized to accept a
  set of target tags instead of the single literal `"integration"`).
- Rationale: matches the current check's existing precision level (single substring/token
  match, no real boolean evaluation). Requiring ALL custom tags to match would need correct
  AND/OR handling to avoid new false positives on OR-composed expressions — that's a
  meaningfully larger scope than either source issue asked for.
- Rejected: requiring all custom tags to match — deferred as future work if a real repo hits
  this gap; not proven necessary by either issue.

### bug1-message-uses-discovered-tag

- Decision: The finding message interpolates the actual discovered custom tag name(s) (e.g.
  "carries a `-tags` flag whose value includes `scout`") instead of the hardcoded word
  "integration".
- Rationale: the hardcoded wording is part of the same bug — a `scout`-tagged file with no
  `-tags` flag should not produce a message that says "integration".
- Rejected: none — this follows directly from generalizing the detection itself.

### bug2-fence-guard-both-boundaries

- Decision: `_parse_cards` tracks a single `in_fence` boolean across the whole scan, toggled by
  `line.startswith("```")` (reusing the exact convention already established by
  `_requirements_fence_aware_body`, line 1622, for the identical class of problem). The guard
  applies to **both** regex checks in the loop: the `### Card N:` new-card-start match and the
  "any other `### ` heading ends the card" match — neither fires while `in_fence` is `True`.
- Rationale: a fenced block quoting a `### Card N:`-shaped example is the same bug class as one
  quoting a plain `### ` heading; fixing only the reported ending-match would leave a symmetric,
  equally-real gap unfixed. Reusing the existing precedent's exact toggle convention keeps the
  two fence-aware scanners in this file consistent instead of introducing a second slightly
  different fence-detection idiom.
- Rejected: guarding only the ending-match (narrower, matches only the literally reported
  symptom, leaves the start-match gap live).

## Technical context

- `_parse_cards` (line 126): the function to fix. Called from 7 call sites in the same file
  (lines 750, 838, 872, 1503, 1715, 2511, plus its own definition) — all call it fresh on
  `batch_text`/`text`, so the fix is a single localized change with no call-site updates needed.
- `_requirements_fence_aware_body` (line 1622): the existing fence-aware precedent to mirror —
  same `in_fence` toggle-on-` ``` `-prefix convention, already proven correct and referenced by
  its own "fence-aware-boundary-detection" Decision note (this task's bug2 decision above is the
  second application of that same pattern, not a new one).
- `_go_file_is_integration_tagged` (line 1950), `_verify_command_has_integration_tag` (line
  1979), `_check_verify_excludes_edited_tagged_test` (line 2003): the three functions to
  generalize for bug 1. `_check_verify_excludes_edited_tagged_test` currently tracks a single
  `tagged_token: str | None`; generalizing to a tag set changes this to carry the file's custom
  tag set (or at minimum the first discovered custom tag name, for the message) alongside the
  token path.
- `_RE_GO_BUILD_CONSTRAINT` (line 1941) already captures the full expression string via its
  `expr` named group — the generalized identifier-extraction reuses this same capture, no regex
  change needed there.
- `_GO_BUILD_TAG_SCAN_LINES` (line 1947, bounded to 40 lines) and the header-comment-skipping
  scan logic in `_go_file_is_integration_tagged` are unrelated to either bug and stay unchanged.
- Existing unit tests for bug 1's check live in `plugins/mill/unit_tests/test-plan-validate.py`
  starting at line 5297 (`test_verify_excludes_edited_tagged_test_*`, 7 tests: (a) no-tags-flag
  dirty, (b) tags-integration clean, (c) tags-integration-comma-other clean, (d) no-build-tag
  clean, (e) not-go-project clean, (f) malformed-verify-no-crash, (g) header-comment-scan dirty,
  (h) creates-only clean). Fixtures `_GO_MOD_TEXT`, `_INTEGRATION_TAGGED_TEST_GO`,
  `_UNTAGGED_TEST_GO`, `_HEADER_COMMENT_INTEGRATION_TAGGED_TEST_GO` are defined at lines
  5278–5290-ish, immediately above the test functions; new fixtures for `scout`/`smoke`/a
  GOOS-only tag follow the same `"//go:build <expr>\n\npackage foo\n"` shape. The
  `_make_verify_only_batch_text("alpha", "<verify command>", edits=[...])` helper is the
  established way to build a one-card batch fixture for this check.
- Existing card-parsing tests live near line 301 (`test_check_card_missing_field_clean/dirty`)
  and line 5172 (`test_check_cards_legend_in_comment_not_parsed_as_refs` — a related but
  distinct existing regression guard for a different `_parse_cards`-adjacent false positive).
  `_make_batch_file(...)` is the established helper for constructing a card body; a
  fence-in-Requirements repro likely needs a hand-built batch string (as
  `test_verify_excludes_edited_tagged_test_malformed_verify_no_crash` at line 5444 does) rather
  than that helper, since the helper does not expose raw Requirements: content control.

## Constraints

No `CONSTRAINTS.md` exists at this hub root — no additional constraints beyond the ones already
captured under Scope/Decisions above.

## Testing

- **Bug 1 (`_go_file_is_integration_tagged` / `_verify_command_has_integration_tag` /
  `_check_verify_excludes_edited_tagged_test`) — TDD candidates:**
  - `scout`-tagged test file (`//go:build scout`), `verify:` with no `-tags` → 1 finding naming
    `scout` (mirrors existing test (a), generalized).
  - Same `scout` fixture, `verify:` with `-tags scout` → 0 findings (mirrors existing test (b)).
  - A second custom tag (e.g. `smoke`) repeating the clean/dirty pair, proving the fix isn't
    special-cased to exactly two tag names.
  - GOOS-only build constraint (`//go:build linux`), `verify:` with no `-tags` → 0 findings —
    this is the regression guard proving the denylist prevents a brand-new false positive from
    this very fix (the most important new test; nothing today exercises this path since the
    only pre-existing "no relevant tag" fixture is `_UNTAGGED_TEST_GO`, which has no
    `//go:build` line at all rather than a GOOS-only one).
  - All 7 existing tests at line 5297+ must still pass unmodified (the `integration` case is
    just one instance of the generalized "custom tag" concept now, not special-cased code).

- **Bug 2 (`_parse_cards`) — TDD candidates:**
  - Issue #776's exact repro: a single-card batch whose `Requirements:` field contains a fenced
    block with a literal `### ` line inside it, followed later in the same card (after the
    closing fence) by the `- **Commit:**` field → zero `card-missing-field` errors.
  - Regression guard: a real `### Card N:` heading appearing *outside* any fence, after a
    fenced block that itself contains a `### `-shaped line, still correctly starts card N+1 (or
    N, depending on fixture numbering) — proves the fence guard doesn't over-suppress genuine
    card boundaries.
  - Existing tests at line 301 (`test_check_card_missing_field_clean/dirty`) and line 5172
    (`test_check_cards_legend_in_comment_not_parsed_as_refs`) must still pass unmodified.

## Q&A log

- **Q:** How should the check tell a "custom" build tag apart from a standard Go tag
  (GOOS/GOARCH/etc.)? **A:** [auto-pick] Extract identifiers from the `//go:build` expression,
  exclude a hardcoded denylist of standard Go tags (GOOS/GOARCH/reserved words/release-version
  tags); remainder are custom tags requiring a matching `-tags`. **Why:** the issue asks for
  discovery from the file's own expression, not a bigger fixed list; a denylist is required for
  correctness once generalized (GOOS/GOARCH tags never need `-tags`).
- **Q:** When a file has multiple custom tags, what counts as "verify: has a matching -tags"?
  **A:** [auto-pick] ANY of the file's custom tags appearing in `-tags` satisfies the check.
  **Why:** matches the current check's existing precision level; full boolean evaluation is out
  of scope and not requested by the issue.
- **Q:** Should the finding message name the actual discovered tag instead of always saying
  "integration"? **A:** [auto-pick] Yes, interpolate the discovered tag name(s). **Why:** the
  hardcoded wording is part of the same bug.
- **Q:** Should the `_parse_cards` fence guard cover both the card-start match and the
  card-end match, or only the reported one? **A:** [auto-pick] Both, via one `in_fence` boolean
  tracked across the whole scan, reusing `_requirements_fence_aware_body`'s existing convention.
  **Why:** a fence quoting a `### Card N:`-shaped example is the same bug class as one quoting a
  plain `### ` heading; the unfixed case is a live footgun of the same shape.
- **Q:** Fence-toggle detection convention? **A:** [auto-pick] Reuse
  `line.startswith("\`\`\`")` verbatim, matching the existing precedent in this file. **Why:**
  consistency with the already-battle-tested convention.
- **Q:** Test coverage scope? **A:** [auto-pick] Full coverage per the Testing section above
  (multiple custom-tag cases, a GOOS-only regression guard, and a fence-boundary regression
  guard), not just the minimal reported repro. **Why:** the denylist and both-boundaries
  decisions each introduce a specific new regression risk that needs its own test.
