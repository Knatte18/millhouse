# Batch: plan-validate-heuristic-fixes

```yaml
task: "_plan_validate.py: hardcoded tag-name check and fenced-code-block-unaware card parsing"
batch: plan-validate-heuristic-fixes
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py
depends-on: []
```

## Batch Scope

Fixes both `_plan_validate.py` heuristic bugs named in the task's Scope (In), plus the one
necessary downstream consequence in `mill-plan/SKILL.md`'s own step-1.5 fix table. Card 1
generalizes bug 1 (GitHub #780, false negative: hardcoded `"integration"` tag check) to
denylist-based custom-tag discovery covering every edited tagged file, not just the first. Card 2
adds its test coverage. Card 3 fixes bug 2 (GitHub #776, false positive: fence-unaware card
parsing) by making `_parse_cards` track fence depth, mirroring the existing
`_requirements_fence_aware_body` precedent. Card 4 adds its test coverage. Card 5 updates
`mill-plan/SKILL.md`'s mechanical-fix table row for `verify-excludes-edited-tagged-test` — Card 1
changes that check's finding `message` to name the actual discovered tag instead of the literal
word `"integration"`, and the fix-table row is the sole consumer that parses tag identity out of
that message text to drive an automated `-tags` append; left unchanged, it would keep appending
`"integration"` even when the discovered tag is `"scout"` or `"smoke"`, reproducing bug 1's exact
failure class one layer up, inside mill-plan's own fix automation. This one-line doc fix is not
named in either source issue, but is a direct, unavoidable consequence of Card 1's message-format
change — it is not a new heuristic and not out of scope under the task's own out-of-scope
wording ("Any other `_plan_validate.py` heuristic not named in issues #780 / #776" — this is the
same #780 heuristic's own consumer, not a different one). All cards live in one batch: both bugs
sit in the same file, share the same reviewer/implementer context, and the combined edit set is
well under the batch size cap.

## Cards

### Card 1: Generalize verify-excludes-edited-tagged-test to denylist-based custom-tag discovery

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Fix GitHub #780 (false negative) by generalizing the hardcoded `"integration"` tag check to
  discover custom tags from each file's own `//go:build` expression, per the overview's
  `custom-tag discovery via denylist`, `ANY custom tag ... satisfies`,
  `check every edited tagged file independently`, and `deterministic message tag selection`
  Shared Decisions.

  1. Add four new module-level constants directly above `_go_file_is_integration_tagged`
     (renamed below), immediately after the `_GO_BUILD_TAG_SCAN_LINES = 40` line — pure addition,
     replaces nothing:
     ```python
     # Standard Go build tags that are never "custom" -- discovering a GOOS/GOARCH/reserved/
     # release-version identifier in a //go:build expression must not require a matching -tags
     # flag (those tags are satisfied automatically, never via -tags).
     _GO_BUILD_DENYLIST_GOOS = frozenset({
         "aix", "android", "darwin", "dragonfly", "freebsd", "hurd", "illumos", "ios", "js",
         "linux", "nacl", "netbsd", "openbsd", "plan9", "solaris", "wasip1", "windows", "zos",
     })
     _GO_BUILD_DENYLIST_GOARCH = frozenset({
         "386", "amd64", "amd64p32", "arm", "armbe", "arm64", "arm64be", "loong64", "mips",
         "mipsle", "mips64", "mips64le", "mips64p32", "mips64p32le", "ppc", "ppc64", "ppc64le",
         "riscv", "riscv64", "s390", "s390x", "sparc", "sparc64", "wasm",
     })
     _GO_BUILD_DENYLIST_RESERVED = frozenset({
         "cgo", "race", "msan", "asan", "unix", "boringcrypto", "gc", "gccgo", "purego", "ignore",
     })
     # Release-version tags (e.g. "go1.21") are also never custom.
     _RE_GO_RELEASE_VERSION_TAG = re.compile(r"^go[1-9]\d*\.\d+$")

     # Deliberate divergence from _implementer_common.py's _GO_BUILD_TAG_GOOS/_GO_BUILD_TAG_GOARCH
     # (lines 1014-1017 there): that smaller set is safe only because its caller
     # (_go_build_tag_retiering_stuck) runs `go build -tags <tag>` downstream, so a
     # misclassified real GOOS/GOARCH value fails the compile and surfaces as stuck_type: verify
     # (fails closed). This check has no downstream compile step -- a misclassified value here
     # would silently create a new, never-corrected false positive, so it intentionally uses a
     # larger, more complete denylist and must not share a constant with that smaller set.
     ```

  2. Rename `_go_file_is_integration_tagged(path: Path) -> bool` to
     `_go_file_custom_tags(path: Path) -> set[str]`. Keep the existing header-comment-skipping,
     `_GO_BUILD_TAG_SCAN_LINES`-bounded scan loop unchanged. On the first scanned line matching
     `_RE_GO_BUILD_CONSTRAINT`, extract identifiers via
     `re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", m.group("expr"))` and return (immediately — do not
     keep scanning further lines, matching the original's return-on-first-match control flow) the
     set of extracted identifiers that are in none of `_GO_BUILD_DENYLIST_GOOS`,
     `_GO_BUILD_DENYLIST_GOARCH`, `_GO_BUILD_DENYLIST_RESERVED`, and do not match
     `_RE_GO_RELEASE_VERSION_TAG`. If no `//go:build` line is found before the scan ends, return
     an empty `set[str]` (equivalent to the original's implicit `False`). Rewrite the docstring:
     describe "custom tag discovered from the file's own `//go:build` expression, GOOS/GOARCH/
     reserved-word/release-version tags excluded via denylist" instead of the literal word
     "integration"; update `Returns:` to describe the returned `set[str]` (empty when untagged).

  3. Rename `_verify_command_has_integration_tag(command: str) -> bool` to
     `_verify_command_has_any_tag(command: str, tags: set[str]) -> bool`. Keep the existing
     `_RE_VERIFY_TAGS_FLAG.finditer` loop and comma/whitespace-split tokenizing unchanged; change
     the membership test from `"integration" in tokens` to a non-empty intersection,
     `set(tokens) & tags`. Rewrite the docstring to describe the generalized any-of-`tags` match
     instead of the literal word "integration"; add `tags` to `Args:`.

  4. In `_check_verify_excludes_edited_tagged_test`: remove the `tagged_token: str | None = None`
     single-file tracking and its `break` (today's per-token resolve-and-break loop). Move the
     `frontmatter = _plan_dag._read_batch_frontmatter(batch_path)` /
     `_plan_dag.parse_verify_field(...)` call (today wrapped in `try`/`except ValueError:
     continue`, deferring to `_check_verify_malformed_cwd`) so it runs once per batch, immediately
     after the existing `if not edited_test_tokens: continue` guard and before the per-token loop
     — preserving today's "malformed mapping -> skip whole batch, no findings" behavior. Then loop
     over every token in `edited_test_tokens` unconditionally (no `break`): resolve it via
     `resolve_existing_paths`, `continue` if unresolved; call `_go_file_custom_tags` on the
     resolved path and `continue` if the returned set is empty (untagged file); otherwise, if
     `command is None or not _verify_command_has_any_tag(command, tags)`, append one error dict
     for that token (do not stop after the first — each independent untested tagged file gets its
     own finding).

  5. Change the finding `"message"` (currently ending `"-tags ...integration... flag"`) to:
     ```python
     f"batch '{batch_path.stem}' edits custom-tagged test '{token}' but its verify: command "
     f"lacks a matching -tags flag naming '{sorted(tags)[0]}'"
     ```
     per the overview's `deterministic message tag selection` Shared Decision. Keep the
     `"check"`, `"batch"`, `"card"`, `"path"` dict keys exactly as today — only `"message"`'s
     wording changes.

  6. Rewrite `_check_verify_excludes_edited_tagged_test`'s own docstring: replace
     "integration-tagged" / "an integration-tagged test" wording throughout with "custom-tagged" /
     the denylist-discovery description, and describe the per-file (not per-batch,
     first-match-only) finding behavior from step 4.

  7. Update `_RE_GO_BUILD_CONSTRAINT`'s preceding comment (currently "The captured expression is
     checked for the word 'integration'.") to describe denylist-based identifier extraction
     instead.

  8. Update the module docstring's `verify-excludes-edited-tagged-test` bullet (near the top of
     the file, in the `Checks performed (check keys):` list) to match the generalized behavior:
     custom-tag discovery via denylist, and checking every edited tagged file independently
     rather than only the first.
- **Commit:** `fix(plan-validate): discover custom Go build tags via denylist instead of hardcoding "integration" (#780)`

### Card 2: Tests for custom-tag discovery and multi-file/multi-tag coverage

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add 9 new test functions immediately after `test_verify_excludes_edited_tagged_test_creates_only_clean`
  and before the `# --- Runner ---` section, following the existing 8 tests' fixture/assertion
  style exactly (`tempfile.TemporaryDirectory()`, `_make_overview`, `_make_verify_only_batch_text`,
  `_write_plan`, `_plan_validate.run`, filter on `e["check"] == "verify-excludes-edited-tagged-test"`,
  try/assert/print PASS/except AssertionError/print FAIL-to-stderr). Add new Go-source fixture
  constants alongside the existing `_INTEGRATION_TAGGED_TEST_GO` / `_UNTAGGED_TEST_GO` block:
  ```python
  _SCOUT_TAGGED_TEST_GO = "//go:build scout\n\npackage foo\n"
  _SMOKE_TAGGED_TEST_GO = "//go:build smoke\n\npackage foo\n"
  _GOOS_ONLY_TAGGED_TEST_GO = "//go:build linux\n\npackage foo\n"
  _SCOUT_AND_SMOKE_TAGGED_TEST_GO = "//go:build scout && smoke\n\npackage foo\n"
  ```
  New tests (each writes `go.mod` via `_GO_MOD_TEXT` into `project_root` first, matching every
  existing test in this block):

  1. `test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty` — one file at
     `pkg/foo_test.go` written with `_SCOUT_TAGGED_TEST_GO`, `edits=["pkg/foo_test.go"]`,
     `verify_command="PYTHONPATH= go test ./..."` (no `-tags`) -> assert exactly 1 finding whose
     `path == "pkg/foo_test.go"` and whose `message` contains `"scout"`.
  2. `test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean` — same fixture,
     `verify_command="PYTHONPATH= go test ./... -tags scout"` -> assert zero findings.
  3. `test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty` — one file at
     `pkg/foo_test.go` written with `_SMOKE_TAGGED_TEST_GO`, `edits=["pkg/foo_test.go"]`, no
     `-tags` -> assert exactly 1 finding whose `message` contains `"smoke"`.
  4. `test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean` — same fixture,
     `verify_command="PYTHONPATH= go test ./... -tags smoke"` -> assert zero findings.
  5. `test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean` — one file at
     `pkg/foo_test.go` written with `_GOOS_ONLY_TAGGED_TEST_GO`, `edits=["pkg/foo_test.go"]`, no
     `-tags` -> assert zero findings (the denylist-correctness regression guard: a plain
     `//go:build linux` file must never require `-tags linux`).
  6. `test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty` —
     `pkg/foo_test.go` written with `_SCOUT_TAGGED_TEST_GO`, `pkg/bar_test.go` written with
     `_SMOKE_TAGGED_TEST_GO`, `edits=["pkg/foo_test.go", "pkg/bar_test.go"]`,
     `verify_command="PYTHONPATH= go test ./... -tags scout"` -> assert exactly 1 finding whose
     `path == "pkg/bar_test.go"` and whose `message` contains `"smoke"` (proves the loop no longer
     stops at the first tagged file).
  7. `test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean` — same two-file
     fixture as test 6, `verify_command="PYTHONPATH= go test ./... -tags scout,smoke"` -> assert
     zero findings.
  8. `test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty` — one
     file at `pkg/baz_test.go` written with `_SCOUT_AND_SMOKE_TAGGED_TEST_GO`,
     `edits=["pkg/baz_test.go"]`, no `-tags` -> assert exactly 1 finding whose
     `path == "pkg/baz_test.go"` and whose `message` contains `"scout"` (the alphabetically-first
     of `{scout, smoke}` per `sorted(tags)[0]`) and does NOT contain `"smoke"`.
  9. `test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean`
     — same fixture as test 8, `verify_command="PYTHONPATH= go test ./... -tags smoke"` (only the
     second/non-first tag) -> assert zero findings (proves the "ANY tag matches" rule is
     independent of which tag the message-selection logic happens to name).

  Register all 9 new test function names in `main()`'s `tests` list, immediately after the
  existing `test_verify_excludes_edited_tagged_test_creates_only_clean` entry, in the same order
  as authored above.
- **Commit:** `test(plan-validate): cover custom-tag discovery, multi-file, and multi-composed-tag verify-excludes-edited-tagged-test cases`

### Card 3: Make _parse_cards fence-aware so quoted ### headings never truncate a card

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Fix GitHub #776 (false positive) per the overview's
  `_parse_cards reuses the existing fence-toggle convention, guards both boundaries` Shared
  Decision. Replace `_parse_cards`'s full function body (today's line-by-line scan with the bare
  `re.match(r"^###\s+Card\s+(\d+)\s*:", line)` start-check and `line.startswith("### ")`
  end-check) with a fence-aware version that tracks a single `in_fence: bool = False` across the
  whole scan, toggled on every line `.startswith("```")` — mirroring
  `_requirements_fence_aware_body`'s existing toggle convention (same file, ~line 1622) exactly.
  Full replacement body:
  ```python
  def _parse_cards(batch_text: str) -> list[tuple[int, list[str]]]:
      """Return list of (card_number, card_lines) pairs.

      Each card block starts at a ``### Card N:`` line and ends just before the next ``### ``
      heading or at EOF. A ``### `` line inside a fenced code block (delimited by lines starting
      with ``` ``` ```, toggled per ``_requirements_fence_aware_body``'s convention) never starts
      or ends a card block.
      """
      lines = batch_text.splitlines()
      cards: list[tuple[int, list[str]]] = []
      current_num: int | None = None
      current_lines: list[str] = []
      in_fence = False

      for line in lines:
          m = re.match(r"^###\s+Card\s+(\d+)\s*:", line) if not in_fence else None
          if m:
              if current_num is not None:
                  cards.append((current_num, current_lines))
              current_num = int(m.group(1))
              current_lines = [line]
          elif current_num is not None:
              if not in_fence and line.startswith("### "):
                  cards.append((current_num, current_lines))
                  current_num = None
                  current_lines = []
              else:
                  current_lines.append(line)
          if line.startswith("```"):
              in_fence = not in_fence

      if current_num is not None:
          cards.append((current_num, current_lines))

      return cards
  ```
  The function signature is unchanged; all 6 existing call sites (the `_parse_cards(text)` /
  `_parse_cards(batch_text)` call sites throughout this file) need no updates — same return shape,
  same semantics for every non-fenced input.
- **Commit:** `fix(plan-validate): make _parse_cards fence-aware so a quoted ### heading never truncates a card (#776)`

### Card 4: Tests for fence-aware card boundary parsing

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add 2 new test functions immediately after `test_check_cards_legend_in_comment_not_parsed_as_refs`
  and before the `verify-excludes-edited-tagged-test check (#724)` section comment (i.e. directly
  above the `_GO_MOD_TEXT` fixture block), following the existing tests' fixture/assertion style.

  1. `test_check_card_missing_field_fence_guard_clean` — Issue #776's exact repro. Build via
     `_make_batch_file("alpha", edits=["src/a.py"], requirements=requirements)` where
     `requirements` is:
     ```python
     requirements = (
         "  Write the following exact heading into the target file:\n"
         "  ```markdown\n"
         "  ### Some Heading\n"
         "  ```\n"
     )
     ```
     (`_make_batch_file`'s `requirements` parameter already inserts this text verbatim as the
     card's `Requirements:` body, immediately followed by the `Commit:` field — reproducing the
     exact "fenced `### ` line, then `Commit:` after the closing fence, same card" shape from the
     bug report; no hand-built batch string is needed for this repro). Create `project_root /
     "src" / "a.py"` on disk (needed for `non-existent-path` to stay clean) before writing the
     plan. Run `_plan_validate.run(plan_dir, project_root)`, filter
     `e["check"] == "card-missing-field"` -> assert the filtered list is empty (pre-fix, this
     fixture produces a spurious `Commit:`-missing finding because `_parse_cards` truncates the
     card at the fenced `### Some Heading` line).
  2. `test_check_card_missing_field_fence_guard_real_boundary_still_detected` — regression guard
     proving the fence guard doesn't over-suppress a genuine card boundary. Hand-build a two-card
     batch file text (following the same concatenation style as
     `test_check_cards_legend_in_comment_not_parsed_as_refs`'s `dirty_text`/`clean_text`
     construction: frontmatter string + `"## Cards\n\n"` + card blocks): Card 1's `Requirements:`
     contains a fenced block with a `### Not A Real Heading` line inside it (same shape as test
     1's fence, different heading text so the two tests are visibly distinct), followed by its own
     `Commit:` field, then a real `### Card 2: card 2` heading with all 7 required fields
     (`Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:` all `none`, `Requirements:` "See scope.",
     `Commit: feat(alpha): card 2`). Set the overview's batch entry and frontmatter `cards: 2` to
     match. Run `_plan_validate.run(plan_dir, project_root)` (with an empty, real `project_root`
     directory — no `src/a.py` needed since both cards use `none`/no-path fields), filter on both
     `"card-missing-field"` and `"card-numbering"` -> assert both filtered lists are empty (proves
     card 2 was correctly recognized as a real, separate, sequentially-numbered card with all its
     own required fields intact, not swallowed into or duplicated from card 1).

  Register both new test function names in `main()`'s `tests` list, immediately after the
  existing `test_check_cards_legend_in_comment_not_parsed_as_refs` entry (i.e. before the
  `# verify-excludes-edited-tagged-test check (#724)` comment in that list), in the order authored
  above.
- **Commit:** `test(plan-validate): cover fence-aware card boundary parsing (#776)`

### Card 5: Fix mill-plan's own step-1.5 mechanical-fix table row for the renamed message

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Card 1 changes `_check_verify_excludes_edited_tagged_test`'s finding `message` to end
  `f"...lacks a matching -tags flag naming '{sorted(tags)[0]}'"` instead of the fixed string
  `"-tags ...integration... flag"`. This skill's own `### Phase: Plan Review` Step 1.5 mechanical
  fix-table has one row keyed `verify-excludes-edited-tagged-test` whose cell text currently reads:
  `Open the offending batch's verify: command (payload's batch/path fields name the batch and the
  tagged test file). If a -tags flag already exists, append ,integration to its value; otherwise
  append " -tags integration" to the command.` Left unchanged, this row would keep appending the
  literal word `"integration"` even when Card 1's generalized check reports a different discovered
  tag (e.g. `"scout"` or `"smoke"`) — reproducing bug 1's exact hardcoded-tag failure class one
  layer up, inside mill-plan's own fix automation, for every non-`"integration"` finding once
  Card 1 ships. Replace that row's cell text with: `Open the offending batch's verify: command
  (payload's batch/path fields name the batch and the tagged test file; the payload's message
  field names the missing tag in its trailing "naming '<tag>'" fragment). If a -tags flag already
  exists, append ,<tag> to its value; otherwise append " -tags <tag>" to the command.` Keep the
  row's table-cell structure (leading `|`, trailing ` |`, single-row-single-line format) identical
  to every sibling row in the same table — this is a same-row text substitution, not a table
  restructuring.
- **Commit:** `docs(mill-plan): fix-table row for verify-excludes-edited-tagged-test names the discovered tag, not "integration"`

## Batch Tests

`verify:` runs the full `test-plan-validate.py` unit-test file — the only test file covering
`_plan_validate.py`, and both bugs plus their new coverage (Cards 1-4) live entirely inside this
one module/test-file pair. Card 5 edits a `.md` skill file with no automated test surface; its
correctness is reviewed by inspection (single mechanical text substitution), not by `verify:`.
