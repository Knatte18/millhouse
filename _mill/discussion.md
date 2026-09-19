# Discussion: _plan_validate.py context-completeness: path-token exemption list gaps

```yaml
task: _plan_validate.py context-completeness: path-token exemption list gaps
slug: plan-validate-context-completeness-path-branch-gaps
status: discussing
parent: main
```

## Problem

`_check_context_completeness` in `plugins/mill/scripts/_plan_validate.py` flags a backtick-quoted,
path-shaped token in a plan card's `Requirements:` prose as an unlisted dependency unless one of ten
existing exemptions applies (prohibition markers, citation markers, non-dependency negation,
contrast-citation, quoted material, gitignored paths, out-of-repo literals, directory-intent,
forward cross-card `Creates:`, plan-wide `Moves:` sources — see the numbered list in that function's
own docstring).
Commit `ae07b506` added several of these (negation/citation/contrast/quoted-material) to fix earlier
false-positive reports, but three concrete phrasings still slip through and were re-reported (three
GitHub issues, one already closed against `ae07b506`'s partial fix but still reproducing for these
specific shapes):

- **#1022** — a card's `Requirements:` legitimately names a path to say *another* card/batch owns it
  ("the stale prose reference in `` `.../WellboreDuctTransferEngine.cs` ``, which batch 8 fixes").
  This is a cross-batch handoff statement, not a dependency the card itself reads.
- **#985** — a card's `Requirements:` names a file as an illustrative, rendered-output literal
  ("emitting the bare `` `README.md` ``, never `` `./README.md` ``") — neither string is a file the
  implementer opens; they are the literal values an assertion compares against.
- **#984** (two sub-cases, one of which overlaps #1022's shape):
  - An inline table-driven-test input enumeration ("tables `` `isGlyphTarget` `` over at least
    `` `a/b#C` ``, `` `a/b` ``, `` `#x` ``, `` `a#b#c` ``, `` `README.md` ``, the empty string, and
    `` `.` ``") — `README.md` happens to resolve to a real on-disk file, so it is flagged even though
    it is one literal value in a list of test inputs, not a read dependency.
  - A cross-reference to another numbered card's file ("for the same reason card 23 corrects one
    stale sentence in `` `internal/engine/golang.go` `` and card 9 rewrites the header of
    `` `internal/engine/resolve.go` ``") — the same ownership-attribution shape as #1022, just with
    different verbs ("corrects"/"rewrites" instead of "fixes"/"owns").

Each was previously "fixed" by deleting the path from the prose and describing the file in words —
which makes the plan strictly less precise for the implementer, the opposite of what the check exists
to achieve. All three reports explicitly ask for a lexical exemption template, mirroring what
`ae07b506` already did, not a rewording workaround.

## Scope

**In:**

- Three new exemption mechanisms in `_check_context_completeness`'s exemption chain (documented as
  exemptions 11-13, continuing the existing numbered docstring list):
  1. Same-line cross-batch/cross-card ownership phrasing (`#1022` + the cross-reference half of
     `#984`).
  2. Same-line literal-value enumeration outside a fence (the test-input half of `#984`).
  3. Illustrative-example / rendered-output framing (`#985`).
- Unit tests for each, added to `plugins/mill/unit_tests/test-plan-validate.py`, mirroring the
  existing `test_check_context_completeness_clean_<exemption-name>` /
  `test_check_context_completeness_dirty_<exemption-name>_*` naming convention already used for the
  negation/contrast/quoted-material exemptions.
- A docstring update to `_check_context_completeness` recording the three new exemptions in its
  numbered list, consistent with how exemptions 1-10 are documented today.

**Out:**

- The *symbol* branch's exemptions (bare/dotted-identifier tokens resolved via
  `_resolve_symbol_files`) — that is a separate, already-distinct Home.md entry ("the symbol branch
  above" in this task's own summary) and is not touched here.
- `_PATH_CANDIDATE_EXTENSIONS` / `_SYMBOL_SEARCH_EXTENSIONS` — unrelated to these three phrasings.
- Any new manual escape-hatch marker phrase — `"mentioned, not read"` already exists for a mention no
  structural rule reaches; this task adds *automatic* detection so planners don't have to reach for
  it (or reword prose) for these three shapes specifically.
- A general NLP/semantic parser — every fix here stays lexical/structural, matching the existing
  code's own stated tradeoffs (see `_is_prohibition_exempt`'s and `_CITATION_MARKERS`'s docstrings,
  which both accept line-wide/substring false-negative risk as a known limitation).

## Decisions

### Ownership-phrase exemption (covers #1022 and #984's cross-reference case)

