# Batch: context-completeness-check

```yaml
task: 'mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check'
batch: context-completeness-check
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-validate.py
depends-on: []
```

## Batch Scope

This batch adds the `context-completeness` heuristic validator check (#742) to `_plan_validate.py` — a new `_check_context_completeness` function wired into `run()` — plus its unit test coverage. It is self-contained: no dependency on the SKILL.md prose changes in Batch 02, even though Batch 02's Card 6 documents this batch's exact behavior in the Step 1.5 fix table (hence Batch 02 depends on this one, not the reverse).

## Cards

### Card 1: Add `_check_context_completeness` and wire it into `run()`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `_check_context_completeness(batch_files: list[Path], project_root: Path, root: str | None, creates_union: set[str], *, wiki_root: Path | None = None, git_root: Path | None = None) -> list[dict]` to `plugins/mill/scripts/_plan_validate.py`, placed immediately after `_check_plugin_manifest_context_missing` (after its closing `return errors` at line 1357) and before the `# Check 8 — all-files-touched-mismatch` section comment at line 1361.

  For each batch file, call the existing `_parse_cards(batch_text)` (line 117) to get `(card_num, card_lines)` pairs, then join `card_lines` into `card_text` with `"\n".join(card_lines)` (the same pattern `_check_card_missing_field` uses at line 748).

  Locate this card's `Requirements:` field: search `card_text` for the header line matching `^-\s*\*\*Requirements:\*\*` (the same header-line regex shape `_check_card_missing_field` builds per-field at lines 750-752, applied here to the literal field name `Requirements`), then take that line's text after the header plus every subsequent line up to (but not including) the next `- **<Field>:**` header line or the end of `card_text`, as `requirements_text`.

  Extract every backtick-quoted token from `requirements_text` using the same backtick-capture regex `_check_ref_not_backtick_path` already applies inline at line 1181 (a raw-string pattern matching one or more non-backtick characters enclosed in a pair of backticks). For each token, treat it as a path-candidate only if it contains a `/` or ends with one of `.py`, `.go`, `.cs`, `.ts`, `.md`, `.yaml`, `.yml`, `.json`. Skip non-path-candidate tokens silently (no finding).

  **Prohibition-marker exemption.** Before testing resolvability, find the single line within `requirements_text` that contains the token's backtick-wrapped occurrence. If that line, lowercased, contains any of the substrings `"forbid"`, `"never touch"`, `"must not touch"`, `"do not touch"`, `"not touch"`, skip the token silently (no finding) — the token names a file the card explicitly must NOT act on, not an unlisted read dependency. This exemption is required because a prohibition sentence (e.g. "forbid touching `` `mill-config.yaml` ``") is itself a legitimate, resolvable-file reference that would otherwise false-positive: this exact plan's own Batch 02 Card 3 contains such a sentence, and `mill-config.yaml` resolves against this repo's real top-level file.

  **Line-range suffix stripping.** Before testing resolvability and before matching against the combined set (below), strip a trailing line-range suffix from the token using the module's existing `_RE_LINE_RANGE` pattern (line 94: matches `:NN-NN` at the end of a token) via `_RE_LINE_RANGE.sub("", token)`. Use this stripped form for the `resolve_existing_paths(...)` call, the `creates_union` membership test, and the combined-set membership test described below. Continue to use the ORIGINAL (unstripped) token in the emitted error dict's `"path"` field, so the message shows exactly what the Requirements: text wrote. Without this stripping, a line-range-suffixed citation (a style already used elsewhere in this codebase's plans, e.g. Card 2's own `` `plugins/mill/unit_tests/test-plan-validate.py:93-155` `` reference below) would never resolve as an existing path and would be silently — and wrongly — treated as a non-path token.

  For each path-candidate token surviving the prohibition-marker exemption, determine resolvability by calling `resolve_existing_paths([stripped_token], project_root, root, wiki_root=wiki_root, git_root=git_root)` (already imported into this module from `_review_common` at line 68). The token is resolvable when that call returns a non-empty list, OR `stripped_token in creates_union`. A path-candidate token that is NOT resolvable is skipped silently (no finding) — this is the false-positive guard: `context-completeness` must never flag a token that is not actually a file reference (e.g. `` `response.json` `` as a JSON-body key), since the alternative (flagging it) would prescribe the actively harmful "add to Context:" remedy, which would itself then trip `non-existent-path` on the very next validator pass.

  For each resolvable token, build this same card's own resolved-reference set:
  1. Inline-extract `Context`/`Edits`/`Creates`/`Deletes` backtick tokens from `card_text` using `_RE_REFS_HEADER` (line 76) to find header lines and `_RE_REFS_SUB` (line 91) to find multi-line sub-bullets — mirror `_parse_edits_only`'s single-line-vs-multi-line traversal (lines 150-189) but scope the traversal to `card_text`'s lines instead of a whole batch file's lines. Collect every backtick token found (using the same backtick-capture regex as line 1181, referenced above) on the relevant inline/sub-bullet text into one combined set.
  2. Separately, extract this card's `Moves:` source-only tokens: find the `Moves:` header line within `card_text` using `_RE_MOVES_HEADER` (line 83) — mirror `_card_field_is_none`'s Moves-specific branch (lines 785-786) to locate it — then for each following `_RE_REFS_SUB`-matched sub-bullet line, apply `_RE_MOVE_PAIR` (line 88) and take only `.group(1)` (the source path; deliberately exclude `.group(2)`, the target). Add each source path into the same combined set from step 1.

  If the resolvable (stripped) token — matched as an exact string against the combined set, OR (when the stripped token contains no `/`) matched by comparing `Path(stripped_token).name` against `Path(entry).name` for each `entry` in the combined set — is absent from the combined set, append one error dict using the ORIGINAL unstripped token: `{"check": "context-completeness", "batch": batch_path.stem, "card": card_num, "path": token, "message": f"card {card_num}'s Requirements: references '{token}' which is not in this card's Context:/Edits:/Creates:/Deletes:/Moves:"}`.

  Wire the new check into `run()`: add `errors.extend(_check_context_completeness(batch_files, project_root, effective_root, creates_union, wiki_root=wiki_root, git_root=git_root))` immediately after the existing `errors.extend(_check_plugin_manifest_context_missing(batch_files))` line (`_plan_validate.py:2275`) and before `errors.extend(_check_all_files_touched_mismatch(overview_path, batch_files))`.

  Add `context-completeness` to the module docstring's "Checks performed (check keys)" list (after the `plugin-manifest-context-missing` entry, lines 41-42), with a one-line description in the same style as neighboring entries, e.g. "`context-completeness` — a card's Requirements: references a resolvable file-path-shaped backtick token absent from that card's own Context:/Edits:/Creates:/Deletes:/Moves:-source".
- **Commit:** `feat(plan-validate): add context-completeness check for Requirements:/Context: cross-reference (#742)`

### Card 2: Add unit tests for `_check_context_completeness`

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  First, extend `_make_batch_file` (`plugins/mill/unit_tests/test-plan-validate.py:93-155`) with a new optional keyword parameter `requirements: str | None = None`. When not `None`, use its value verbatim as the `Requirements:` field's body instead of the hardcoded `"See scope.\n"` text at line 151 (the default `None` must preserve every existing call site's current output byte-for-byte).

  Add these test functions, following the `test_check_<name>_<scenario>` naming convention used throughout this file, each using `tempfile.TemporaryDirectory()` and the existing `_make_overview` / `_make_batch_file` / `_write_plan` fixture helpers:
  - `test_check_context_completeness_clean_in_context`: a card whose `requirements` text contains a backtick file-path token also present in that same card's `context=[...]` list, where the referenced file exists on disk under `project_root` — assert zero `context-completeness` errors from `_plan_validate.run(...)`.
  - `test_check_context_completeness_clean_in_edits`: identical setup but the token is in `edits=[...]` instead of `context=[...]` — assert zero errors.
  - `test_check_context_completeness_clean_in_creates`: identical setup but the token is in `creates=[...]` (a `Creates:` target that does not exist on disk — resolvable via `creates_union`, not disk existence) — assert zero errors.
  - `test_check_context_completeness_dirty_missing`: a card whose `requirements` text references a token that exists on disk but is absent from that card's `context=[...]`, `edits=[...]`, `creates=[...]`, `deletes=[...]`, and `moves=[...]` — assert exactly one `context-completeness` error with `check == "context-completeness"`, `card` equal to the card's number, and `path` equal to the token.
  - `test_check_context_completeness_dirty_missing_scoped_to_own_card`: two cards in the same batch (use `_make_batch_file_cards`-style manual card text, or two separate batch files); the missing token from the previous scenario IS present in a *different* card's `context=[...]`, not the offending card's own — assert the error is still raised (per-card scoping, not batch-wide).
  - `test_check_context_completeness_clean_non_path_token`: `requirements` text contains a backtick token with no `/` and none of the recognized extensions (e.g. `` `_load_config` ``) — assert zero errors (heuristic does not fire on non-path-shaped tokens).
  - `test_check_context_completeness_clean_unresolvable_token`: `requirements` text contains a path-shaped backtick token (e.g. `` `response.json` ``) that does not exist on disk and is not a `Creates:` target anywhere in the plan — assert zero errors (unresolvable tokens are silently skipped, never flagged).
  - `test_check_context_completeness_clean_in_deletes`: `requirements` text names a file present in that same card's own `deletes=[...]` — assert zero errors.
  - `test_check_context_completeness_clean_in_moves_source`: `requirements` text names the source half of a `moves=[(src, dst)]` pair on that same card — assert zero errors.
  - `test_check_context_completeness_dirty_moves_target_only`: `requirements` text names the *target* half of a `moves=[(src, dst)]` pair on that same card, with no matching `context=`/`edits=` entry — assert exactly one error (only the source side is exempted).
  - `test_check_context_completeness_run_wiring_no_false_positives`: a full plan fixture (overview + at least two batches, matching the shape other `test_run_returns_sorted`-style tests use) with exactly one deliberately-broken card producing one `context-completeness` finding — assert the result contains exactly one error with `check == "context-completeness"` and zero errors with any other `check` value.
  - `test_check_context_completeness_clean_prohibition_marker`: `requirements` text contains a sentence such as "forbid touching `` `mill-config.yaml` ``" naming a file that exists on disk and is absent from the card's own `context=[...]`/`edits=[...]`/etc. — assert zero errors (the prohibition-marker exemption skips it; this reproduces the exact false-positive this task's own plan Batch 02 Card 3 exhibited during review).
  - `test_check_context_completeness_clean_line_range_suffix_in_context`: `requirements` text references a line-range-suffixed token (e.g. `` `src/a.py:10-20` ``) whose un-suffixed form is present in the card's own `context=[...]` and exists on disk — assert zero errors (suffix is stripped before matching against the combined set).
  - `test_check_context_completeness_dirty_line_range_suffix_missing`: identical line-range-suffixed token, but its un-suffixed form is absent from the card's own `context=[...]`/`edits=[...]`/etc. and exists on disk — assert exactly one error whose `path` equals the ORIGINAL suffixed token (e.g. `"src/a.py:10-20"`), confirming the suffix is stripped for resolution/matching but preserved in the reported error.

  Register all fourteen new test functions in `main()`'s `tests` list (`plugins/mill/unit_tests/test-plan-validate.py:4394`), grouped under a new `# context-completeness check (#742)` comment placed immediately after the existing `# plugin-manifest-context-missing check` group (after line 4445, before the `# skip_checks filtering (Card 7 / #188)` comment).
- **Commit:** `test(plan-validate): add context-completeness check coverage (#742)`

## Batch Tests

`verify:` runs `run-all.py --only test-plan-validate.py`, which executes every test in `test-plan-validate.py`, including the fourteen new `test_check_context_completeness_*` functions added by Card 2 and every pre-existing test in the file (regression coverage for the `run()` wiring change in Card 1). Scoped to this one file since only `_plan_validate.py` — imported directly by this test module — is touched by this batch; no other test file exercises `_plan_validate.py`.
