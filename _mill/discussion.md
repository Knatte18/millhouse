# Discussion: _plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps

```yaml
task: _plan_validate.py: further context-completeness, fence/indent-drift, and tag-exclusion gaps
slug: plan-validate-context-completeness-round2-gaps
status: discussing
parent: main
```

## Problem

`plugins/mill/scripts/_plan_validate.py` gates every `mill-plan` run (Step 1.5's self-validate loop): its
`context-completeness`, `requirements-quote-indent-drift`, `move-target-collision`, and
`verify-excludes-edited-tagged-test` checks catch real authoring bugs, but their heuristics also produce
false positives (and one false negative) that cost real planner time to work around — rephrasing prose,
stripping backticks, inventing unsanctioned `skip_checks`, or silently producing an `IndentationError`
that only a later LLM review round catches.

This task bundles a second round of ten such feedback reports (issues #1109, #1099, #1070, #1053, #1052,
#1050, #1079, #1075, #1074, #1044), gathered from real `mill-plan` runs on `loomyard` (Go), `Models` (C#),
and this repo (`millhouse`) itself, distinct from the already-completed "symbol-branch" and "path-branch"
false-positive tasks that preceded it.

## Scope

**In:**

- `_check_move_target_collision`: stop flagging a `Moves:` target that collides only with an
  in-plan `Moves:` *source* slated to vacate that path (intra-plan rename chains). (#1052)
- `_card_own_reference_set`: include a card's own `Moves:` *target* tokens (not just sources), so
  `context-completeness` stops flagging a rename card's own destination path in its `Requirements:`.
  (#1053)
- `_check_context_completeness` symbol branch:
  - New plan-wide "declared symbol" exemption: a bare identifier that some card's `Requirements:`
    declares as a new function-signature parameter or struct-literal field is not resolved as an
    unlisted dependency. (#1070, and the declaration-exemption half of #1050)
  - `_resolve_symbol_files` must never resolve a symbol to a conventional test file (`_test.go`,
    and the equivalent conventions for `.py`/`.cs`/`.ts`). (the test-file half of #1050)
  - `_symbol_candidate_shape`: gate out single-character bare identifiers and single-character
    dotted qualifiers (`t.Cleanup`-shaped tokens). (#1099's single-letter symptom, #1109)
  - `_resolve_symbol_files`'s `.cs` member-declaration regex (`cs_member_re`): stop matching a
    `throw new X(...)` / `= new X(...)` construction as if `X` were a declared member. (#1099's
    `InvalidOperationException` symptom)
- `_check_requirements_quote_indent_drift`: new detection for a new-code fence that immediately
  follows a byte-matched anchor fence in the same card but is indented differently from it.
  (#1074, #1075)
- `mill-plan/SKILL.md`'s Step 1.5 fix-table: rewrite the `verify-excludes-edited-tagged-test` row so
  its guidance scopes the added `-tags` invocation to the package(s) containing the flagged file(s),
  in both its "no `-tags` flag yet" and "`-tags` flag already exists" branches, instead of reusing
  the (possibly multi-package) verify command's own package pattern. (#1044)
- Fix-table rows updated to describe the new/changed check behavior: `move-target-collision` (#386),
  `requirements-quote-indent-drift` (#391).
- Unit test coverage for every fix above, following `test-plan-validate.py`'s existing conventions.

**Out:**

- #1079 (context-completeness fence detection disagreeing with indent-drift's, missing indented
  fences): **already fixed**, no action needed here — see Decision `fence-detection-already-fixed`.
- A hardcoded BCL/stdlib type-name denylist (part of #1099's suggested fix) — see Decision
  `no-bcl-denylist`.
- Generalizing the new indent-drift detection to arbitrary "insert after/before `<anchor>`" prose
  (the fully general form #1075 gestures at) — only the structural paired-fence case is implemented;
  see Decision `paired-fence-only`.
- Struct-field-shaped same-plan declarations that aren't written as a parenthesized signature or a
  `{...}`-braced literal in some card's `Requirements:` — the new `declared symbols` exemption is
  restricted to that syntactic shape; a plain-prose declaration with no such fence/backtick shape is
  not covered. See Decision `declared-symbols-shape-limit`.
- Any change to `.go`/`.py`/`.ts` declaration-detection regexes in `_resolve_symbol_files` — only the
  `.cs` member regex is touched (#1099's demonstrated false positive is `.cs`-specific).
- Any change to `_check_move_source_missing` — it already suppresses correctly via plan-wide
  `moves_targets` (the mirror image of the `_check_move_target_collision` fix here).

## Decisions

### intra-plan-move-chain

- Decision: `_check_move_target_collision` gains a new parameter `moves_sources: set[str]` (the same
  plan-wide union `run()` already computes at `_plan_validate.py:4163` via `compute_moves_union` and
  threads into `_check_context_completeness`). Condition 1 ("target already exists on disk") is
  suppressed when the target is also a member of `moves_sources` — the file currently occupying that
  path is itself a `Moves:` source somewhere in the plan and will vacate before/independently of this
  target being written.
- Rationale: `_check_move_source_missing` (line 479) already suppresses its own symmetric case
  ("source doesn't exist yet") via the plan-wide `moves_targets` set — "chained moves ... do not
  generate a false positive". `_check_move_target_collision` never received the mirror-image
  treatment for its own condition 1. Threading `moves_sources` plan-wide (not just same-batch) is
  consistent with that existing precedent and is a strict superset of the reported same-batch repro
  (`a.go -> b.go`, `b.go -> c.go` in one batch).
- Rejected: scoping the fix to same-batch chains only (matching the issue's literal repro) — rejected
  because the plan-wide set is already computed, already used the same way by the sibling check, and
  a cross-batch chain (batch 1 moves `a->b`, batch 2 moves `b->c`) would hit the identical false
  positive with no principled reason to leave it unfixed.
- Rejected: re-ordering/simulating the Moves: sequence to detect "occupied only by an earlier pair's
  source" (the issue's own literal suggestion) — rejected as unnecessarily stateful; the set-membership
  check is O(1) per target and produces the same outcome without needing an ordering model, matching
  how `moves_targets`/`moves_sources` are used everywhere else in this file (unordered plan-wide sets).

### move-target-own-card-exemption

- Decision: `_card_own_reference_set` (line 1971) additionally collects the *destination* half of a
  card's own `Moves:` pairs (today it only collects the source half — see the docstring's explicit
  "the destination half is deliberately excluded" note, which this task reverses).
- Rationale: #1053's repro is exactly the normal case, not a defect: the card performing a rename is
  the one card whose `Requirements:` must describe what happens to the destination. `Creates:` targets
  are already exempt in their own declaring card via this same mechanism; `Moves:` targets deserve
  identical treatment, per the issue's own suggested fix ("treat Moves targets like Creates targets").
- Rejected: adding a *plan-wide* Moves-target exemption (mirroring how `moves_sources` is plan-wide) —
  rejected because a card OTHER than the one declaring the `Moves:` pair citing that not-yet-existing
  destination in prose is a much weaker signal of "this is fine" than the declaring card citing its
  own operation; scope the exemption to the declaring card only, matching `Creates:`'s own scope
  (`_card_own_reference_set` is inherently a same-card mechanism for every other field already).

### declared-symbols-exemption

- Decision: add a new module-private helper `_compute_declared_symbols_union(plan_dir: Path) -> set[str]`
  in `_plan_validate.py` (not `_review_common.py` — this extraction is specific to context-completeness's
  symbol branch, mirroring `_build_creates_declaring_card_map`'s existing placement as a plan-wide,
  check-specific helper local to this module). For every card in the plan, scan its
  `Requirements:` text (via `_requirements_fence_aware_body`, matching how the check itself already
  reads the field) for every backtick token containing a balanced `(...)` or `{...}` — a
  function-signature- or struct-literal-shaped citation. Take the substring between the first `(`/`{`
  and the matching last `)`/`}`, split it on `,`/`;`, and for each non-empty clause add BOTH its first
  and its last whitespace-separated word to the set when that word matches a bare-identifier shape
  (`^[A-Za-z_]\w*$`) — first word covers `name Type` order (Go), last word covers `Type name` order
  (C#/TS). Thread the resulting plan-wide `declared_symbols` set into `_check_context_completeness` as
  a new keyword-only parameter defaulting to `None` (materialized to `set()`), matching
  `creates_declaring_card_map`'s existing optional-parameter convention (this keeps the one direct-call
  unit test at `test-plan-validate.py:6165` passing unchanged). In the symbol branch, immediately after
  computing `search_key` (before calling `_resolve_symbol_files` at all — this also skips a needless
  filesystem walk), skip when `search_key in declared_symbols`.
- Rationale: this is the symbol-branch's missing equivalent of the path branch's existing "Forward
  cross-card Creates" exemption (#7 in the check's docstring) — a plan that introduces its own new
  identifier in prose (a parameter name, a struct field) must not have that identifier treated as an
  unlisted dependency merely because an unrelated same-named symbol exists elsewhere in the repo.
  Building the set plan-wide (not same-card-only) covers both #1070 (same card declares and uses the
  name) and the declaration side of #1050 (an earlier card declares it, a later card's prose uses it) —
  the same "plan-wide, not just the declaring card" pattern `moves_sources`/`creates_union` already
  establish for the path branch.
- Rejected: a same-card-only exemption (matching #1070's literal repro) — rejected because #1050's
  repro is explicitly cross-card, and the plan-wide set costs nothing extra to compute or check.
- Rejected: attempting true signature parsing (AST-level Go/C#/TS parsing) to extract exact parameter
  names precisely — rejected as far outside this validator's text-heuristic design (every other check
  in this file is regex/text based, not AST based) and unnecessary: the false-positive cost of
  over-collecting a few extra candidate words (e.g. a type name) is a silent, harmless no-op (see
  Decision `declared-symbols-shape-limit`), not a new false negative anyone has reported.

### declared-symbols-shape-limit

- Decision: the `declared_symbols` exemption above only recognizes identifiers cited inside a
  parenthesized or braced backtick token. A struct field or parameter introduced purely in plain
  prose, with no such fenced/backtick shape, is not exempted by this mechanism.
- Rationale: this is an explicit, disclosed scope boundary (see Scope: Out). #1050's own repro
  (`Acquire` as a struct field "the plan itself declares in an earlier card") is not fully
  reproducible from the issue text alone (the originating file isn't in this repo), so this task
  implements the mechanically well-defined, syntactically-anchored version of the fix rather than
  guessing at a fully general "any new identifier mentioned anywhere" detector, which would have an
  unbounded false-negative surface of its own (indistinguishable from a real unlisted dependency
  without deeper analysis).
- Rejected: matching on prose verbs ("declares", "the new field", "defines") the way
  `_is_prohibition_exempt`/`_is_cross_card_ownership_exempt` match ownership/negation phrasing —
  rejected because those exemptions gate on a clear, closed verb list describing the CARD's own
  relationship to a token it already knows about; "does this repo-wide same-named symbol match the
  NEW thing this plan introduces" is a existence question a verb list cannot answer.

### test-file-exclusion

- Decision: `_resolve_symbol_files` never counts a conventional test file as a match, for every
  language in `_SYMBOL_SEARCH_EXTENSIONS`. Add a helper `_is_conventional_test_file(path: Path) -> bool`:
  `.go` → stem ends with `_test`; `.py` → stem starts with `test_` or ends with `_test`; `.cs` → stem
  ends with `Test` or `Tests`; `.ts` → stem ends with `.test` or `.spec` (e.g. `Path("foo.test.ts").stem
  == "foo.test"`). Applied in the same per-file loop that already checks
  `file_path.suffix not in _SYMBOL_SEARCH_EXTENSIONS` (skip before ever reading the file's content).
- Rationale: #1050 reports this for `.go` specifically, but the underlying principle — "a card should
  never be told to add another package's test file to its read-only Context: allowlist" — is
  language-agnostic and matches how `_has_declaration` already branches per-language uniformly.
  Generalizing avoids leaving the identical bug open for the other three languages this same check
  already supports.
- Rejected: scoping the fix to `_test.go` only (matching the literal repro) — rejected as an
  inconsistent, arbitrary language carve-out with no reason a `.py`/`.cs`/`.ts` test file should be
  treated differently.

### single-letter-gate

- Decision: `_symbol_candidate_shape`'s inner `qualifies()` helper additionally requires
  `len(segment) > 1` (alongside the existing not-all-lowercase-or-underscore test). For a dotted
  two-segment token, ALSO require the qualifier segment (`segments[0]`) to be longer than one
  character — when it isn't, return `None` for the whole token (not just skip qualifier-based
  disambiguation), since a single-letter qualifier carries no reliable type information at all.
- Rationale: directly resolves #1109 (`t.Cleanup`, qualifier `t`) and the "`A`, `B`, `D`" bare-token
  symptom of #1099. Single-letter receiver/loop/parameter variables are near-universal convention
  across Go/C#/TS/Python and essentially never disambiguate a real project-specific type — the
  qualifier-based filtering path (`_filter_matches_by_qualifier`) only ever runs when a search already
  produced 2+ matches, so it can't help when (as in `t.Cleanup`) there is exactly one filesystem match;
  the only fix that reaches that case is refusing to treat the token as symbol-shaped at all.
- Rejected: a stdlib-receiver-name denylist (`t`, `tb`, `ctx`, `err`, …) — rejected in favor of the
  simpler, more general length-based rule, which needs no per-language vocabulary and covers the same
  cases (every idiomatic single-letter receiver is, definitionally, one character).

### cs-member-regex-tightening

- Decision: `cs_member_re` (in `_resolve_symbol_files`, currently
  `r"\b(?:public|private|protected|internal)\b.*\b" + sym + r"\b\s*[({;=]"`) is tightened to forbid
  the literal keyword `new` appearing between the access modifier and the symbol:
  `r"\b(?:public|private|protected|internal)\b(?:(?!\bnew\b).)*?\b" + sym + r"\b\s*[({;=]"`.
- Rationale: the unbounded `.*` between the modifier and the symbol lets an unrelated
  `public ... { ... throw new InvalidOperationException(...); }`-shaped line (or any
  `private ... = new Foo();`-shaped field initializer) match as though `InvalidOperationException`/
  `Foo` were themselves declared members — that's exactly #1099's demonstrated false positive.
  A `new <Symbol>` occurrence is unambiguously a construction expression in C#, never a member
  declaration, so excluding it structurally fixes the mechanism rather than papering over one instance
  of it with a name-specific denylist entry.
- Rejected: requiring the symbol to appear immediately (no `.*` at all) after the modifier — rejected
  because real declarations legitimately have a return type between the modifier and the name
  (`public void Foo(...)`, `public static readonly int Bar = ...`) and the type token varies too much
  to enumerate.

### no-bcl-denylist

- Decision: no hardcoded list of "well-known BCL/stdlib type names" is added, despite #1099
  suggesting one.
- Rationale: `cs-member-regex-tightening` and `single-letter-gate` together resolve every concretely
  demonstrated false positive in #1099 and #1109 by fixing the underlying resolution mechanism, not by
  special-casing specific names. A denylist would need independent, ever-growing upkeep per language
  (.NET BCL, Go stdlib, Python stdlib, TS/DOM lib) with no natural end state, and would still miss any
  exception/type name not yet added to it — a structural fix generalizes; a name list doesn't.
- Rejected: (see above) — the suggestion is reasonable defense-in-depth but out of proportion to what
  the demonstrated repros actually require.

### paired-fence-indent-check

- Decision: `_check_requirements_quote_indent_drift` gains a new detection branch. While iterating a
  card's `fence_bodies` in order, track `last_matched_indent: int | None`, reset to `None` at the start
  of each card. After a fence is found byte-exact-clean, or matches via the strip pass, or matches via
  the add pass: set `last_matched_indent` to that fence's own raw (as-authored) first-non-blank-line
  leading-space count. After a fence matches in NEITHER direction (today's silent "illustrative
  snippet" skip): if `last_matched_indent is not None`, compute this fence's own raw first-non-blank-
  line leading-space count and compare; a mismatch emits a new `requirements-quote-indent-drift`
  finding (same check name, new message: `"card {card_num}'s Requirements: fence {fence_idx} (new/
  replacement code) immediately follows matched fence {fence_idx-1}, but its first line is indented
  {sibling_indent} spaces vs the anchor fence's {anchor_indent} spaces"`, `path` = the anchor fence's
  own matched `Edits:` token). Regardless of whether a mismatch was found, reset
  `last_matched_indent = None` after processing an unmatched fence — the check only ever compares one
  fence against the single anchor immediately preceding it, never chains across multiple consecutive
  unmatched fences.
- Rationale: unifies #1074 and #1075, which report the identical underlying gap (the docstring's own
  "matching in neither direction ... is silently skipped -- never flagged" branch) from two different
  angles. #1074's own suggested fix explicitly frames this as the paired
  "Replace:-quote immediately followed by an unmatched with:-fence" structural case, and states that
  "even just the paired-fence case would have caught both instances observed here" — covering #1075's
  repro too (a byte-matched anchor immediately followed by a new-code insertion fence).
- Rejected: requiring literal "Replace:"/"with:" phrasing markers before applying the check — rejected
  because neither repro depends on that literal wording (#1075's repro has no such marker at all), and
  requiring it would make the fix fragile to phrasing rather than structure.
- Rejected (see `paired-fence-only` in Scope: Out): the fully general "insertion at a named function's
  body indent" detection #1075 gestures at — its own text calls this "likely much harder and may not be
  worth it," and the narrower paired-fence case already resolves both concrete reports.

### verify-tags-package-scoping

- Decision: rewrite the `verify-excludes-edited-tagged-test` fix-table row in
  `plugins/mill/skills/mill-plan/SKILL.md` (currently line 395). Both branches change: derive the
  affected package pattern(s) from the flagged file's own directory (the payload's `path` field, e.g.
  `internal/reedcli/foo_test.go` → package pattern `./internal/reedcli/`) rather than reusing the
  existing verify command's own (possibly multi-package) pattern. "No `-tags` flag yet" branch: append
  a new ` && `-chained invocation of the same base command's verb, scoped ONLY to the affected
  package(s), carrying `-tags <tag>` — never append `-tags` to the existing multi-package invocation in
  place. "`-tags` flag already exists" branch: same package-scoping applies to the new chained
  invocation this branch already prescribes (today's wording says "same ... package pattern as the
  existing invocation," which inherits the identical multi-package risk if the existing invocation is
  itself multi-package) — reword to scope to the flagged file's package(s) instead.
- Rationale: this row is pure prose guidance consumed by the LLM self-fix pass at mill-plan Step 1.5 —
  `_check_verify_excludes_edited_tagged_test` (the detector) is unaffected and needs no code change.
  #1044's repro is a 4-package `go test ./a/ ./b/ ./c/ ./d/` command where the naive "append -tags in
  place" guidance would silently enable the tag across all 4 packages, changing what compiles/runs in
  3 unrelated ones. The already-exists branch's existing wording has the same latent multi-package risk
  even though #1044 didn't demonstrate it — fixing both keeps the row internally consistent.
- Rejected: leaving the already-exists branch untouched (fixing only the literally-reported branch) —
  rejected because it shares the identical root cause and an inconsistent row would read as an
  oversight, not a design choice, to the next planner who hits it.

### fence-detection-already-fixed

- Decision: no code change for #1079. Verified against current `_plan_validate.py`
  (`plugins/mill/scripts/_plan_validate.py:2668`, `:2684`, `:2966-3007`, `:3078`) with a direct
  reproduction of the reported repro (a 2-space-indented fence quoting a path inside a card's
  `Requirements:`): both `_check_context_completeness` and `_check_requirements_quote_indent_drift`
  now share `_requirements_fence_aware_body` for locating the field body, and both toggle their own
  `in_fence` state via `line.lstrip().startswith("\`\`\`")` (leading-whitespace-tolerant), not the
  strict `line.startswith("\`\`\`")` the issue describes. This was already fixed by commit `599a2c1b`
  ("_plan_validate.py: subprocess trace noise, batch-oversized TDD cap, unrelated-test-file and
  fence-unaware parser bugs", 2026-09-19 15:28 — after #1079 was filed at 13:55 the same day, in a
  different, already-merged task). A regression test already exists for the closely-related #992
  scenario (`test_context_completeness_survives_indented_delimiter_column_zero_field_header_in_fence`
  in `test-plan-validate.py`).
- Rationale: CLAUDE.md's own "Task-worktree path for source verification, not CLAUDE_PLUGIN_ROOT"
  rule exists precisely to catch this — trusting the (now-stale) issue text instead of the current
  worktree source would have produced an incorrect plan re-fixing an already-fixed bug.
- Rejected: adding a regression test anyway "just in case" — rejected per YAGNI; the closely-related
  `#992` regression test already exercises the shared fence-toggle mechanism both checks rely on, and
  this task's own repro (recorded below in Testing) confirms current behavior directly.

## Technical context

All work is in `plugins/mill/scripts/_plan_validate.py` (4237 lines) plus one documentation-only edit in
`plugins/mill/skills/mill-plan/SKILL.md`. Read the actual code at these locations before writing the
plan — the task-worktree copy, not any plugin cache.

- `_check_move_target_collision` — `_plan_validate.py:541`. Called from `run()` at line 4227 without
  `moves_sources` today; `run()` already computes `moves_sources, moves_targets =
  compute_moves_union(plan_dir)` at line 4163 and threads `moves_sources` into
  `_check_context_completeness` at line 4200 — the same variable is available to thread into this call
  too.
- `_check_move_source_missing` — `_plan_validate.py:479` — the existing symmetric precedent
  (`src not in moves_targets` suppression) to mirror.
- `_card_own_reference_set` — `_plan_validate.py:1971`. Its Moves:-pair walk (lines 2002-2018) currently
  adds only `pair_m.group(1)` (the source); add `pair_m.group(2)` (the target) too. Update the
  docstring, which currently states the opposite ("the destination half is deliberately excluded").
- `_check_context_completeness` — `_plan_validate.py:2520`. Symbol branch is lines 2845-2883. The shape
  gate (`is_path_shaped` / `_symbol_candidate_shape`) is at lines 2694-2699; add the `declared_symbols`
  skip immediately after `search_key, qualifier = shape_result` (before any of the existing exemption
  checks, since it applies to raw candidacy, not line-phrasing). `creates_declaring_card_map`'s
  `None`-default-then-materialize pattern (lines 2646-2647) is the template for the new parameter.
  `run()`'s call site is at lines 4198-4204.
- `_resolve_symbol_files` — `_plan_validate.py:2091`. The per-file loop is lines 2200-2217;
  `_SYMBOL_SEARCH_EXTENSIONS` is defined at line 1822. `cs_member_re` is defined at line 2149-2151.
- `_symbol_candidate_shape` — `_plan_validate.py:2040`. `qualifies()` closure is lines 2081-2082;
  the two return points are lines 2085 (bare) and 2088 (dotted).
- `_check_requirements_quote_indent_drift` — `_plan_validate.py:3010`. The per-fence loop is lines
  3106-3168; the clean/strip/add three-way branch is exactly where `last_matched_indent` bookkeeping
  slots in. `_strip_n_leading_spaces`/`_add_n_leading_spaces` (lines 2888-2928) are the existing
  per-line indent helpers — reuse their "count leading spaces, skip blank lines" convention for the new
  first-non-blank-line indent helper rather than inventing a third convention.
- `compute_moves_union`, `compute_creates_union`, `compute_deletes_union` — `_review_common.py:879-978`
  — the existing plan-wide-union pattern (glob `??-*.md` excluding `00-overview.md`, iterate, union) to
  mirror in the new `_compute_declared_symbols_union` helper. Per Decision `declared-symbols-exemption`,
  the new helper belongs in `_plan_validate.py` itself (like `_build_creates_declaring_card_map`), not
  `_review_common.py`, since nothing outside context-completeness needs it.
- `mill-plan/SKILL.md` fix-table — lines 372-403. Rows to edit: `move-target-collision` (386),
  `context-completeness` (390, only if a plan-writer judges the new exemption needs a mention — it adds
  no new message shape, so likely no edit needed there), `requirements-quote-indent-drift` (391, new
  message-shape clause), `verify-excludes-edited-tagged-test` (395, full rewrite per Decision
  `verify-tags-package-scoping`).
- Unit tests: `plugins/mill/unit_tests/test-plan-validate.py`. Existing helpers `_make_overview`,
  `_make_batch_file`, `_write_plan` build fixtures; `_plan_validate.run(plan_dir, project_root)` is the
  standard end-to-end entry point most tests use. The one direct-call exception is
  `test_check_context_completeness_direct_call_forward_map_default` at line ~6118 (calls
  `_check_context_completeness` positionally through `moves_targets` only) — the new `declared_symbols`
  parameter must be keyword-only with a `None` default so this test keeps passing unmodified.
  `test_context_completeness_survives_indented_delimiter_column_zero_field_header_in_fence` (line 11979)
  and its sibling `test_check_card_missing_field_indented_delimiter_column_zero_heading_clean` (line
  11938) are the existing #992 regression tests confirming the fence-toggle mechanism Decision
  `fence-detection-already-fixed` relies on — no changes needed to them, just awareness they already
  cover the shared mechanism.

## Testing

TDD candidates, one test (at minimum) per Decision above, following `test-plan-validate.py`'s existing
naming convention (`test_<check_name>_<scenario>`):

- **intra-plan-move-chain**: a batch with `Moves: a.go -> b.go` and `Moves: b.go -> c.go` (both in one
  batch, matching the reported repro) produces zero `move-target-collision` findings; a second test with
  the chain split across two batches (cross-batch) also produces zero findings, confirming the plan-wide
  (not same-batch-only) scope. A third negative test: a genuine collision (target exists on disk and is
  NOT any batch's Moves: source) still fires.
- **move-target-own-card-exemption**: a card with `Moves: old.go -> new.go` whose `Requirements:` cites
  `` `new.go` `` produces zero `context-completeness` findings; a negative test confirms a DIFFERENT
  card citing the same not-yet-existing Moves: target (not its own declaring card) still fires.
- **declared-symbols-exemption**: (a) same-card case — a card whose `Requirements:` backtick-quotes a
  function signature `` `planReapCycle(live []string, inFlight map[string]bool)` `` and separately
  references `` `inFlight` `` produces zero findings, in a repo containing an unrelated file with a
  real `inFlight` declaration. (b) cross-card case — an earlier card's Requirements: quotes
  `` `type Deps struct { Acquire func() error }` ``, a later card references `` `Acquire` ``: zero
  findings. (c) negative test — a token NOT present in any signature/struct-shaped backtick anywhere in
  the plan still resolves and fires normally.
- **test-file-exclusion**: a repo where the only real declaration of a search key lives in a
  `_test.go`/`test_*.py`/`FooTests.cs`/`foo.test.ts` file, referenced from a card's Requirements: prose
  by bare symbol name, produces zero findings (the token is unresolvable-with-confidence once the test
  file is excluded, same as the existing "zero or ambiguous matches" no-op path).
- **single-letter-gate**: `` `t.Cleanup` `` referencing a real `Cleanup` declaration elsewhere produces
  zero findings; a bare single-letter token like `` `A` `` (illustrative step name) produces zero
  findings even when a file coincidentally declares a symbol literally named `A`.
- **cs-member-regex-tightening**: a `.cs` repo with a line like
  `public void Foo() { throw new InvalidOperationException("x"); }`, referenced via
  `` `InvalidOperationException` `` in a card's Requirements:, produces zero findings (previously would
  have matched). A positive/regression test confirms a genuine member declaration
  (`public InvalidOperationException Custom { get; }` or similar, no `new` between modifier and symbol)
  still matches and still fires when uncited.
- **paired-fence-indent-check**: (a) a card with a byte-matched anchor fence (2-space list-continuation
  indent) immediately followed by a new-code fence at a DIFFERENT indent (matching #1074/#1075's
  "22/26-space instead of 20/24-space" repro shape) produces one new-shape
  `requirements-quote-indent-drift` finding. (b) the same setup with matching indents produces zero
  findings. (c) an unmatched fence NOT immediately preceded by a matched one (e.g. two illustrative
  fences in a row, or a matched fence separated from an unmatched one by intervening prose text but
  still within the same Requirements: field — clarify during planning whether "immediately follows"
  means adjacency within the parsed `fence_bodies` list, which is what this task implements) produces
  no new-shape finding.
- **fence-detection-already-fixed**: no NEW test required (existing #992 regression tests already cover
  the shared mechanism), but the plan should record that this task's own repro
  (documented above) was run against current code and produced zero findings, confirming no regression
  exists before closing #1079 as already-fixed.
- **verify-tags-package-scoping**: documentation-only change — no unit test applies; the plan should
  note this row is prose consumed by an LLM self-fix pass, not executable code, per Decision
  `verify-tags-package-scoping`'s rationale.

## Q&A log

- **Q:** Should mill-start interview an operator about each of these 10 bundled issues one at a time?
  **A:** [auto-pick] No — the task ran in `--auto`-equivalent unattended mode (no operator present).
  Each issue's own repro and suggested fix (read via `gh issue view`) was treated as the requirements
  source, verified against current worktree code before committing to a design, per this task's own
  operating instructions. **Why:** matches the instruction to treat the task body as what a human would
  otherwise have supplied in conversation, with actual code taking priority when it disagrees.
- **Q:** #1079 (fence detection disagreement) — implement the described fix, or verify first?
  **A:** [auto-pick] Verify against current code first. **Why:** CLAUDE.md's "Task-worktree path for
  source verification" rule exists exactly to prevent re-fixing an already-fixed bug from stale issue
  text; verification found the fix already landed in commit `599a2c1b` (see Decision
  `fence-detection-already-fixed`).
- **Q:** For the `declared_symbols` exemption, how should a same-plan declared identifier be detected —
  same-card only, or plan-wide? **A:** [auto-pick] Plan-wide, computed once per `run()` call, mirroring
  `moves_sources`/`creates_union`'s existing plan-wide scope. **Why:** #1050's repro is explicitly
  cross-card (an earlier card declares, a later card cites), so a same-card-only mechanism would leave
  half the bundled reports unfixed.
- **Q:** Should the new indent-drift paired-fence check require "Replace:"/"with:" phrasing markers, or
  fire on pure structural adjacency? **A:** [auto-pick] Pure structural adjacency (no phrasing
  requirement). **Why:** #1075's repro has no such marker at all, and #1074's own text says the
  paired-fence case alone (without phrasing detection) already covers both reports.
- **Q:** Should `verify-excludes-edited-tagged-test`'s fix-table fix touch only the reported
  ("no -tags yet") branch, or also the "already exists" branch that shares the same latent risk?
  **A:** [auto-pick] Fix both branches for consistency. **Why:** leaving one branch with an
  undisclosed, structurally-identical bug would read as an oversight to the next planner who hits it;
  the fix-table is prose, so extending it costs nothing beyond wording.
- **Q:** Add a hardcoded BCL/stdlib type-name denylist as #1099 suggests, alongside the structural
  regex/qualifier-length fixes? **A:** [auto-pick] No. **Why:** the structural fixes (cs_member_re
  tightening, single-letter qualifier gate) resolve every demonstrated repro; a denylist would need
  unbounded per-language upkeep for no additional demonstrated benefit. Documented as Decision
  `no-bcl-denylist`.