- Decision: add a new exemption function, `_is_cross_card_ownership_exempt(lowered_line)`, mirroring `_is_prohibition_exempt`'s **line-wide** (not clause-scoped) search granularity: it searches the *whole* `Requirements:` line for a regex matching `\b(?:batch|card)\s+\d+\s+(?:'s\s+)?(?:owns?|fixes?|corrects?|rewrites?|addresses?|handles?|resolves?|covers?|edits?|updates?)\b`, independent of the token's own position. The verb set mirrors both issues' exact wording ("fixes", "owns", "corrects", "rewrites") plus close synonyms already implied by the same ownership-attribution idiom, following the same "spell out the inflected forms by hand" convention `_PROHIBITION_VERB_FORMS` uses.
- Rationale: the verbatim #1022 shape — "the stale prose reference in `` `x.cs` ``**,** which batch 8 fixes." — puts a comma between the token and the ownership phrase, which `_clause_bounds` treats as a clause boundary (confirmed against the existing `test_check_context_completeness_dirty_contrast_citation_comma_clause_boundary` test's own semantics). A clause-scoped search would therefore fail to exempt the exact real-world sentence this exemption exists for. Line-wide search (matching `_is_prohibition_exempt`'s own granularity, not `_is_contrast_citation_exempt`'s clause-wide one) is the only granularity that reaches across that comma. This accepts the same false-negative-adjacent tradeoff `_is_prohibition_exempt`'s docstring already accepts for its own line-wide match: an unrelated "batch N fixes" mention elsewhere on an unusually long Requirements: line would exempt every backtick token on that line, not just the one the ownership phrase actually refers to. Given how rarely a single Requirements: line packs both an unrelated batch-ownership remark and an unrelated real dependency path, this is judged an acceptable tradeoff, consistent with how the existing line-wide mechanisms already accept it.
- Rejected: a plan-wide structural check cross-referencing the actual card/batch numbering (e.g. resolving "batch 8" to that batch's own `Creates:`/`Edits:` and verifying the path is really there) — over-engineered for what both issues ask for (a lexical exemption "mirroring the existing negation/citation templates"), and would need the same plan-wide card-index plumbing `creates_declaring_card_map` uses today, which is out of scope for a docstring-lexical fix.
- Rejected: keeping the clause-scoped design and instead rewriting the #1022 test fixture to drop its comma — rejected because it would make the test fixture diverge from the actual reported real-world sentence, defeating the point of a regression test for that exact issue.

### Literal-value enumeration exemption (covers #984's test-input case)

- Decision: add a new structural exemption, `_is_literal_enumeration_exempt`, operating at line granularity (matching `_CITATION_MARKERS`' own line-wide granularity, not clause-scoped). On a line with 3 or more backtick-quoted tokens total, if at least one of those tokens (other than the one under test) is neither path-shaped (`"/" in token or token.endswith(_PATH_CANDIDATE_EXTENSIONS)`) nor passes `_symbol_candidate_shape`, exempt every backtick token on that line.
- Rationale: the reported example mixes tokens that are unambiguously not files or symbols (`` `#x` ``, `` `.` ``, `` `a#b#c` ``) with one that happens to resolve on disk (`` `README.md` ``) — the presence of clearly-non-path/non-symbol siblings in the same enumeration is the actual signal that the whole list is literal test-input values, not a dependency list. A genuine multi-file dependency enumeration ("reads `` `a.py` ``, `` `b.py` ``, and `` `c.py` ``") contains only path-shaped tokens and so never trips this rule. The 3-token threshold is deliberately above 2, since two-token contrastive prose ("`x.py` and `y.py`") is common and unrelated to this idiom.
- Rejected: a marker-phrase list (e.g. "table-driven", "over at least", "as test input") mirroring `_CITATION_MARKERS`'s mechanism exactly — rejected because it is brittle to the specific wording of one issue's example and would not generalize to a differently-worded enumeration; the structural "mixed shape" signal generalizes to any table-driven-test-input list without depending on exact phrasing.
- Accepted tradeoff: a genuine dependency enumeration that also names one non-path/non-symbol literal on the same line (e.g. a CLI flag or sentinel string listed alongside real file paths, `` "reads `a.py`, `b.py`, and the `--dry-run` flag" ``) is wrongly swept in and its real path tokens suppressed — this exemption trades that specific false-negative risk for fixing the reported false positive, the same kind of tradeoff `_is_prohibition_exempt`'s and `_CITATION_MARKERS`' own docstrings already document and accept for their respective line-wide mechanisms.

### Illustrative-example / output-framing exemption (covers #985)

