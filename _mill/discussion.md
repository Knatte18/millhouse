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
  `_check_verify_excludes_edited_tagged_test` (renamed to `_go_file_custom_tags` /
  `_verify_command_has_any_tag` per `bug1-rename-integration-specific-identifiers`): generalize
  from a single hardcoded tag name to discovering the actual custom tag(s) from each edited
  file's own `//go:build` expression, and check every edited tagged test file in the batch
  (not just the first one found, per `bug1-check-every-tagged-file-not-just-first`).
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
- **Deliberate divergence from `_implementer_common.py`'s `_GO_BUILD_TAG_GOOS`/
  `_GO_BUILD_TAG_GOARCH` (lines 1014-1017):** that existing precedent uses a small, explicitly
  non-exhaustive set (`{"linux", "darwin", "windows", "freebsd"}` / `{"amd64", "arm64",
  "386"}`) and documents that an unrecognized-but-real GOOS/GOARCH value is safe to
  misclassify as "custom" there, because its caller (`_go_build_tag_retiering_stuck`) actually
  runs `go build -tags <tag>` downstream — a bogus tag fails the compile and surfaces as
  `stuck_type: verify`, i.e. the misclassification fails closed. This check has no such
  downstream compile step: it is a static validator whose only effect is requiring a `-tags`
  flag in `verify:`. A misclassified real GOOS/GOARCH value here (e.g. some less-common value
  missing from a small set, like `openbsd` or `wasm`) would silently create a *new*,
  never-corrected false positive — the exact failure mode this task exists to eliminate — not
  a safely-failing one. This check therefore intentionally uses a larger, more complete
  denylist than the existing precedent rather than reusing or extending that smaller set;
  the two checks have different safety directions and must not share one constant.

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

### bug1-check-every-tagged-file-not-just-first

- Decision: `_check_verify_excludes_edited_tagged_test`'s loop over `edited_test_tokens`
  (line ~2059) currently sets `tagged_token` on the first tagged file found and `break`s,
  checking only that one file against `verify:`. The generalized check removes the `break`:
  it walks every edited test token, resolves each one, and for every file that is tagged
  (has ≥1 custom tag per `bug1-tag-discovery-via-denylist`), independently checks that file's
  custom-tag set against `verify:`'s `-tags` value using the "any tag matches" rule from
  `bug1-any-tag-match-semantics`. A batch editing both a `scout`-tagged and a `smoke`-tagged
  test file, with `verify: -tags scout`, now correctly still flags the untested `smoke` file —
  today's single-file logic would silently pass with 0 findings. Each untested tagged file
  produces its own finding (error dict), not one finding per batch — the existing shape
  (`errors.append(...)` once per batch) generalizes to appending once per untested file inside
  the same per-batch loop iteration.
- Rationale: verified against source that the current `break` genuinely stops at the first
  tagged file. Generalizing tag *discovery* per file without also generalizing the *loop* to
  cover every tagged file would reproduce bug 1's exact false-negative class inside the fix
  itself — a `verify:` command satisfying only the first-found file's tag would pass even
  though a second, differently-tagged file is silently excluded from the build. Fixing
  discovery but not coverage would be a materially incomplete fix.
- Rejected: keeping the single-file `break` and documenting it as an accepted limitation —
  rejected because it isn't a narrow, unlikely-to-matter edge case like the existing
  `Creates:`-only limitation; it directly undermines the generalization this task is doing,
  and multi-file batches with different build tags are exactly the shape a Go repo with
  multiple test tiers (integration/smoke/scout) is likely to produce.

### bug1-message-uses-discovered-tag

- Decision: The finding message interpolates the actual discovered custom tag name(s) (e.g.
  "carries a `-tags` flag whose value includes `scout`") instead of the hardcoded word
  "integration".
- Rationale: the hardcoded wording is part of the same bug — a `scout`-tagged file with no
  `-tags` flag should not produce a message that says "integration".
