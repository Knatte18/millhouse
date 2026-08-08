# Plan: Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch

```yaml
task: "Classify review GAPs by kind (design/scope/decision/consistency); scope discussion review to what downstream stages cannot catch"
slug: "review-gap-classification-by-kind"
approved: false
started: "20260808-172233"
parent: "main"
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: core-taxonomy
    file: 01-core-taxonomy.md
    depends-on: []
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-class-taxonomy.py test-review-common.py test-review-finalize.py"
  - number: 2
    name: discussion-backend
    file: 02-discussion-backend.md
    depends-on: [1]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-discussion-flow.py test-review-cli-error-envelope.py test-bg-json-contract.py test-bg-liveness.py"
  - number: 3
    name: plan-backend
    file: 03-plan-backend.md
    depends-on: [1]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py"
  - number: 4
    name: code-backend
    file: 04-code-backend.md
    depends-on: [1]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-code-flow.py test-nit-gate.py"
  - number: 5
    name: templates-and-config
    file: 05-templates-and-config.md
    depends-on: [1]
    verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-templates.py test-review-output-contract.py"
  - number: 6
    name: skills-start-plan-receiving
    file: 06-skills-start-plan-receiving.md
    depends-on: [1, 5]
    verify: null
  - number: 7
    name: skill-mill-go
    file: 07-skill-mill-go.md
    depends-on: [1]
    verify: null
```

## Shared Decisions

### Decision: unified-severity-vocabulary

- **Decision:** all three review types use `[BLOCKING]` / `[NIT]` as finding severities and `APPROVE` / `REQUEST_CHANGES` as verdicts.
  `GAP`, `NOTE`, and `GAPS_FOUND` are never emitted again by any template, SKILL, or script.
  `GAPS_FOUND` survives only as a historical value accepted by `parse_verdict` and normalised to `REQUEST_CHANGES`.
- **Rationale:** two of three review types already speak this vocabulary, so the migration is smaller in this direction; it collapses `finalize_scope`'s per-review-type severity fork and lets the module carry one severity pair as a constant.
- **Applies to:** all batches

### Decision: class-syntax-in-bracket

- **Decision:** class is encoded inside the same bracket as severity, colon-separated: `### [BLOCKING:design] <short title>`.
  Severity tokens are uppercase ASCII; class tokens are lowercase ASCII.
  The four recognised classes are `design`, `scope`, `decision`, `consistency`.
- **Rationale:** preserves the one-bracketed-label-per-heading convention every template, regex, and SKILL already assumes; a separate field line would add a fourth line to a finding format capped at 3-5 lines and could be silently omitted.
- **Applies to:** all batches

### Decision: class-definitions-generic-across-stages

- **Decision:** one definition set, identical in all three stages, with only the *examples* differing per template:
  - `design` -- a decision is missing, wrong, or rests on a false premise.
  - `scope` -- the work inventory is incomplete, or the enumeration method is unreliable.
  - `decision` -- a named artifact with no stated disposition.
  - `consistency` -- the artefact contradicts itself, carries a superseded statement, or violates an established repo convention.
- **Rationale:** class names must mean the same thing in the envelope regardless of which review produced it, or `blocking_classes` is not comparable across stages and the per-class diagnostics are meaningless.
- **Applies to:** batches 1, 5

### Decision: ceiling-applied-once-at-write-time

- **Decision:** the `blocking_classes` ceiling, the demotion rewrite, and the per-class counting all live in `finalize_scope` in `_review_common.py` and nowhere else.
  The historical re-read sites -- `_review_plan._scan_approved_batches`, `_review_plan.run`'s crash-recovery re-read, and `_nit_gate.compute_unfixed_nits` -- never apply the ceiling.
  The two `_review_plan` sites do call `extract_findings`, because their entries feed the same aggregation as the write-time entries and would otherwise contribute counts without contributing findings; extraction is not ceiling application, and the file they read was already written in its demoted form.
  `_nit_gate.compute_unfixed_nits` needs only a count and stays on the widened `parse_blocking_count` regex.
- **Rationale:** those sites re-read a review file `finalize_scope` already wrote, so the demotion is already baked into the text they read; applying the ceiling again would be a no-op at best and a double-demotion at worst.
  `finalize_scope` also writes a file, which recovery and resume paths must not do.
- **Applies to:** batches 1, 3, 4

### Decision: ceiling-demotes-only

- **Decision:** the stage table is a ceiling, never a floor.
  `[NIT:design]` at the discussion stage stays `NIT`.
  The backend never promotes a finding's severity.
- **Rationale:** the reviewer must stay free to judge something less serious than the table permits; promotion would make class fully determine severity, collapsing the two dimensions into the severity ladder this task exists to prevent.
- **Applies to:** batches 1, 5