- Decision: add a new marker-verb pairing exemption, `_is_illustrative_output_exempt(lowered_line)`, mirroring `_is_prohibition_exempt`'s existing line-wide "negation word + verb form" pairing mechanism but for a new `_OUTPUT_VERB_FORMS` set (`emit(s)/emitting`, `render(s)/rendering`, `output(s)/outputting`, `print(s)/printing`, `display(s)/displaying`) paired with any backtick token on the line — i.e. the line-wide gate fires whenever an output/rendering verb form appears anywhere on the same `Requirements:` line as the token, independent of position, exactly like `_is_prohibition_exempt`'s existing gate.
- Rationale: `#985`'s exact sentence ("an answer ... emitting the bare `` `README.md` ``, never `` `./README.md` ``") describes a function's rendered *output value*, not a file it reads — "emitting"/"rendering"/"outputting" is the idiom that marks a backtick token as an illustrative output literal rather than a read dependency, the same semantic class `_CITATION_MARKERS`'s existing "signature inlined" / "no file read needed" entries already carve out for a different idiom. Reusing `_is_prohibition_exempt`'s line-wide pairing *mechanism* (rather than inventing a new one) keeps the new function's shape consistent with precedent and needs no new clause-boundary logic.
- Rejected: adding "the bare" as a `_CITATION_MARKERS` substring — too narrow (only catches this one phrasing) and semantically misleading as a "citation" marker when the real signal is the output-verb idiom; rejected in favor of the verb-pairing mechanism above, which generalizes to any output-describing verb.
- Rejected: treating this as a negation case via "never" — `_is_prohibition_exempt` already requires a verb from `_PROHIBITION_VERB_FORMS` paired with "never" on the line, and "emitting" is not (and should not become) a prohibition verb; conflating the two would blur what "prohibition" means for the existing exemption 1 and risks false-exempting an actual prohibition-adjacent dependency sentence that happens to also contain an output verb elsewhere on the line.

## Technical context

- All work is in `plugins/mill/scripts/_plan_validate.py`, inside and immediately around
  `_check_context_completeness` (the function whose docstring enumerates exemptions 1-10 today).
- Reuse existing shared helpers rather than duplicating logic:
  - `_clause_bounds(lowered_line, start, end)` — clause-scoping, already used by
    `_is_non_dependency_negation_exempt` and `_is_contrast_citation_exempt`.
  - `_symbol_candidate_shape(token)` — the existing bare/dotted-identifier shape gate, reused as-is
    (not modified) by the literal-enumeration exemption's "other tokens on the line" test.
  - `_PATH_CANDIDATE_EXTENSIONS` — the existing path-shape test, reused as-is.