- Rejected: none — this follows directly from generalizing the detection itself.

### bug1-message-tag-selection-deterministic

- Decision: `_go_file_custom_tags` returns `set[str]` (matching uses set intersection, order
  doesn't matter there). When a file has more than one custom tag, the finding message names
  `sorted(tags)[0]` — the alphabetically-first custom tag — never raw set-iteration order.
- Rationale: Python's `set[str]` iteration order for strings is not guaranteed stable/
  deterministic across runs (no insertion-order guarantee like `dict`), so "the first
  discovered tag" as originally phrased in Technical context was ambiguous and would make the
  finding message's exact wording flaky across runs/interpreter versions for a
  multi-tag-in-one-file case (e.g. `//go:build scout && smoke`). `sorted(...)[0]` is
  deterministic and matches this same function's own existing convention one call up: `edited_test_tokens`
  is already built via `sorted(t for t in _parse_edits_only(batch_path) if ...)` for the same
  determinism reason.
- Rejected: preserving `re.findall`'s source-order via a list before the denylist filter (i.e.
  "first tag as it appears in the `//go:build` expression") — also deterministic, but adds a
  second ordered-list code path alongside the `set[str]` used for matching, for a message-only
  cosmetic difference; `sorted()` reuses the pattern already established one line up in the same
  function.

### bug1-rename-integration-specific-identifiers

- Decision: `_go_file_is_integration_tagged` is renamed to `_go_file_custom_tags` (returns
  `set[str]` of discovered custom tags, empty set = untagged, replacing the current `bool`
  return) and `_verify_command_has_integration_tag` is renamed to
  `_verify_command_has_any_tag(command: str, tags: set[str]) -> bool`. The module-level
  docstring block (lines 38-41) and both functions' own docstrings are reworded to describe
  "custom tag discovered from the file's own `//go:build` expression" instead of the literal
  word "integration". `_RE_GO_BUILD_CONSTRAINT`'s comment (line 1940, "checked for the word
  'integration'") is updated to describe the denylist-based extraction instead.
- Rationale: generalizing the behavior while leaving `..._is_integration_tagged`-shaped names
  and "integration"-only docstrings in place would be actively misleading to the next reader —
  the whole point of this task is that "integration" was never a safe hardcode. Renaming is
  cheap (function is called from exactly one check, `_check_verify_excludes_edited_tagged_test`,
  plus its own unit tests) and there is no external/cross-file API surface to preserve.
- Rejected: leaving the legacy names in place with updated docstrings only — rejected because
  the name itself is the misleading part, not just the prose describing it.

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

- `_parse_cards` (line 126): the function to fix. Called from 6 call sites in the same file
  (lines 750, 838, 872, 1503, 1715, 2511) — all call it fresh on `batch_text`/`text`, so the
  fix is a single localized change with no call-site updates needed.