### Decision: unknown-class-preserves-stated-severity

- **Decision:** a finding with no class (`### [BLOCKING] <title>`) or an unrecognised class (`### [BLOCKING:perf]`) keeps its stated severity, records `class: null` in the `findings` list, is exempt from the ceiling, and emits a one-line ASCII stderr warning naming the heading.
  The review still lands and the round still counts.
  An unrecognised *severity* is unchanged from today's house rule: it is forced to `BLOCKING`.
- **Rationale:** the severity token was read successfully, so the reviewer's blocking judgment is available and there is nothing to be conservative about; forcing `[NIT:perf]` to `BLOCKING` would let one typo cost a full extra review round.
  Ceiling exemption is the conservative half -- an unclassifiable `BLOCKING` is never silently demoted.
- **Applies to:** batches 1, 5

### Decision: single-pass-finding-extraction

- **Decision:** `extract_findings(raw_text) -> list[Finding]` extracts every finding exactly once and `finalize_scope` derives `blocking_count` and `nit_count` by counting that list.
  The two independent regex sweeps used today (`parse_blocking_count` per severity plus `count_unrecognized_severity_findings` over the whole document) are no longer used on the new-review path.
- **Rationale:** with a class axis, `### [NIT:perf]` would match `parse_blocking_count(severity="NIT")` on its severity token *and* trip a class-unrecognised sweep, landing in both counters.
  Extracting each heading once and classifying it in place cannot double-count by construction, and it is the same pass that has to build the `findings` list anyway.
- **Applies to:** batches 1, 3, 4

### Decision: dual-mechanism-scan-preserved

- **Decision:** `extract_findings` scans **both** the markdown-heading mechanism and the fenced-`findings:`-YAML mechanism unconditionally, concatenates the results, and deduplicates by heading title **across mechanisms only**.
  Two findings from the same mechanism that share a title are both kept.
  Neither scan is gated on the other's result.
- **Why the dedup is cross-mechanism only:** its purpose is to stop one finding being counted twice for appearing in both representations, not to merge distinct findings within one.
  A flat first-occurrence-wins dedup would drop a genuine second finding whose title happened to match, and would leave a `BLOCKING` heading on disk that no surviving `Finding` demotes.
- **Rationale:** this is the mixed-format property `count_unrecognized_severity_findings` was written to hold -- a document using markdown headings for one severity and a YAML block for the other must not be able to hide a finding in whichever mechanism the known labels did not use.
  A regression here is the most likely silent failure of the whole change.
- **Applies to:** batches 1, 3, 4

### Decision: verdict-derives-from-surviving-blocking-count

- **Decision:** `finalize_scope` recomputes the returned verdict from the post-ceiling finding list: `REQUEST_CHANGES` when at least one finding is still `BLOCKING` after the ceiling, otherwise `APPROVE`.
  `NEED_CONTEXT` parsed from the reviewer's own output is passed through unchanged and is never recomputed.
- **Rationale:** makes the verdict mean "is there anything serious here at this stage", which every consumer already assumes.
  It is also what delivers issue #788's "stop when a round returns zero design gaps" through the existing APPROVE-based loop exit, with no new loop mechanism anywhere.
- **Applies to:** batches 1, 2, 3, 4

### Decision: demotion-rewritten-into-review-file

- **Decision:** when the ceiling demotes a finding, `finalize_scope` rewrites the heading in the text it is about to write -- `### [BLOCKING:scope] X` becomes `### [NIT:scope] X` -- and inserts a `**Demoted-from:** BLOCKING` line as the first field line of that finding.
  The rewrite happens after `apply_actual_model_override` and before `write_review_file`, so the file on disk is the demoted form.
  Because `extract_findings` reads findings from both the markdown-heading mechanism and the fenced-`findings:`-YAML mechanism, the rewrite must correct **both** representations, keyed on the finding's title -- a demotion visible in only one of them is the same file/envelope divergence this Decision exists to prevent.
  The marker written by the rewrite is also the **re-read signal**: `extract_findings` sets `demoted: True` when it sees it, so a finding re-read from an already-written file reports the same `demoted` value it had when it was first finalized.
  Without that, the two `_review_plan.py` re-read sites would emit `demoted: false` for genuinely demoted findings and the envelope's `findings` list would disagree with itself across paths.
- **Rationale:** a SKILL reading the review file and a SKILL reading the envelope must route identically; if the file kept `[BLOCKING:scope]` while the envelope counted a NIT, mill-start would surface it as an operator question while the envelope said `APPROVE`.
  It also means the historical re-read sites see already-demoted files.
- **Applies to:** batches 1, 5, 6

### Decision: structured-findings-in-envelope

