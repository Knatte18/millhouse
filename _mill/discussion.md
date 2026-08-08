# Discussion: Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch

```yaml
task: Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch
slug: review-gap-classification-by-kind
status: discussing
parent: main
```

## Problem

Mill's review system has two independent defects that this task fixes together.

**Defect 1 — findings are flat.**
A `[GAP]` in a discussion review, or a `[BLOCKING]` in a plan or code review, carries exactly one bit of information: does it block or not.
Every blocking finding counts the same toward `blocking_count`, gates the round loop identically, and — in mill-start's Phase: Discussion Review step 5 — is surfaced to the operator as a numbered question.
That conflates findings with very different economics.

The evidence is a real 6-round discussion-review loop on the loomyard task `pattern-into-lyx-consolidation` (GitHub issue #788).
Blocking findings went 6 → 5 → 4 → 3 → 3 → 3 and never converged on count.
Sorted by kind, the reason is obvious:

| Round | design/correctness | scope (missed call sites) | undecided fixture/step |
|---|---|---|---|
| r1 | 5 | 0 | 1 |
| r2 | 2 | 3 | 0 |
| r3 | 2 | 2 | 0 |
| r4 | 2 | 1 | 0 |
| r5 | 2 | 1 | 0 |
| r6 | 0 | 1 | 2 |

Design findings converged to zero by r6.
Scope findings recurred in four of six rounds and never converged, because the orchestrator kept patching the symptom (adding the newly-named files) instead of the cause (hand-enumerating ~40 call sites from greps is not a reliable method).
Most `scope` findings at the discussion stage are work that downstream stages do better and for free — the compiler enumerates every missed call site exhaustively and instantly, plan review catches batch sizing, code review catches the remainder.
A discussion reviewer spending its budget listing test files the build will list anyway is correct but economically wrong at that stage.

The nuance: an inventory is not worthless pre-plan, because the plan sizes batches from it.
The right reviewer behaviour is to file it once, as a design finding about method — "the discussion is hand-enumerating call sites;
delegate it to a mechanical sweep and say so" — and never again as N individual missing files.

**Defect 2 — the severity vocabulary is split three ways for no reason.**
Discussion review speaks `GAP` / `NOTE` with verdicts `APPROVE` / `GAPS_FOUND`.
Plan and code review speak `BLOCKING` / `NIT` with verdicts `APPROVE` / `REQUEST_CHANGES`.
The split is historical (a v1 convention), not semantic, and it costs real complexity: `finalize_scope()` forks on `review_type` to pick a severity pair, `parse_verdict()` carries a four-value closed set where three would do, `count_unrecognized_severity_findings()` takes two severity arguments that only ever hold two distinct value pairs,
and every SKILL, template, and test that touches review output has to know which dialect it is reading.
Adding a class dimension on top of a split vocabulary would double that cost.

**Why now:** the class dimension has to touch every severity-parsing regex and the whole envelope contract anyway.
Unifying the vocabulary in the same pass costs a larger diff once, instead of two migrations of the same call sites.

## Scope

**In:**

- Unify the severity vocabulary across all three review types to `[BLOCKING]` / `[NIT]` with verdicts `APPROVE` / `REQUEST_CHANGES`.
  Retire `GAP`, `NOTE`, and `GAPS_FOUND` from every template, SKILL, script, and test.
- Add an orthogonal **class** dimension to the finding heading: `### [BLOCKING:design] <title>`, with classes `design`, `scope`, `decision`, `consistency`.
- Add a per-role `blocking_classes` config key that acts as a backend **ceiling**: `finalize_scope()` demotes `BLOCKING` → `NIT` for any finding whose class is not in the stage's set.
- Rewrite the demoted heading in the review file that gets written to disk, so file and envelope always agree.
- Replace the flat `blocking_count` / `nit_count` envelope scalars with a structured `findings:` list, retaining the scalars as derived values.
- Add a `## Out of scope for this stage` section to all five review-prompt templates.
- Add the anti-ladder guarantee to `mill-receiving-review`, `review-output.schema.md`, and every review template.
- Update mill-start, mill-plan, and mill-go SKILLs for the new vocabulary and envelope.
- Unit and template tests, plus the minimum integration-test update forced by the vocabulary rename.

**Out:**

- `NEED_CONTEXT` semantics, the `## Missing context` body section, and the `--extra-file` retry loop.
  Untouched.
- `ERROR` verdict handling, the ERROR-only retry paths (mill-start step 3.5, mill-plan step 4.5), and `stuck_type` classification.
  Untouched.
- The reviewer registry (`mill-agents.yaml`), model tiers, `maybe_switch_spec_for_large_prompt`, and LLM-provider wrappers.
  Untouched.
- Promotion of severity by class.
  The ceiling only demotes;
  see the `ceiling-demotes-only` Decision.
- The `rounds` config key and its backstop role.
  No new loop-exit mechanism is added;
  see the `loop-exit-needs-no-new-mechanism` Decision.
- Adding new review types, new scopes, or new verdicts.
- Wiki writes of any kind.
  This task touches only `plugins/mill/` and the hub `mill-config.yaml`.
- Rewriting historical review files already on disk.
  Back-compat is read-only;
  see the `gaps-found-back-compat` Decision.

## Decisions

### unified-severity-vocabulary

- Decision: all three review types use `[BLOCKING]` / `[NIT]` as finding severities and `APPROVE` / `REQUEST_CHANGES` as verdicts.
  `GAP`, `NOTE`, and `GAPS_FOUND` are removed from every template and SKILL and are never emitted again.
- Rationale: two of the three review types already speak this vocabulary, so the migration is smaller in this direction.
  It collapses `finalize_scope()`'s per-type severity fork, shrinks `parse_verdict()`'s closed value set from four to three,
  and lets `count_unrecognized_severity_findings()` drop its two severity parameters in favour of a single module-level constant pair.
- Rejected: keeping `GAP` / `NOTE` / `GAPS_FOUND` as the winning vocabulary (three of five templates would have to change instead of two, and "GAP" reads wrong for a code-review finding about a real defect);
  inventing a third neutral pair such as `[MUST]` / `[MAY]` (all five templates change, and no reader benefit).

### class-syntax-in-bracket

- Decision: class is encoded inside the same bracket as severity, colon-separated: `### [BLOCKING:design] <short title>`.
  Class names are lowercase ASCII;
  severity names are uppercase ASCII.
- Rationale: keeps the existing one-bracketed-label-per-heading convention that every template, every regex, and every SKILL already assumes.
  A separate `**Class:** design` field line would leave both existing regexes untouched but would add a fourth field to a finding format the templates deliberately cap at 3–5 lines, and would let a reviewer omit it silently.
- Rejected: a separate `**Class:**` field line;
  moving entirely to a structured `findings:` YAML block and deprecating markdown headings (the YAML path exists only as a fallback in `parse_blocking_count()` and is not what reviewers actually emit).

### taxonomy-applies-to-all-three-review-types

- Decision: the class dimension applies uniformly to discussion, plan, and code review.
  All three share one finding format, one envelope schema, and one set of class names.
- Rationale: they already share `_review_common.py`, `finalize_scope()`, `write_review_file()`, `parse_verdict()`, and the `ReviewResult` envelope.
  A discussion-only taxonomy would fork the shared layer for no semantic gain.
- Rejected: discussion-only with a generically-shaped field for later adoption (defers a migration that is cheaper to do once);
  per-type class vocabularies.

### severity-and-class-independent-with-ceiling

- Decision: severity and class are independent dimensions.
  The reviewer emits both.
  Each stage declares which classes are permitted to be blocking at that stage, and the backend demotes `BLOCKING` → `NIT` for any finding whose class falls outside that set.
- Rationale: this is the mechanism that makes the whole task work.
  It preserves the reviewer's judgment on severity while capping the economics per stage, so a discussion reviewer physically cannot force a fifth round over a missed call site the build will find for free.
  Because the verdict then derives from the count of *surviving* blocking findings, the "stop when a round returns zero design gaps" rule from issue #788 falls out of the existing loop with no new mechanism.
- Rejected: deriving severity entirely from class (the reviewer loses the ability to say "this scope finding is genuinely serious", and the two dimensions collapse into the severity ladder the issue warned against);
  fully independent with no ceiling and only template prose steering the reviewer (restores the original problem — a reviewer can keep filing blocking scope findings for four rounds).

### ceiling-demotes-only

- Decision: the stage table is a ceiling, never a floor.
  A finding emitted as `[NIT:design]` at the discussion stage stays `NIT`.
  The backend never promotes.
- Rationale: the reviewer is always free to judge something *less* serious than the table permits;
  the table exists to stop the reviewer inflating cheap findings, not to force it to inflate its own.
  Promotion would make class fully determine severity, which is the rejected option of the previous Decision arriving by the back door.
- Rejected: exact class-to-severity mapping in both directions.

### blocking-classes-in-config

- Decision: the per-stage class set lives in `mill-config.yaml` under each review role, as `blocking_classes`, following the existing `rounds` / `reviewer` shape:

  ```yaml
  roles:
    discussion-review:
      holistic:
        rounds: 4
        reviewer: sonnetmax
        blocking_classes: [design]
    plan-review:
      batch:
        blocking_classes: [design, scope]
      holistic:
        blocking_classes: [design, scope]
    code-review:
      batch:
        blocking_classes: [design, scope, decision, consistency]
      holistic:
        blocking_classes: [design, scope, decision, consistency]
  ```

- Rationale: per-role and per-scope granularity matches how every other review knob is already expressed, and it is genuinely worth tuning — a repo where discussion review is the only review stage wants `[design, scope]` there.
  The values encode the task's thesis directly: each downstream stage promotes one more class to blocking as that class becomes cheaply and reliably verifiable at that stage.
- Rejected: a hardcoded constant keyed by `review_type` in `_review_common.py` (no operator control, and it would not express the per-scope distinction);
  a single global `review.blocking_classes` per review type outside `roles:`.

### verdict-derives-from-surviving-blocking-count

- Decision: `verdict` is `REQUEST_CHANGES` if and only if at least one finding is `BLOCKING` **after** the ceiling has been applied;
  otherwise `APPROVE`.
  A round that produces one `[BLOCKING:design]` and three `[BLOCKING:scope]` findings at the discussion stage yields three demotions and a verdict of `REQUEST_CHANGES`.
  A round that produces only `[BLOCKING:scope]` findings at the discussion stage yields `APPROVE` with three NITs.
- Rationale: makes the verdict mean "is there anything serious here at this stage", which is what every consumer already assumes it means.
  The reviewer's own `verdict:` line in its output is advisory and is recomputed by the backend from the post-ceiling counts, exactly as `blocking_count` already is.
- Rejected: keeping the reviewer's verdict authoritative and carrying the exit signal in a separate envelope field (two sources of truth for the same question).

### loop-exit-needs-no-new-mechanism

- Decision: no new loop-exit rule is added anywhere.
  mill-start, mill-plan, and mill-go keep their existing "exit on `APPROVE`, `rounds` is the backstop" loops verbatim.
  Issue #788's behavioural consequence 1 is delivered entirely by the ceiling changing what `APPROVE` means.
- Rationale: the existing loops already exit on `APPROVE`.
  Once `APPROVE` means "zero surviving blocking findings" and only `design` survives at the discussion stage, "stop when a round returns zero design gaps" is already the behaviour.
  Adding a parallel exit condition would be dead weight.
- Rejected: an explicit `design_gap_count == 0` exit check in the mill-start loop.
- Accepted cost: the non-design fixes applied in the final round are never re-reviewed, because the round that produced them is the round that exits.
  This is deliberate — re-reviewing them is exactly the churn this task removes.

### unknown-class-preserves-stated-severity

- Decision: a finding whose bracket carries no class (`### [BLOCKING] <title>`) or an unrecognised class (`### [BLOCKING:perf]`) is a reviewer defect, and is handled as follows:
  - Its **stated severity is preserved** — `[NIT:perf]` stays `NIT`, `[BLOCKING]` stays `BLOCKING`.
  - It records `class: null` in the `findings` list and is **exempt from the ceiling**, since a class that cannot be read cannot be checked against `blocking_classes`.
  - A one-line ASCII warning goes to stderr naming the heading.
  - The review still lands and the round still counts.
- Rationale: an off-vocabulary *severity* is genuinely unknown in the dimension that decides blocking, which is why the existing house pattern folds it into the blocking bucket.
  An unknown *class* is different: the severity token was read successfully, so the reviewer's blocking judgment is available and there is nothing to be conservative about.
  Forcing `[NIT:perf]` to `BLOCKING` would let one typo in a cosmetic finding flip a round to `REQUEST_CHANGES` and cost a full extra review round.
  Exemption from the ceiling is the conservative half: an unclassifiable `BLOCKING` is never silently demoted.
- Rejected: folding unknown-class findings into the blocking bucket regardless of stated severity (the r1 reviewer showed this double-counts — see the `single-pass-finding-extraction` Decision — and it overreacts to a typo in a dimension that does not decide blocking);
  hard-failing the review with `verdict: ERROR` and letting the existing ERROR-only retry re-dispatch (a literal reading of "it's an error", but it burns a full re-review round per malformed heading and, on a second consecutive occurrence, blocks the task outright).

### single-pass-finding-extraction

- Decision: `finalize_scope()` extracts every finding **once**, into the `findings` list, and derives `blocking_count` and `nit_count` from that list by counting.
  The two independent regex sweeps that exist today — `parse_blocking_count()` called once per severity, plus `count_unrecognized_severity_findings()` sweeping the whole document again — are replaced for the new-review path by one `extract_findings(raw_text) -> list[Finding]` pass.
  `parse_blocking_count()` survives only for the historical re-read sites named in the `ceiling-applied-once-at-write-time` Decision, which need a count and not a classification.
- Rationale: the r1 reviewer identified a real double-count that only a single pass eliminates structurally.
  Today the two sweeps are mutually exclusive by construction — a heading with an unrecognised *severity* cannot also match `parse_blocking_count(severity="NIT")`, because the severity token is what both key on.
  Adding a class axis breaks that invariant: `### [NIT:perf]` matches `parse_blocking_count(severity="NIT")` on its severity token *and* trips a class-unrecognised sweep, so it lands in both counters.
  Reconciling two sweeps with subtraction rules would be fragile;
  extracting each heading exactly once and classifying it in place cannot double-count by construction, and it is the same pass that has to build the `findings` list anyway.
- Rejected: keeping the two sweeps and subtracting the overlap (the overlap set is not expressible without re-deriving per-finding identity, which is the single pass);
  keeping the two sweeps and accepting the double count.
- Note: the mixed-format property that `count_unrecognized_severity_findings()` was written to hold — a document with markdown headings for one severity and a fenced `findings:` YAML block for the other must not hide a finding in whichever mechanism the known labels did not use — is preserved by having the single pass scan **both** mechanisms and concatenate, deduplicating by heading title.
  This property is non-negotiable;
  see the Testing section.

### gaps-found-back-compat

- Decision: `parse_verdict()` keeps `GAPS_FOUND` in its accepted value set as a historical-only value and normalises it to `REQUEST_CHANGES` in the returned envelope.
  No template ever emits it again.
  The same applies to `[GAP]` / `[NOTE]` headings in files already on disk: under the unified vocabulary they are off-vocabulary severity labels and are therefore folded into the blocking bucket by the existing mechanism, which is the safe direction.
- Rationale: read-tolerance, not a correctness requirement — and this is worth stating precisely, because the obvious justification is wrong.
  **No code path re-reads a historical discussion-review verdict.** `discover_round()` (`_review_common.py:429–470`) matches on filename only and never opens the file;
  `_review_plan.py`'s recovery and resume re-reads both filter on `m.group("type") == "plan"`;
  `_nit_gate.py` is code-review only.
  `GAP` / `NOTE` / `GAPS_FOUND` was always discussion-review-only vocabulary, so none of those sites can encounter it.
  What remains is that archived review files under `_mill/reviews/` are read by humans, by `mill-inspect`, and by any manual or future re-parse, and keeping `GAPS_FOUND` in the accepted set costs exactly one tuple entry in each of `parse_verdict()`'s two closed-set checks.
  A hard cut buys nothing and makes every archived discussion review unparseable forever.
- Rejected: removing `GAPS_FOUND` from the accepted set outright (defensible on the code-path evidence, but the retention cost is one tuple entry against permanent loss of archive readability);
  retaining it while claiming a code path depends on it (factually false, and the r1 reviewer correctly caught the earlier draft doing so).

### structured-findings-in-envelope

- Decision: `ReviewResult.to_dict()` gains a `findings` list.
  Each entry is `{"severity": "BLOCKING"|"NIT", "class": "design"|"scope"|"decision"|"consistency"|null, "title": "<heading text>", "demoted": true|false}`.
  `blocking_count` and `nit_count` remain in the envelope as values derived from that list, so no existing consumer breaks.
  The list is per-scope inside each `reviews[]` entry and aggregated at the top level, mirroring how the scalars already aggregate.
- Rationale: it subsumes any per-class counts dict, and it removes a duplicated markdown re-parse — mill-start's `--auto` non-progress check currently parses gap titles out of the review file's `### [GAP]` headings by hand, and mill-plan/mill-go run comparable title-set comparisons.
  Those all become envelope reads.
  It also makes the issue's core diagnostic — "same class, fourth round running" — directly visible without counting headings.
- Rejected: a `class_counts` nested dict alongside the scalars (SKILLs keep re-parsing markdown for titles);
  flat `blocking_by_class` / `nit_by_class` dicts (same limitation, less detail).

### demotion-rewritten-into-review-file

- Decision: when the ceiling demotes a finding, `finalize_scope()` rewrites the heading in the text it writes to disk — `### [BLOCKING:scope] X` becomes `### [NIT:scope] X` — and inserts a `**Demoted-from:** BLOCKING` line as the first field line of that finding.
  The rewrite happens before `write_review_file()`, so the file on disk is the demoted form.
- Rationale: a SKILL that reads the review file and a SKILL that reads the envelope must route identically.
  If the file kept `[BLOCKING:scope]` while the envelope counted it as a NIT, mill-start step 5 would surface it to the operator as a numbered question while the envelope said `APPROVE`.
  Writing the demotion into the file also makes it auditable in the artefact a human actually reads, and it means the historical re-read sites (`_review_plan.py`, `_nit_gate.py`) see already-demoted files and need no ceiling logic of their own.
- Rejected: writing the reviewer's text verbatim and reflecting the demotion only in the envelope;
  a verbatim file plus an appended `## Demotions` section.

### ceiling-applied-once-at-write-time

- Decision: the ceiling, the demotion rewrite, and the per-class counting all live in `finalize_scope()` in `_review_common.py`, and nowhere else.
  The other three `parse_blocking_count()` call sites — `_review_plan.py:110`, `_review_plan.py:782`, `_nit_gate.py:95` — get only the widened regex.
- Rationale: all three of those sites re-read a review file that `finalize_scope()` already wrote, so the demotion is already baked into the text they read.
  Applying the ceiling again there would be a no-op at best and a double-demotion bug at worst.
  Note that `finalize_scope()` is not a fit for those sites regardless — it writes a file, and they are recovery and resume paths that must not.
- Rejected: a shared `count_findings_by_class()` helper invoked independently at all four sites;
  refactoring the re-read sites to route through `finalize_scope()`.

### class-definitions-generic-across-stages

- Decision: one definition set, identical in all three stages, with stage-specific *examples* in each template:
  - `design` — a decision is missing, wrong, or rests on a false premise.
  - `scope` — the work inventory is incomplete, or the enumeration method is unreliable.
  - `decision` — a named artifact with no stated disposition.
  - `consistency` — the artefact contradicts itself, carries a superseded statement, or violates an established repo convention.
- Rationale: the class names have to mean the same thing in the envelope regardless of which review produced it, or `blocking_classes` is not comparable across stages and the per-class diagnostics are meaningless.
  `consistency` is widened from issue #788's wording ("the document contradicts itself or carries a superseded statement") to include repo-convention violations, which is what makes it a useful class for code review rather than a discussion-only one.
- Rejected: per-stage meanings for the same four names;
  dropping `decision` for plan and code review.

### mill-start-routes-on-severity

- Decision: mill-start's Phase: Discussion Review step 5 routes on severity alone — `BLOCKING` findings become numbered operator questions, `NIT` findings are auto-resolved by the orchestrator under `mill-receiving-review`'s fix-everything default.
  The SKILL contains no class logic whatsoever.
- Rationale: because the discussion stage's `blocking_classes` is `[design]`, severity-based routing *is* "only design reaches the operator", with no duplicated rule.
  It also tracks the config for free: an operator who sets `blocking_classes: [design, scope]` gets scope findings routed to the operator without editing the SKILL.
- Rejected: explicit class-based routing in the SKILL (duplicates the ceiling's logic in prose, and would diverge from the config the moment either changed).

### out-of-scope-section-per-template

- Decision: each of the five review-prompt templates gains a `## Out of scope for this stage` section with stage-specific prose.
  The discussion template's version states that call-site and compile-breakage enumeration belongs to the build and to code review, and that an unreliable enumeration method is **one** `design` finding, never N `scope` findings.
  The plan templates' version states that per-line code correctness belongs to code review.
  The code templates' version states that re-litigating a decision already recorded in `discussion.md` is out of scope unless new evidence contradicts it.
- Rationale: the ceiling stops a cheap finding from *blocking*, but it does not stop the reviewer from spending its token budget generating it.
  Explicit negative instruction is the only lever on that, and it is necessarily different per stage — a code reviewer legitimately cares about things a discussion reviewer should skip.
- Rejected: negative bullets folded into the existing `## Criteria` list (buried among 8–14 positive criteria);
  a shared partial rendered into all five via a new token (over-engineering for prose that is deliberately different in every instance).

### anti-ladder-guarantee-stated-three-times

- Decision: the guarantee — **class governs who decides and when the loop stops, never whether a finding gets fixed** — is stated verbatim in three places: `mill-receiving-review`'s Forbidden Dismissals list as a sibling bullet to "NITs are not optional", `review-output.schema.md`'s class section, and the severity block of every review template.
- Rationale: the failure mode this guards against is a reading error, not a code path — a reviewer or orchestrator reading class as a severity ladder and filing or dismissing real problems as `scope` to dodge the fix-everything default.
  A reading error is prevented by being unmissable at each point of contact, not by being correct once in a document the reader may not open.
  `mill-receiving-review` already fights the identical battle for NITs, and the redundancy there is what makes it work.
- Rejected: stating it only in `mill-receiving-review` with links from schema and templates;
  stating it only in `review-output.schema.md`.

### testing-scope

- Decision: thorough unit coverage plus the minimum forced integration edit.
  One new `plugins/mill/unit_tests/test-review-class-taxonomy.py` covers the ceiling table, demote-only behaviour, the demotion rewrite, and verdict derivation.
  Existing files are extended: `test-review-common.py` (widened regexes, unknown-class folding, `GAPS_FOUND` normalisation), the three flow tests (envelope `findings` shape), `test-review-templates.py` (the template contract — unified vocabulary, class syntax, `## Out of scope for this stage` present, anti-ladder sentence present), `test-nit-gate.py` (`[NIT:consistency]` matches), and `test-review-output-contract.py`.
  `integration_tests/test-review-discussion.py` line 166 asserts `("APPROVE", "GAPS_FOUND")` and gets its verdict assertion updated — no new integration assertions.
- Rationale: everything decided here is deterministic backend behaviour testable with in-memory fixtures.
  Asserting that a live reviewer emits well-formed `[BLOCKING:design]` headings would be a model-behaviour test — slow, paid, and flaky — and the unknown-class folding path is precisely the designed handling for when it does not.
- Rejected: adding live-reviewer format assertions to the integration test;
  folding the taxonomy tests into `test-review-common.py` with no new file (it is already 3983 lines).

## Technical context

**The four severity-parsing call sites.**
All of them break silently on `[BLOCKING:design]` unless changed, because a colon and lowercase letters match neither existing pattern.

- `_review_common.py:1661` — `parse_blocking_count()`, pattern `^###\s+\[<severity>\]\s+`, MULTILINE, case-sensitive.
  Needs an optional class group: `^###\s+\[<severity>(?::(?P<cls>[a-z-]+))?\]\s+`.
  It keeps its count-only signature and remains in use for the historical re-read sites;
  the new-review path goes through `extract_findings()` instead (see the `single-pass-finding-extraction` Decision).
- `_review_common.py:1719` — `count_unrecognized_severity_findings()`, pattern `^###\s+\[([A-Z0-9-]+)\]\s+`.
  Its off-vocabulary-*severity* responsibility folds into `extract_findings()` for the new-review path.
  It does **not** gain an unknown-*class* responsibility — that is `extract_findings()`'s job and lives in the same single pass, which is what prevents the double count.
- `_review_plan.py:110` and `_review_plan.py:782` — re-read historical review files;
  regex only.
- `_nit_gate.py:95` — code-review only, so no demotion ever fires there, but it must still match `### [NIT:consistency]`;
  regex only.

**The new extraction function.**
`extract_findings(raw_text) -> list[Finding]` in `_review_common.py`, where `Finding` carries `severity`, `class` (or `None`), `title`, and `demoted`.
It scans both the markdown-heading mechanism and the fenced-`findings:`-YAML mechanism, concatenates, and deduplicates by heading title.
Severity classification per finding: recognised severity → kept;
unrecognised severity → forced to `BLOCKING` (the existing house rule).
Class classification per finding: recognised class → kept and subject to the ceiling;
missing or unrecognised class → `None`, exempt from the ceiling, stderr warning.
`finalize_scope()` calls it once, applies the ceiling to the returned list, performs the demotion rewrite on the text it is about to write, and derives both scalars by counting the list.

**The YAML fallback path.**
`parse_blocking_count()` falls back to scanning fenced ` ```yaml ` blocks for a `findings:` list when zero headings match, counting entries by their `severity:` field (`_review_common.py:1674–1707`);
`count_unrecognized_severity_findings()` duplicates that scan (`:1729–1758`).
Both need a `class:` field alongside `severity:`, with the same unknown/missing handling as the heading path.
The duplication between the two functions is deliberate and documented (`_review_common.py:1713`) — a mixed-format document could otherwise hide a finding in whichever mechanism the known labels did not use.
Preserve that property;
do not "simplify" one scan into the other.

**The single chokepoint.**
`finalize_scope()` at `_review_common.py:1867` is where verdict parsing, file writing, and both counters already meet, and it is the only place that produces counts for a *new* review.
Its per-type severity fork at `:1906–1909` disappears under the unified vocabulary.
The ceiling, the demotion rewrite, and the `findings` list all belong here.
Note that the demotion rewrite must happen before `write_review_file()` at `:1900` but after `apply_actual_model_override()` at `:1898`.

**The envelope.**
`ReviewResult` is a dataclass at `_review_common.py:286` with `to_dict()` at `:297`.
`_review_plan.py:1063–1070` aggregates `blocking_count` / `nit_count` across sub-reviews with a `sum()` over `reviews[]`;
the `findings` list aggregates by concatenation at the same site.
`_review_cli.py:36` constructs an error envelope with a hardcoded `"blocking_count": 0` and needs an empty `findings: []` alongside it.

**Verdict vocabulary.**
`parse_verdict()` at `_review_common.py:1517–1588` carries the closed set in two places — the fenced-block path at `:1562` and the unfenced-fallback path at `:1582`.
Both need `GAPS_FOUND` retained-but-normalised.
The docstring at `:1517` documents the v1 `GAPS_FOUND` rationale and should be rewritten to describe it as historical.

**Config.**
`plugins/mill/templates/mill-config.yaml` roles start at line 136 (`discussion-review`), 144 (`plan-review`), 156 (`code-review`).
Per CLAUDE.md, the hub `mill-config.yaml` and this plugin template must stay in sync — the template seeds new hubs, so both files need the `blocking_classes` key.
Unknown config keys emit a stderr warning at load time and load proceeds (template comment, line 19), so a hub that has not been updated degrades to a missing key rather than an error;
`_review_common.load_config()` should therefore supply the documented per-stage defaults when `blocking_classes` is absent, rather than raising.

**SKILL surfaces carrying the old vocabulary.**
`mill-start/SKILL.md` lines 46, 50, 247, 270, 336 (line 270 contains the literal JSON contract shown to the orchestrator, and line 50 is the `--auto` non-progress check that hand-parses `### [GAP]` heading text — that one becomes an envelope read per the `structured-findings-in-envelope` Decision).
`mill-plan/SKILL.md` line 60 mentions mill-start's GAPS_FOUND loop.
mill-start's steps 4a / 4b / 5 are written in terms of `[NOTE]` and `[GAP]` throughout and need renaming to `[NIT]` and `[BLOCKING]`;
their control flow is unchanged.

**Templates.**
Five review-prompt templates carry severity blocks and the "Severity vocabulary is closed" paragraph: `review-discussion.md` (lines 70–95), `review-plan-batch.md` (100–126), `review-plan-holistic.md` (96–116), `review-code-batch.md` (87–113), `review-code-holistic.md` (84–111).
`review-discussion.md:93` explicitly documents the vocabulary split and is deleted by this task.
`review-output.schema.md` documents the format authoritatively — the finding structure at lines 23–26 and 71–76, the severity rules at 78–88, and the verdict table at 131–140.

**Constraints file.**
No `CONSTRAINTS.md` exists at the hub root.
`read_constraints_md()` handles its absence already;
nothing to do.

## Constraints

- The hub `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml` must stay in sync (CLAUDE.md).
- All `print()` / `_log()` output must be ASCII only — no em-dashes or arrows in stderr warnings, including the new unknown-class warning.
- Generated markdown uses fenced ` ```yaml ` metadata blocks, never `---` frontmatter.
- `verify:` commands in plan batch files must start with a literal empty `PYTHONPATH=` prefix, since this is a Python project.
- Unit tests use in-memory or tempfile fixtures with no real git and no real LLM;
  scratch files go under `.scratch/`, never `/tmp/`.
- Reviews must stay tight — the templates cap findings at 3–5 lines each and target a few hundred tokens;
  the added `## Out of scope for this stage` section must not inflate the prompt materially.

## Testing

**TDD candidates** — write the test first, since the behaviour is fully specified here and has no dependency on how the parse is implemented:

- The ceiling table: for each of the three stages, a synthetic review text with one finding of each class, asserting exactly which survive as `BLOCKING`.
- Demote-only: `[NIT:design]` at the discussion stage stays `NIT`.
- Verdict derivation: `[BLOCKING:scope]` only, at the discussion stage, yields `APPROVE` with `nit_count == 1`.
- Unknown-class handling: `[BLOCKING:perf]` and bare `[BLOCKING]` stay `BLOCKING` and are exempt from demotion;
  `[NIT:perf]` and bare `[NIT]` stay `NIT`.
- **No double-counting:** `[NIT:perf]` at any stage contributes exactly 1 to `nit_count` and 0 to `blocking_count`, and appears exactly once in `findings`.
  This is the regression the r1 review caught;
  assert both scalars and the list length together, since asserting only one hides the bug.

**Scenarios that must be covered:**

- Regex: `[BLOCKING]`, `[BLOCKING:design]`, `[NIT:consistency]`, and mid-line occurrences that must *not* match.
- Mixed-format document — real markdown headings for one severity and a fenced `findings:` YAML block for the other — with an unknown class hidden in whichever mechanism the known labels did not use.
  This is the property `count_unrecognized_severity_findings()` was written to hold and that `extract_findings()` must inherit;
  a regression here is the most likely silent failure of the whole change.
- Deduplication: the same finding title present in both the heading mechanism and the YAML block appears once in `findings`, not twice.
- Demotion rewrite: the written file's heading and inserted `**Demoted-from:**` line, asserted against the file on disk, not against the in-memory text.
- Envelope shape: `findings` present per sub-review and aggregated at the top level, with `blocking_count` / `nit_count` still consistent with it.
- Back-compat: a historical review file with `verdict: GAPS_FOUND` and `### [GAP]` headings parses without raising, normalises to `REQUEST_CHANGES`, and folds the `GAP` findings into the blocking bucket.
- Missing `blocking_classes` in config falls back to the documented per-stage default rather than raising.
- Template contract, per template: unified vocabulary only, class syntax shown in the finding example, `## Out of scope for this stage` present, anti-ladder sentence present.
- `_nit_gate` counts `[NIT:consistency]` in a code-review file.

**Not tested:** live reviewer output format, LLM-provider behaviour, and anything requiring a real dispatch.

## Q&A log

- **Q:** Should the class dimension be discussion-only or generalise to plan and code review? **A:** Uniform vocabulary and taxonomy across all three; behaviour differs only through each stage's `blocking_classes` value.
- **Q:** Should the split severity vocabulary be unified as part of this task? **A:** Yes — this expanded the task from the original proposal. `BLOCKING`/`NIT` + `APPROVE`/`REQUEST_CHANGES` wins; `GAP`/`NOTE`/`GAPS_FOUND` retired.
- **Q:** Issue #788 proposed a separate "stop when a round returns zero design gaps" exit rule. Is that still needed? **A:** No. It was never in the proposal that the *verdict* should carry the signal, but under the ceiling it does, so the existing APPROVE-based loop exit already implements it. No new mechanism.
- **Q:** What happens when a reviewer emits a finding with no class? **A:** It is a defect, not a supported fallback — but it is handled tolerantly rather than by failing the round. Refined in review round 1: the stated severity is preserved (an unknown *class* does not make the *severity* unknown), the finding is exempt from the ceiling, and a stderr warning fires.
- **Q:** [review r1] Can a recognized-severity/unrecognized-class finding land in both counters? **A:** Yes, under the two-sweep design it would have. Fixed structurally by extracting every finding exactly once into the `findings` list and deriving both scalars from it.
- **Q:** [review r1] Does any code path actually re-read a historical discussion-review verdict? **A:** No — verified. `GAPS_FOUND` back-compat is retained for archive readability at a cost of one tuple entry, not because a code path depends on it.
- **Q:** Should the ceiling be able to promote a finding as well as demote it? **A:** No. Demote-only, so the reviewer can always judge something less serious than the table permits.
- **Q:** Does mill-start need class-aware routing logic? **A:** No. Routing on severity alone reproduces "only design reaches the operator" and tracks `blocking_classes` automatically.
- **Q:** Should the demotion be visible in the review file or only in the envelope? **A:** In the file — otherwise a SKILL reading the file and a SKILL reading the envelope route differently.
- **Q:** Should the per-class information in the envelope be counts or a structured list? **A:** A structured `findings` list, which also lets the non-progress checks stop hand-parsing markdown for finding titles.