- `_requirements_fence_aware_body` (line 1622): the existing fence-aware precedent to mirror —
  same `in_fence` toggle-on-` ``` `-prefix convention, already proven correct and referenced by
  its own "fence-aware-boundary-detection" Decision note (this task's bug2 decision above is the
  second application of that same pattern, not a new one).
- `_go_file_is_integration_tagged` (line 1950, renamed `_go_file_custom_tags` per
  `bug1-rename-integration-specific-identifiers`), `_verify_command_has_integration_tag` (line
  1979, renamed `_verify_command_has_any_tag`), `_check_verify_excludes_edited_tagged_test`
  (line 2003): the three functions to generalize for bug 1.
  `_check_verify_excludes_edited_tagged_test` currently tracks a single
  `tagged_token: str | None` and `break`s at the first tagged file (lines 2059-2068); per
  `bug1-check-every-tagged-file-not-just-first` this becomes a loop with no `break` that
  independently resolves each edited test token's custom-tag set and appends one finding per
  untested tagged file, carrying that file's own custom-tag set (or `sorted(tags)[0]` per
  `bug1-message-tag-selection-deterministic`, for the message) alongside its token path.
- `_RE_GO_BUILD_CONSTRAINT` (line 1941) already captures the full expression string via its
  `expr` named group — the generalized identifier-extraction reuses this same capture, no regex
  change needed there.
- `_GO_BUILD_TAG_SCAN_LINES` (line 1947, bounded to 40 lines) and the header-comment-skipping
  scan logic in `_go_file_custom_tags` (renamed, see above) are unrelated to either bug and stay
  unchanged.
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

- **Bug 1 (`_go_file_custom_tags` / `_verify_command_has_any_tag` /
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
  - **Multi-file batch** (per `bug1-check-every-tagged-file-not-just-first`): a batch editing
    both a `scout`-tagged and a `smoke`-tagged test file, `verify:` carrying only `-tags scout`
    → 1 finding naming the untested `smoke` file — this is the regression guard proving the
    loop no longer stops at the first tagged file. A companion clean case (same two files,
    `verify: -tags scout,smoke`) → 0 findings.
  - **Multi-composed-tag single file** (per `bug1-any-tag-match-semantics` /
    `bug1-message-tag-selection-deterministic`): one test file with
    `//go:build scout && smoke`, `verify:` with no `-tags` → 1 finding whose message names
    `scout` (the alphabetically-first of the two, deterministic per `sorted(tags)[0]`). A
    companion clean case, same fixture, `verify: -tags smoke` (only the second/non-first tag)
    → 0 findings — proves the "ANY tag matches" rule from `bug1-any-tag-match-semantics` is
    independent of which tag the message-selection logic happens to name.
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
- **Q:** (discussion-review r1 GAP) `_check_verify_excludes_edited_tagged_test` breaks at the
  first tagged edited file and checks only that one — should the generalized check validate
  every edited tagged file in the batch, or is single-file coverage an accepted limitation?
  **A:** [auto-pick] Validate every edited tagged file independently; remove the `break`, emit
  one finding per untested tagged file. **Why:** leaving the `break` in place would reproduce
  bug 1's exact false-negative class inside the fix itself — a batch editing both a
  `scout`-tagged and a `smoke`-tagged file with `verify: -tags scout` would otherwise still
  silently pass despite the untested `smoke` file. See `bug1-check-every-tagged-file-not-just-first`.
- **Q:** (discussion-review r1 GAP) `_implementer_common.py` already has a small
  `_GO_BUILD_TAG_GOOS`/`_GO_BUILD_TAG_GOARCH` denylist for an analogous purpose — should this
  task's new denylist reuse/extend that set instead of introducing a separate, larger one?
  **A:** [auto-pick] No — keep a separate, larger denylist; explicitly document why. **Why:**
  the existing precedent's small set is safe only because its caller fails closed downstream
  (a bogus `-tags` value there triggers an actual `go build` failure); this check has no such
  downstream compile step, so an unrecognized-but-real GOOS/GOARCH value falling through the
  small set would create a new, never-corrected false positive instead of failing safely. See
  the `_implementer_common.py` divergence note under `bug1-tag-discovery-via-denylist`.
- **Q:** (discussion-review r2 GAP) `_go_file_custom_tags` returns `set[str]`, and the finding
  message was specified as naming "its first discovered tag" — but `set[str]` iteration order
  isn't guaranteed deterministic. What determines the named tag when a single file has more
  than one custom tag? **A:** [auto-pick] `sorted(tags)[0]` — deterministic, alphabetically
  first — reusing this same function's own existing `sorted(...)` convention for
  `edited_test_tokens` one call up. **Why:** an ambiguous "first discovered" spec over a
  `set[str]` would make the finding message's wording flaky across runs; also added a
  single-file multi-composed-tag test case, which was previously unexercised. See
  `bug1-message-tag-selection-deterministic`.