- **Decision:** `ReviewResult` gains a `findings` list serialised by `to_dict()`.
  Each entry is `{"severity": "BLOCKING"|"NIT", "class": "design"|"scope"|"decision"|"consistency"|null, "title": "<heading text>", "demoted": true|false}`.
  `blocking_count` and `nit_count` remain in the envelope as values derived from that list, so no existing consumer breaks.
  The list appears per-scope inside each `reviews[]` entry and aggregated at the top level, mirroring how the scalars already aggregate.
- **Rationale:** it subsumes any per-class counts dict and lets the SKILL-side non-progress checks stop hand-parsing markdown for finding titles.
- **Applies to:** batches 1, 2, 3, 4, 6, 7

### Decision: blocking-classes-config-with-defaults

- **Decision:** the per-stage class set lives in `mill-config.yaml` under each review role as `blocking_classes`, alongside `rounds` / `reviewer`.
  `_review_common.resolve_blocking_classes(cfg, review_type, scope)` reads it and falls back to the documented per-stage default when the key is absent, never raising:
  `discussion-review` -> `["design"]`; `plan-review` (both scopes) -> `["design", "scope"]`; `code-review` (both scopes) -> `["design", "scope", "decision", "consistency"]`.
- **Rationale:** per-role and per-scope granularity matches every other review knob; defaults mean a hub that has not been updated degrades to correct behaviour rather than an error, which is required because unknown config keys only warn.
- **Applies to:** batches 1, 2, 3, 4, 5

### Decision: anti-ladder-guarantee-stated-three-times

- **Decision:** the sentence **"Class governs who decides and when the loop stops, never whether a finding gets fixed."** is stated verbatim in `mill-receiving-review`'s Forbidden Dismissals list, in `review-output.schema.md`'s class section, and in the severity block of every one of the five review templates.
- **Rationale:** the failure mode is a reading error, not a code path -- a reviewer or orchestrator reading class as a severity ladder and filing or dismissing real problems as `scope` to dodge the fix-everything default.
  A reading error is prevented by being unmissable at each point of contact.
- **Applies to:** batches 5, 6

### Decision: ascii-only-stderr

- **Decision:** every new `print()` / `_log()` string added by this plan is ASCII-only -- no em-dash, no arrow glyph.
  Use ` -- ` and ` -> `.
- **Rationale:** Windows cp1252 crashes on non-ASCII stdout (CLAUDE.md).
- **Applies to:** all batches

### Decision: config-key-addition-is-safe-mid-flight

- **Decision:** adding `blocking_classes:` to `mill-config.yaml` and `plugins/mill/templates/mill-config.yaml` in batch 5 is safe while this very task is still being reviewed by the installed plugin cache.
- **Rationale:** the cache-resident `_config.load_config` treats an unrecognised key as a stderr warning and proceeds, and `resolve_blocking_classes` (batch 1) supplies the documented default when the key is absent.
  Neither the old cache code nor the new worktree code can fail on the key's presence or absence.
- **Applies to:** batch 5

## All Files Touched

- `mill-config.yaml`
- `plugins/mill/integration_tests/bench-reviewers.py`
- `plugins/mill/integration_tests/test-review-discussion.py`
- `plugins/mill/scripts/_review_cli.py`
- `plugins/mill/scripts/_review_code.py`
- `plugins/mill/scripts/_review_common.py`
- `plugins/mill/scripts/_review_discussion.py`
- `plugins/mill/scripts/_review_plan.py`
- `plugins/mill/scripts/millpy-review-plan.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
- `plugins/mill/skills/mill-receiving-review/SKILL.md`
- `plugins/mill/skills/mill-start/SKILL.md`
- `plugins/mill/templates/mill-config.yaml`
- `plugins/mill/templates/review-code-batch.md`
- `plugins/mill/templates/review-code-holistic.md`
- `plugins/mill/templates/review-discussion.md`
- `plugins/mill/templates/review-output.schema.md`
- `plugins/mill/templates/review-plan-batch.md`
- `plugins/mill/templates/review-plan-holistic.md`
- `plugins/mill/unit_tests/test-bg-json-contract.py`
- `plugins/mill/unit_tests/test-bg-liveness.py`
- `plugins/mill/unit_tests/test-nit-gate.py`
- `plugins/mill/unit_tests/test-review-class-taxonomy.py`
- `plugins/mill/unit_tests/test-review-cli-error-envelope.py`
- `plugins/mill/unit_tests/test-review-code-flow.py`
- `plugins/mill/unit_tests/test-review-common.py`
- `plugins/mill/unit_tests/test-review-discussion-flow.py`
- `plugins/mill/unit_tests/test-review-finalize.py`
- `plugins/mill/unit_tests/test-review-output-contract.py`
- `plugins/mill/unit_tests/test-review-plan-flow.py`
- `plugins/mill/unit_tests/test-review-templates.py`
