# Conflict Resolution Brief

Your sole job is to resolve git conflict markers in the listed files, stage each resolved file, and report success. Do NOT commit. Do NOT run `git merge --continue` — the SKILL does that after receiving `{"status":"success"}`.

## Task intent

These excerpts describe what THIS branch is trying to accomplish. When the merge introduces a parent-side change that conflicts with this branch's intent, the resolution preserves THIS branch's intent. In particular: if a file appears under a batch's `Deletes:` list and the merge introduces a modified version of that file from the parent, the resolution is to delete the file (your branch's intent overrides). Stage the deletion with `git -C /home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps rm <file>`.

### From discussion.md

# Discussion: mill-plan review severity counting and validation schema gaps

```yaml
task: mill-plan review severity counting and validation schema gaps
slug: mill-plan-review-validation-gaps
status: discussing
parent: hanf/linux-port-more
```

## Problem

Two independent, unrelated bugs in the mill plugin's review/validation layer, both filed via `/mill-self-report --auto` from real mill-plan sessions across three different downstream repos (this task bundles four GitHub issues: #663, #685, #695, #664).

**Bug 1 — severity vocabulary blind spot (issues #663, #685, #695).** `_review_common.parse_blocking_count(raw_output, *, severity)` counts only `### [<severity>]` ATX headings matching the exact `severity` argument passed in. `_review_plan.py`'s finalize logic calls it once with `severity="BLOCKING"` and once with `severity="NIT"` to populate the finalize envelope's `blocking_count`/`nit_count`. Reviewer LLMs have independently, on three separate occasions, emitted findings labeled `[MAJOR]`, `[MINOR]`, `[MEDIUM]`, or `[HIGH]` instead of `[BLOCKING]`/`[NIT]` — none of these map to either counter, so they are silently dropped from both. mill-plan's step 4c treats `blocking_count == 0` as "this round produced only NITs, safe to auto-approve, skip further review," so a round containing a genuine compile-breaking MAJOR/MEDIUM finding gets waved through as if it were cosmetic-only. In one observed case (#663) the dropped finding was a real compile break (a plan card enumerated stale test fixtures referencing a type the plan deletes) — it was only caught because the orchestrator happened to read the review file by hand rather than trusting the envelope.

**Why now:** three independent incidents across three different source repos over roughly nine days (2026-07-16 to 2026-07-25) is a pattern, not a one-off — the review-output schema (`review-output.schema.md`) already documents BLOCKING/NIT as the only valid severities for plan/code reviews, but nothing in the counting code or the reviewer prompt templates actively prevents or safely handles a reviewer emitting anything else.

**Bug 2 — no way to express a commit-less verification-only plan card (issue #664).** `_plan_validate._REQUIRED_CARD_FIELDS` unconditionally requires every card to carry a `Commit:` field, with no `none` sentinel accepted — unlike `Edits:`/`Creates:`/`Deletes:`/`Moves:`, which already accept the literal `none` when a card has nothing for that field. A card whose sole job is verification (e.g. "grep for X and confirm cards 25-26 actually finished," no edits of its own) is therefore forced to either fabricate an empty commit or get folded into a neighboring card, losing it as a separately-trackable, separately-reviewable step.

## Scope

**In:**
- `_review_common.py`: a new shared helper that detects `### [XXX]` findings headings whose bracketed label is neither the review type's configured blocking-equivalent nor its nit-equivalent severity, and folds those into `blocking_count` ("fail-loud" — unrecognized severity blocks convergence rather than vanishing). Applied uniformly across all three review types (plan, code, discussion) since they share the same counting primitive.
- `_review_plan.py`: apply the fail-loud helper at every call site that currently derives `blocking_count` from `parse_blocking_count(severity="BLOCKING")` — both the Agent-mode `finalize()`/`finalize_scope()` path and the subprocess/psmux `run()` path's five inline call sites (per-batch review, disk-resume, holistic NEED_CONTEXT double-retry, holistic NEED_CONTEXT no-resolve, holistic normal).
- `_review_code.py` / wherever code review's finalize path derives `blocking_count`: same fail-loud treatment (shares `finalize_scope`).
- `_review_discussion.py`: same fail-loud treatment for GAP/NOTE, via the same shared `finalize_scope` path.
- Reviewer prompt templates (`review-plan-holistic.md`, `review-plan-batch.md`, `review-code-holistic.md`, `review-code-batch.md`, `review-discussion.md`): add an explicit instruction that the finding-severity vocabulary is closed — only the two documented labels for that review type are valid, never invent another word, and an ambiguous finding must default to the blocking-equivalent label, not the nit-equivalent one.
- `review-output.schema.md`: document the fail-loud behavior — any non-conforming severity finding, whether expressed as a markdown heading (`### [XXX]`) or as a `severity:` entry inside a fenced yaml `findings:` block, is treated as blocking, not dropped — so the schema and the code agree on both formats, not just the heading case.
- `_plan_validate.py`: accept the literal `Commit: none`, mirroring the existing `none` convention for Edits/Creates/Deletes/Moves. Add a validation error when `Commit: none` co-occurs with any non-`none` Edits/Creates/Deletes/Moves on the same card (verification-only cards must be genuinely diff-free).
- `plan-batch.md` template: document the `Commit: none` convention alongside the existing per-field `none` documentation.
- `implementer-brief.md`: instruct the implementer to skip the commit step entirely for a `Commit: none` card (no git-commit skill invocation, nothing to stage). Update the "Resume-after-incomplete" card-matching logic (currently matches `git log` commit subjects against each card's `Commit:` message) and the "Card-count self-check" logic so a `Commit: none` card — which by definition never produces a commit — is still correctly recognized as satisfied/complete rather than perpetually counted as remaining.
- Unit tests: `test-review-common.py` (fail-loud helper: unrecognized severities count as blocking; existing BLOCKING/NIT/GAP/NOTE case-sensitive matching behavior unchanged) and `test-plan-validate.py` (`Commit: none` accepted alone; rejected when combined with non-none Edits/Creates/Deletes/Moves; existing required-field behavior for every other card shape unchanged).

**Out:**
- The pre-existing, separate gap where the subprocess/psmux `run()` path in `_review_plan.py` never populates `nit_count` at all (`ReviewResult.nit_count` silently defaults to 0 for that whole dispatch mode). Discovered during exploration; not described by any of the four linked issues, and fixing it would require adding nit_count computation/plumbing to 5 call sites plus aggregation — a materially different, larger change. To be filed as a separate follow-up issue via `/mill-self-report`, not fixed here.
- `_nit_gate.py`'s `parse_blocking_count(text, severity="NIT")` call — unaffected by the fail-loud change (it only ever needs the literal NIT count for its own purpose, unrelated to blocking-convergence); left untouched.
- `parse_blocking_count()` itself is not modified — its existing single-severity heading/YAML-fallback counting behavior (and the ~15 existing unit tests pinning that behavior) stays exactly as-is. The fail-loud logic is additive, in a new helper, layered on top.
- No change to `mill-plan`/`mill-go` SKILL.md step 4c's convergence condition text itself (`blocking_count == 0`) — it doesn't need to change because the fix makes `blocking_count` itself now correctly non-zero whenever a non-NIT-equivalent finding exists, rather than requiring step 4c to learn about a new counter.
- No change to mill-go's per-card commit execution for cards with real edits — only the new `Commit: none` verification-only path is added; the existing one-commit-per-card / combined-commit norm for cards that do have edits is untouched.
- No retroactive re-validation of already-written plans elsewhere in the repo; this only changes the validator/schema/templates going forward.

## Decisions

### fail-loud-not-vocabulary-pin-only

- Decision: fix the severity-counting blind spot at the code level (any unrecognized `### [XXX]` severity heading is folded into `blocking_count`), not by relying solely on tightening the reviewer prompt templates.
- Rationale: three independent LLM reviewer sessions have already produced non-standard severity words despite the templates' strict output-format examples only showing `[BLOCKING]`/`[NIT]`. A prompt-only fix depends on continued model compliance — the exact failure mode already observed three times. A code-level backstop guarantees no severity can ever be silently dropped from the convergence decision again, regardless of what a reviewer emits.
- Rejected: vocabulary-pinning only (issue #663's smaller option (a)) — cheaper but doesn't close the actual failure mode, only reduces its frequency. Hardcoded severity-tier mapping (MAJOR/MEDIUM/HIGH → blocking, MINOR → nit) — rejected because it requires guessing tier semantics for words that were never part of the agreed vocabulary in the first place; fail-loud sidesteps the guessing entirely.

### uniform-across-review-types

- Decision: apply the fail-loud fix to all three review types (plan, code, discussion) since they share `_review_common.finalize_scope()` / the underlying counting primitive, even though only plan review has a filed bug.
- Rationale: the identical code path drives blocking_count/nit_count for code review (BLOCKING/NIT) and gap_count/note_count for discussion review (GAP/NOTE, via the same function with different severity args). Fixing only the plan-review call sites while leaving the shared function's other callers exposed would be an inconsistent half-fix — a future MAJOR-labeled finding in a code review would reproduce the exact same silent-drop bug.
- Rejected: scoping strictly to the three filed plan-review issues — technically satisfies the letter of the bug reports but leaves an identical, already-demonstrated failure mode live in two adjacent code paths for no cost savings (the fix is at the shared layer regardless).

### commit-none-cross-field-constraint

- Decision: `_plan_validate` accepts `Commit: none`, but only when every other content field on that card (`Edits`, `Creates`, `Deletes`, `Moves`) is also `none` — a card cannot have a real diff and skip its commit.
- Rationale: issue #664's actual reported use case is a pure verification gate (a grep, no edits). Allowing `Commit: none` alongside real edits would let a card silently leave changes uncommitted, violating the plan-authoring norm ("one commit per card is the norm... do not create empty commits") and producing exactly the kind of dirty-tree state the implementer-brief's pre-report self-check already guards against elsewhere.
- Rejected: no cross-field constraint (trust plan authors) — simpler but opens an obvious misuse path that validation should catch at plan-review time rather than at implementation time when it's more expensive to fix.

### full-fix-not-validator-only

- Decision: alongside the validator change, also update `implementer-brief.md`'s commit-skip instruction, "Resume-after-incomplete" matching logic, and "Card-count self-check" logic.
- Rationale: both of those existing mechanisms work by matching `git log` commit subjects against each card's `Commit:` message. A `Commit: none` card produces no commit and therefore no log entry to match — leaving those mechanisms unchanged would make every `Commit: none` card look perpetually incomplete/remaining on any resume-after-incomplete dispatch, reintroducing a new variant of "the tooling can't see this card's true state" that this task exists to eliminate.
- Rejected: validator-only fix — smaller diff, but ships a schema change that's unusable in practice because the very next resume dispatch after a partial batch would misclassify every already-satisfied `Commit: none` card as still outstanding.

## Technical context

**Severity-counting call graph:**
- `_review_common.py:1564` `parse_blocking_count(raw_output, *, severity)` — single-severity heading counter (regex `^###\s+\[<severity>\]\s+`, MULTILINE, case-sensitive) with a YAML-fenced-block fallback when heading_count is 0. Stays unchanged; ~15 existing unit tests in `test-review-common.py` (lines ~1920-2150, ~3078-3186) pin its exact behavior — do not modify its signature or matching semantics.
- `_review_common.py:1744` `finalize_scope(reviews_dir, review_type, round_n, raw_text, *, scope=None, actual_model=None)` — calls `parse_blocking_count` twice (blocking_severity, nit_severity — `BLOCKING`/`NIT` for plan/code, `GAP`/`NOTE` for discussion) at lines 1788-1789. This is the Agent-mode dispatch finalize path, used by `_review_plan.py:finalize()` (line 580), and presumably analogous finalize functions in `_review_code.py` and `_review_discussion.py` — confirm exact call sites when writing the plan.
- `_review_plan.py`'s `run()` function (the subprocess/psmux "full"/synchronous dispatch path — NOT going through `finalize_scope()`) has its own duplicated inline `blocking_count = parse_blocking_count(raw, severity="BLOCKING")` at 5 call sites: line 284 (per-batch review), line 734 (disk-resume reload), line 947 (holistic NEED_CONTEXT after successful re-retry), line 965 (holistic NEED_CONTEXT, no re-attachable paths), line 982 (holistic normal path). All 5 need the same fail-loud treatment for `blocking_count` specifically (this path already doesn't track `nit_count` at all — see Scope/Out above, that gap is explicitly not being fixed here, only `blocking_count`'s severity-vocabulary blindness).
- `_nit_gate.py:98` calls `parse_blocking_count(text, severity="NIT")` for an unrelated purpose (detecting unfixed nits on already-approved scopes) — do not touch.
- New helper should live in `_review_common.py` alongside `parse_blocking_count` (same module, same public-API surface consumers already import from). Suggested shape: a function that takes the raw text plus the pair of severities already in play (e.g. `blocking_severity`, `nit_severity`) and returns the count of `### [XXX]` headings whose bracket content is neither, using the same case-sensitive, line-start-anchored matching as `parse_blocking_count` so behavior stays consistent. mill-plan writes the exact function name/signature during plan-writing.
- **The helper MUST also cover the YAML-fallback path, not just headings — and must not gate that coverage behind an ambiguous headings-vs-YAML mode switch.** `parse_blocking_count` has two independent counting paths: the heading regex, and — when heading_count is 0 for that specific severity call — a fallback that scans fenced ` ```yaml ` blocks for a `findings:` list and counts entries whose `severity` field matches (case-**insensitive**, unlike the case-sensitive heading path), added for incident #552 (see `test-review-common.py:1969-2016`). Because `parse_blocking_count` is called once per severity, its headings-vs-YAML choice is made independently per call — a single review could legitimately have real `### [NIT]` headings (heading path) while also carrying an unrecognized severity expressed only in a YAML `findings:` entry with zero corresponding `### [BLOCKING]` headings. A fail-loud helper that picks ONE global mode for the whole document (e.g. "fall back to YAML only when both known severities' heading counts are 0") would miss exactly that mixed-format case — reproducing Bug 1 through a different edge case. To avoid this ambiguity entirely, the new unrecognized-severity scan does **not** try to infer which format is "active" from the known severities' counts at all: it unconditionally scans **both** mechanisms every time — every `### [XXX]` heading (case-sensitive) AND every entry in any fenced yaml `findings:` block (case-insensitive) — and fail-loud-counts (into the blocking-equivalent bucket) any match, from either mechanism, whose severity label matches neither known severity. Running both scans unconditionally, rather than conditioning either on the other's result, is strictly safer than any AND/OR gating and sidesteps the ambiguity the discussion-review round-2 GAP identified. (This does NOT change `parse_blocking_count`'s own existing per-severity heading-vs-YAML mode selection for the two known severities — only the new unrecognized-severity scan runs both mechanisms unconditionally.) **Accepted risk, not fixed:** unlike `parse_blocking_count`'s own known-severity counting (which already guards against double-counting via "heading_count > 0 skips the yaml scan entirely," tested at `test-review-common.py:1994-1998`), the new unrecognized-severity scan does not dedup — if a reviewer emits both a heading and a mirroring yaml entry for the same unrecognized-severity finding, it is counted twice. This inflates the operator-facing "N BLOCKING findings remain" count but does not affect convergence correctness (`blocking_count == 0` still gates correctly on any nonzero count). Explicitly accepted as low-probability and cosmetic-only rather than adding dedup complexity for an edge case that doesn't affect correctness.

**Validation call graph:**
- `_plan_validate.py:102` `_REQUIRED_CARD_FIELDS = ["Context", "Edits", "Creates", "Deletes", "Moves", "Requirements", "Commit"]` — field-presence list used by `_check_card_missing_field` (line 695) via a regex per field (`^-\s*\*\*<field>:\*\*`, MULTILINE) that only checks the field label exists, not its value. The `none` sentinel for Edits/Creates/Deletes/Moves is handled entirely by *other*, separate checks further down the file (e.g. `deletes_only` loop at line 670-686 explicitly skips `t.lower() == "none"`) — `Commit:` currently has no equivalent "is this none, and if so what does that imply" check anywhere in the file. The new cross-field constraint (decision `commit-none-cross-field-constraint` above) will need its own new check function, following the existing pattern of small `_check_*` functions each returning a list of error dicts with `check`/`batch`/`card`/`path`/`message` keys.
- `implementer-brief.md` line 57: implementer commits per card by invoking the `git-commit` skill with the card's `Commit:` message — needs a conditional: if `Commit:` is `none`, skip this step entirely (no skill invocation, nothing staged).
- `implementer-brief.md` line 52 ("Resume-after-incomplete"): matches `git -C <PROJECT_ROOT> log <START_SHA>..HEAD --oneline` subjects against each card's `Commit:` message to determine which cards are already done. A `Commit: none` card needs a different completion signal — since the decision above enforces that such a card has zero Edits/Creates/Deletes/Moves, its "completion" is really just "was its Requirements: verification step performed," which for a re-dispatched implementer effectively means: treat a `Commit: none` card as always eligible to (re-)verify inline without needing a prior commit to detect, i.e. exclude it from the log-matching scan entirely rather than trying to detect its "prior completion" from git history. mill-plan should write the exact resume semantics.
- `implementer-brief.md` line 100 ("Card-count self-check"): same log-matching mechanism, same exclusion needed — a `Commit: none` card should not inflate the "expected card count that must appear in git log" denominator.
- `implementer-brief.md` line 111 ("Report section"): currently states "`commit_sha` MUST be a real content commit distinct from the batch start commit. An implementer that made edits but did not run the per-card `git-commit` skill must report `status: stuck` instead." This conflicts with an all-`Commit: none` batch (every declared/remaining card is `Commit: none`), which legitimately produces zero content commits — the implementer has no honest value to put in `commit_sha`. Needs an explicit carve-out: when every card being reported this turn is `Commit: none`, permit `commit_sha` to equal the batch-start SHA (or the last real content commit if this is a partial-Commit:-none tail of an otherwise-normal batch) instead of demoting to `stuck`, mirroring the same code-derived, all-`Commit:-none` condition already planned for the backend no-content-commit gate above — the two carve-outs must use the same underlying signal so the implementer's self-report and the backend gate agree on when an all-`Commit: none` turn is legitimately commit-less.
- **Backend no-content-commit gate must gain a `Commit: none`-aware exemption — and the exemption signal must be code-derived, not implementer self-reported.** `_implementer_common.py` has a mechanical, code-level gate — independent of anything the implementer self-reports — that demotes a reported `status: success` to `stuck_type: logic` whenever zero content commits exist since `start_sha` (the "HEAD == start_sha" check at ~line 1431-1448, plus the batch-start-commit-only variant at ~line 1452-1464; both invoked via `_reclassify_verify_failure` at ~line 149-160 too). Its docstring is explicit: this is "unaffected by cards_done: zero commits means zero work regardless of any self-report" (`_implementer_common.py:121-122`) — the gate is deliberately immune to whatever the implementer claims. The only existing exemption is `nits_only`, and critically that flag is **orchestrator-supplied** (passed by the Builder via `millpy-fix.py --nits-only`, confirmed at `millpy-fix.py:170,345`), never something the fixer/implementer self-reports. A batch composed entirely of `Commit: none` verification cards — or one where, on a late `--resume-incomplete` re-dispatch, every *remaining* card happens to be `Commit: none` — would legitimately produce zero content commits despite `cards_done` correctly reporting every card addressed, and would be mechanically misclassified as stuck by this gate. The carve-out must genuinely mirror `nits_only`'s orchestrator-supplied nature: the signal has to be **code-derived** — a plan-level scan (performed by the CLI/orchestrator, not trusted from implementer output) of whether every card the batch declares (or every card still remaining, on a resume) is a `Commit: none` card — never an implementer-self-reported flag, which would let a session falsely claim "all my remaining cards were Commit: none" to bypass the zero-commit check even when real work was silently skipped. mill-plan decides the precise threading mechanism when writing the plan, but the signal source is fixed: code-derived only.

## Constraints

No `CONSTRAINTS.md` present at the hub root — none discovered beyond what's captured under Scope/Decisions above.

Per project `CLAUDE.md`: `print()`/`_log()` output must stay ASCII-only (relevant if the new fail-loud helper or validation check emits any diagnostic messages). Ad-hoc Python lint via `uvx ruff check .` if a project-specific `python-build` override isn't already in place for this repo.

## Testing

- **`test-review-common.py`** (TDD candidate: the new fail-loud helper). Cases: zero unrecognized headings → 0; one `[MAJOR]` heading with blocking_severity=BLOCKING, nit_severity=NIT → counted; one `[MEDIUM]`/`[HIGH]`/`[MINOR]` heading → counted, same as MAJOR (no special-casing by word); a literal `[BLOCKING]` heading is not double-counted by the new helper (it's already counted by the existing `parse_blocking_count(severity="BLOCKING")` call — the new helper's count is additive only for headings matching neither known severity); a literal `[NIT]` heading is never counted by the new helper; mixed-case `[Major]`/`[major]` is NOT counted (case-sensitive, consistent with existing `parse_blocking_count` behavior — confirmed by Decision/Technical-context above); a GAP/NOTE-typed review with a stray `[MAJOR]` heading also gets it counted toward the blocking-equivalent bucket (GAP), proving the discussion-review path shares the fix; empty input → 0, no crash.
- **`finalize_scope()`** integration-style unit test: raw text with one BLOCKING + one MAJOR + one NIT → `blocking_count == 2`, `nit_count == 1`.
- **`_review_plan.py`**'s 5 inline `run()` call sites: at minimum one regression test in the existing `test-review-plan-flow.py` (`plugins/mill/unit_tests/`) confirming a MAJOR-only round (no literal BLOCKING) still yields `blocking_count > 0` in the synchronous dispatch path specifically, since that's the path that diverges most from `finalize_scope()`. Only this one site gets a discrete test — the other 4 (lines 734, 947, 965, 982) are expected to reach the same fail-loud outcome via an identical helper call copy-pasted at each site, so they're covered by code-identity with the tested site rather than by their own discrete tests. This is acceptable ONLY if the applied fix is truly identical at every site; if any site's surrounding logic diverges when mill-plan writes the actual implementation — the double-retry NEED_CONTEXT paths at lines 947/965 are the likeliest candidates, since they sit inside nested retry/exception branches unlike the more linear sites at 284/734/982 — that site needs its own discrete regression test rather than relying on code-identity.
- **YAML-fallback fail-loud path**: a test case in `test-review-common.py` with a fenced ` ```yaml ` `findings:` block (no markdown headings at all) containing one entry with `severity: MAJOR` and no matching `### [MAJOR]` heading anywhere — the new helper must still count it toward the blocking-equivalent bucket. Include a case-insensitivity check (`severity: major` lowercase) mirroring the existing YAML-path case-insensitivity test at `test-review-common.py:2014-2016`, contrasted with the headings-path case-sensitivity test covered above.
- **`test-plan-validate.py`** (TDD candidate: the new cross-field check). Cases: card with `Commit: none` + all other fields `none` → no error; card with `Commit: none` + one non-none `Edits:` → new validation error raised; card with a real `Commit:` message + real edits → unchanged, no error (regression); card missing `Commit:` entirely → existing `card-missing-field` error, unchanged (regression, confirms the fix is additive not replacing the existing required-field check).
- **`implementer-brief.md` changes** are prompt/instruction text for an LLM implementer, not directly unit-testable; validate by reading the rendered brief output for a plan containing a `Commit: none` card during manual/integration review of the finished plan, not via `run-all.py`.
- **No-content-commit gate exemption** (`_implementer_common.py`): unit test(s) covering — a report where every `cards_done` entry corresponds to a `Commit: none` card and HEAD == start_sha → gate does NOT demote to `stuck_type: logic` (the new exemption fires); a report with a mix of real and `Commit: none` cards where HEAD == start_sha (no commit was actually made despite a non-`Commit: none` card being claimed) → gate still demotes as today (exemption must not overfire and mask a genuinely missing commit); existing `nits_only` exemption behavior unchanged (regression).

## Q&A log

- **Q:** What's the fix mechanism for MAJOR/MINOR/MEDIUM/HIGH being invisible to blocking_count/nit_count? **A:** [auto-pick] Fail-loud counting (shared helper folding unrecognized severities into blocking_count) + template vocabulary pinning. **Why:** three independent LLM-reviewer sessions already drifted from the documented BLOCKING/NIT vocabulary despite prompt examples; a code-level backstop is the only fix that doesn't depend on continued model compliance.
- **Q:** Should discussion review (GAP/NOTE) get the same fail-loud treatment even though no bug was filed for it? **A:** [auto-pick] Yes, uniform fix across all three review types. **Why:** all three share the same `finalize_scope()` code path; excluding discussion review would deliberately leave an identical, already-demonstrated failure mode live for no savings.
- **Q:** The subprocess/psmux `run()` path never populates `nit_count` at all — fix now or file separately? **A:** [auto-pick] File separately via `/mill-self-report`. **Why:** none of the four linked issues describe this; it's a differently-shaped, larger change (nit_count plumbing across 5 call sites + aggregation) than what was asked.
- **Q:** Case-sensitivity of the new "unrecognized severity" detection? **A:** [auto-pick] Match existing case-sensitive convention (only `[MAJOR]`-style, not `[Major]`/`[major]`). **Why:** consistency with `parse_blocking_count`'s existing, tested, case-sensitive matching — avoids two conflicting case rules in the same subsystem.
- **Q:** Scope of the `Commit: none` fix — validator-only or full (validator + brief resume/count logic)? **A:** [auto-pick] Full fix. **Why:** validator-only ships a schema change that's unusable in practice — the very next resume-after-incomplete dispatch would misclassify a satisfied `Commit: none` card as still outstanding, since resume detection works by matching git log against Commit: messages.
- **Q:** Should `Commit: none` require all other card fields (Edits/Creates/Deletes/Moves) to also be `none`? **A:** [auto-pick] Yes, enforce the cross-field constraint as a new validation error. **Why:** matches the issue's actual reported use case (pure verification gate) and prevents a card from silently leaving real edits uncommitted.
- **Q:** Testing approach? **A:** [auto-pick] Add targeted unit tests to `test-review-common.py` and `test-plan-validate.py` covering the new fail-loud helper and the new cross-field check, plus regression cases for unchanged existing behavior. **Why:** matches this repo's established testing pattern (`plugins/mill/unit_tests/`) and both bugs are exactly the class of silent-drop / validator-gap that cheap targeted unit tests catch and regression-guard.
- **Q:** [discussion-review r1 GAP] Does the new fail-loud helper need to cover `parse_blocking_count`'s YAML-fenced `findings:` fallback path (used when heading_count is 0, added for incident #552), not just markdown headings? **A:** Yes — mirror both of `parse_blocking_count`'s paths (headings case-sensitive, YAML fallback case-insensitive), since #552 establishes YAML-only reviewer output is a real production shape and an unrecognized severity there would otherwise still be silently dropped through the exact code path this task exists to close.
- **Q:** [discussion-review r1 GAP] Does the `Commit: none` fix need to account for `_implementer_common.py`'s backend no-content-commit gate (which mechanically demotes a self-reported `success` to `stuck_type: logic` whenever zero content commits exist since `start_sha`, independent of `cards_done`)? **A:** Yes — a batch composed entirely (or, on late resume, entirely of remaining) `Commit: none` cards would legitimately make zero commits and get mechanically misclassified as stuck. Needs a carve-out mirroring the existing `nits_only` exemption; exact signal/threading mechanism left to mill-plan.
- **Q:** [discussion-review r2 GAP] Should the fail-loud helper's YAML-fallback coverage be gated by an AND/OR condition on the two known severities' heading counts, or run unconditionally? **A:** Run unconditionally — the unrecognized-severity scan checks both headings and any YAML `findings:` entries every time, independent of which path the known severities used, since `parse_blocking_count` picks headings-vs-YAML per severity independently and any single global AND/OR gate could miss a mixed-format document (real headings for one known severity, an unrecognized severity expressed only in YAML).
- **Q:** [discussion-review r3 GAP] Should the `Commit: none` no-content-commit-gate carve-out signal be implementer-self-reported or code-derived? **A:** Code-derived only (a plan-level scan of which cards are `Commit: none`, performed by the orchestrator/CLI) — never implementer self-reported. The gate's own docstring states it is deliberately immune to self-report ("unaffected by cards_done... regardless of any self-report"), and the existing `nits_only` precedent it's meant to mirror is itself orchestrator-supplied (a CLI flag), not a claim the implementer makes about its own work. A self-reported carve-out signal would let a session falsely claim "no commit needed" to bypass the zero-work check.
- **Q:** [discussion-review r4 GAP] Does implementer-brief.md's Report-section requirement ("`commit_sha` MUST be a real content commit... an implementer that made edits but did not commit must report stuck") also need a carve-out for all-`Commit: none` batches? **A:** Yes — added an explicit exemption permitting `commit_sha` to equal the batch-start SHA (or last real commit) when every card reported this turn is `Commit: none`, using the same code-derived signal as the backend gate's carve-out so the implementer's self-report and the mechanical gate agree.


### From _mill/plan/00-overview.md


```yaml
task: mill-plan review severity counting and validation schema gaps
slug: mill-plan-review-validation-gaps
approved: true
started: 20260725-132313
parent: hanf/linux-port-more
root: ""
verify: null
```

### From _mill/plan/01-severity-failloud-core.md


```yaml
task: mill-plan review severity counting and validation schema gaps
batch: severity-failloud-core
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-review-common.py
depends-on: []
```



- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/02-severity-failloud-legacy-callsites.md


```yaml
task: mill-plan review severity counting and validation schema gaps
batch: severity-failloud-legacy-callsites
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-common.py
depends-on: [1]
```



- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/03-severity-vocabulary-docs.md


```yaml
task: mill-plan review severity counting and validation schema gaps
batch: severity-vocabulary-docs
number: 3
cards: 2
verify: null
depends-on: []
```



- **Edits:**
  - `plugins/mill/templates/review-plan-batch.md`
  - `plugins/mill/templates/review-plan-holistic.md`
  - `plugins/mill/templates/review-code-batch.md`
  - `plugins/mill/templates/review-code-holistic.md`
  - `plugins/mill/templates/review-discussion.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/templates/review-output.schema.md`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/04-commit-none-validator.md


```yaml
task: mill-plan review severity counting and validation schema gaps
batch: commit-none-validator
number: 4
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-plan-dag.py test-plan-validate.py
depends-on: []
```



- **Edits:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/templates/plan-batch.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-dag.py`
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/05-commit-none-implementer-brief.md


```yaml
task: mill-plan review severity counting and validation schema gaps
batch: commit-none-implementer-brief
number: 5
cards: 1
verify: null
depends-on: []
```



- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/06-commit-none-backend-gate.md


```yaml
task: mill-plan review severity counting and validation schema gaps
batch: commit-none-backend-gate
number: 6
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-implementer-common.py
depends-on: [4]
```



- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none

## Conflicting files

- `plugins/mill/unit_tests/test-plan-dag.py`

## Instructions

For each file listed above:

1. Read the file and locate every conflict block (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Understand both sides of the conflict — what each branch intended.
3. Write a resolution that preserves the intent of both sides. When both sides modify **different, non-overlapping parts** of the same conflict region — for example, different columns of one table row, different keys of one object, or disjoint lines of a prose block — **combine both edits** into a single resolved structure. Do NOT pick one side wholesale just because the region overlaps syntactically; picking one side wholesale is correct only when the two changes are genuinely mutually exclusive (e.g. the same key is renamed to two different values). Worked example: if `ours` changes column A and `theirs` changes column B of the same table row, the resolution keeps both column changes in a single row — it does not discard either.
4. Run `git -C /home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps add <file>` to stage the resolved file.
5. For modify/delete (DU) conflicts: if Task intent above lists this file under a batch's `Deletes:`, run `git -C /home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps rm <file>` instead of editing; that stages the intentional deletion.
6. For UD conflicts — files this branch **modified** that the parent branch **deleted**: do not silently keep the modification. Instead:
   a. Run `git log --diff-filter=D --oneline MERGE_HEAD -- <file>` to find the deletion commit on the parent.
   b. Run `git show <deletion-commit>` to inspect context.
   c. If the deletion commit message mentions a replacement file (e.g. "replaced by", "moved to", "consolidated into"), or the commit also adds a file in the same directory with overlapping content: stage the deletion — `git -C /home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps rm <file>`.
   d. If detection is inconclusive: report `{"status":"stuck","stuck_type":"logic","reason":"modify/delete conflict on <file>: cannot determine if parent deletion is a replacement -- operator must decide"}` and halt. Do NOT silently keep the modification.

Never use `git checkout --ours` or `git checkout --theirs` — they silently discard one side of the conflict.

## Report

Your last output line MUST be a bare JSON object (no code fence, no backticks):

On success (nothing discarded):

{"status":"success"}

On success with discarded content — if you had to drop content from one side (e.g. two sides made mutually exclusive changes and only one could survive), list each dropped item:

{"status":"success","discarded":["<short description of what was dropped from which side>"]}

An empty or absent `discarded` field means nothing was lost. If anything was discarded, you MUST list it; an empty list when content was actually dropped is a protocol violation. The `mill-merge-in` frontend reads this field and surfaces any losses to the operator before continuing, rather than silently running `git merge --continue`.

If you cannot resolve one or more conflicts:

{"status":"stuck","stuck_type":"logic","reason":"<one-line description of what you could not resolve>"}

Anything other than this JSON object on the last line is a protocol violation; the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost. Do not wrap the JSON in a code fence; do not add commentary after it.

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob. Use `git -C /home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps` for any git commands; do not `cd`. Worktree cwd is `/home/knatte/Code/millhouse/wts/mill-plan-review-validation-gaps`.