- New exemptions are inserted into the exemption chain inside the per-token loop in
  `_check_context_completeness`, in the same style as the existing checks (`_is_prohibition_exempt`,
  `_is_non_dependency_negation_exempt`, the `_CITATION_MARKERS` substring check, then
  `_is_contrast_citation_exempt`) — each is a `continue` guard evaluated before the path/symbol
  resolution logic below it. All three new exemptions apply to both the path branch and the symbol
  branch, same as exemptions 1-3 and 8-9 today (the docstring's "Unless noted otherwise, an exemption
  applies to both branches" convention).
- Exact insertion order among the three new exemptions relative to each other and to exemptions 1-10
  does not matter functionally (each is an independent `continue` guard over disjoint trigger
  conditions), but should be appended after exemption 10 (quoted material) to keep the docstring's
  existing numbering stable rather than renumbering entries 1-10.
- No existing test fixture file needs restructuring — `test-plan-validate.py` already has one
  `test_check_context_completeness_clean_<exemption>` / `..._dirty_<exemption>_*` pair per existing
  exemption (e.g. `test_check_context_completeness_clean_contrast_citation_rather_than`,
  `test_check_context_completeness_dirty_contrast_citation_comma_clause_boundary`); the new tests
  extend that same file using the same in-memory-fixture, no-real-git/LLM convention (`mill:testing`,
  `python:python-testing`).

## Constraints

_No `CONSTRAINTS.md` at the hub root._

## Testing

TDD candidates — write the `dirty` (currently-still-flagged, pre-fix) case first for each, confirm it
reproduces the false positive against the *current* code, then add the exemption and confirm the
`clean` case passes:

- **Ownership exemption:**
  - `test_check_context_completeness_clean_ownership_batch_fixes` — `` "the stale prose reference in `x.cs`, which batch 8 fixes." `` (verbatim `#1022` shape).
  - `test_check_context_completeness_clean_ownership_card_corrects` — `` "for the same reason card 23 corrects one stale sentence in `golang.go`." `` (verbatim `#984` cross-reference shape, different verb).
  - `test_check_context_completeness_dirty_ownership_no_number_not_exempted` — "batch fixes `x.py`" (no card/batch *number*) must NOT be exempt, guarding against over-matching a bare "batch"/"card" mention.
  - `test_check_context_completeness_dirty_ownership_separate_line_not_exempted` — the ownership phrase on one `Requirements:` bullet line and the token on a *different* bullet line must NOT be exempt (the search is line-wide, not plan-wide or card-wide) — this is the real guard the per-line loop structure already gives for free; there is deliberately no "separate clause, same line" guard test, since the line-wide design accepts a same-line false-negative risk (documented in the Decision above) that a clause-scoped guard would contradict.
- **Literal-enumeration exemption:**
  - `test_check_context_completeness_clean_literal_enumeration_mixed_shapes` — the verbatim `#984` test-input list (`` `a/b#C`, `a/b`, `#x`, `a#b#c`, `README.md`, `.` ``).
  - `test_check_context_completeness_dirty_literal_enumeration_below_threshold_not_exempted` — only 2 backtick tokens on the line, one non-path-shaped — must NOT be exempt (threshold guard).
  - `test_check_context_completeness_dirty_literal_enumeration_all_path_shaped_not_exempted` — 3+ backtick tokens, all path-shaped (a genuine multi-file dependency list) — must NOT be exempt, guarding against suppressing real dependencies.
- **Illustrative-output exemption:**
  - `test_check_context_completeness_clean_illustrative_output_emitting` — the verbatim `#985` sentence.
  - `test_check_context_completeness_clean_illustrative_output_rendering` / `..._printing` — at least one more `_OUTPUT_VERB_FORMS` entry, mirroring how `..._prohibition_marker_new_verbs` exercises more than one verb form for exemption 1.
  - `test_check_context_completeness_dirty_illustrative_output_no_verb_not_exempted` — a line with a backtick token and no output verb — must NOT be exempt.
- Existing exemption tests (1-10) must continue to pass unmodified — no behavior change to any
  existing exemption.
- Run via `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-plan-validate.py` (or the repo's standard `run-all.py` harness), per this repo's `## Script invocation` / `verify:` conventions.

## Q&A log

- **Q:** Should the three new exemptions be three separate functions/mechanisms, or folded into the existing `_CITATION_MARKERS` substring list where possible? 1) Three separate, purpose-built mechanisms (one line-wide ownership regex, one line-wide structural "mixed-shape" rule, one line-wide verb-pairing rule), each reusing an existing shared helper where the existing precedent already has one (Recommended — each phrasing has a distinct enough shape that a generic substring marker would either be too narrow (only matches one exact wording) or too broad (risks suppressing real dependency prose); this mirrors how `ae07b506` itself used three different mechanisms — a marker list, a verb-pairing function, and a clause-scoped function — for its own set of fixes, rather than forcing every fix through one shared shape). 2) Fold all three into `_CITATION_MARKERS` as new substring entries. 3) Add a single new generic "structural exemption" umbrella function covering all three. **A:** [auto-pick] Option 1. **Why:** matches the existing codebase's own precedent for handling heterogeneous false-positive classes, and keeps each new mechanism auditable/testable in isolation, consistent with `mill:code-quality`.
- **Q:** For the literal-enumeration exemption, what backtick-count threshold on a line should trigger the "mixed-shape enumeration" exemption? 1) 3 or more backtick tokens on the line (Recommended — safely below the reported example's own 7-token list, so it still catches shorter real-world enumerations, and safely above ordinary 2-token contrastive prose ("`x.py` and `y.py`"), which is common in genuine dependency sentences and must never be swept in). 2) 2 or more. 3) A configurable threshold read from `mill-config.yaml`. **A:** [auto-pick] Option 1. **Why:** a 2-token threshold would falsely exempt the most common two-file contrastive sentence shape in ordinary Requirements: prose; a config knob adds a plan-format-affecting surface for a narrow lexical heuristic with no evidence any project needs to tune it, which would cut against `mill:code-quality`'s YAGNI guidance.
- **Q:** Should the ownership-exemption's verb set be limited to exactly "fixes"/"owns"/"corrects"/"rewrites" (the four verbs actually seen across the two issues), or extended to close synonyms ("addresses", "handles", "resolves", "covers", "edits", "updates")? 1) Extend to the listed close synonyms, spelled out by hand per the existing `_PROHIBITION_VERB_FORMS` convention (Recommended — the four observed verbs are clearly samples from one open-ended "ownership/handling" idiom class, not an exhaustive enumeration; a planner is likely to phrase the same handoff with any of these near-synonyms, and the existing `_PROHIBITION_VERB_FORMS` precedent already extends beyond the issues that motivated it, e.g. "cite"/"mention" were added for the citation-marker case, not the original prohibition-marker case). 2) Limit strictly to the four verbs actually quoted in the issues. **A:** [auto-pick] Option 1. **Why:** matches the existing codebase's own precedent of generalizing an observed verb set to its natural close-synonym class rather than over-fitting to the literal issue text, while still keeping the set hand-spelled (no suffix-generation) per the file's stated convention.
