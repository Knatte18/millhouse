# Review Output Schema

This file documents the canonical format for all review output files produced by the Layer 02 review system.
Every file written by `_review_common.write_review_file()` must conform to this schema. `parse_verdict()` in `_review_common.py` validates against this schema — specifically the `verdict:` field inside the fenced yaml block.

---

## File format

```markdown
# Review: <title>

```yaml
verdict: APPROVE | REQUEST_CHANGES | NEED_CONTEXT
reviewer_model: <reviewer name from config, e.g. sonnetmax>
duration_s: <wall-clock seconds for the whole round, including any resume-retry or fast-fail-retry>
tool_calls: <tool-use blocks the reviewer made, or the CLI's native turn count when it reports one>
cost_usd: <reported dollar cost of the round>
reviewer_self_id: <optional, reviewer-reported self-identification>
reviewed_file: <path to the artefact that was reviewed>
date: <UTC YYYY-MM-DD>
```

## Findings

### [BLOCKING|NIT][:design|scope|decision|consistency] <finding title>
**Section:** ...
**Issue:** ...
**Suggested fix:** ...

## Missing context
(present only when verdict is NEED_CONTEXT — one bullet per file the reviewer needs but could not find in the bulk)

- `path/to/needed_file.py` — why the reviewer needs it

## Verdict

APPROVE | REQUEST_CHANGES | NEED_CONTEXT
<one-sentence summary>
```

---

## Metadata block fields

The fenced ` ```yaml ` block placed immediately after the `# Review: ...` heading contains review metadata. Fields:

| Field | Type | Required | Values |
|---|---|---|---|
| `verdict` | string | yes | `APPROVE`, `REQUEST_CHANGES`, or `NEED_CONTEXT` (emitted set); `GAPS_FOUND` is also accepted on read, see below |
| `reviewer_model` | string | yes | reviewer name from config (e.g. `sonnetmax`, `sonnethigh`) |
| `duration_s` | number | no | wall-clock seconds for the whole round, including any resume-retry or fast-fail-retry |
| `tool_calls` | integer | no | tool-use blocks the reviewer made, or the CLI's native turn count when it reports one |
| `cost_usd` | number | no | reported dollar cost of the round |
| `reviewer_self_id` | string | no | optional, reviewer-self-reported model identification; unverified |
| `reviewed_file` | string | yes | path to the artefact reviewed (discussion file, batch file, or `plan/`) |
| `date` | string | yes | UTC date in `YYYY-MM-DD` format |

`reviewer_self_id` is unverified and reviewer-reported: it is the reviewer's own best-effort claim about what model/version it is, present only in the discussion and plan review templates, and it is never validated by `parse_verdict()`. This is distinct from `reviewer_model`, which is orchestrator-supplied — dictated to the reviewer up front — and which `apply_actual_model_override()` (invoked via the CLIs' `--actual-model` flag) can rewrite after the fact.

`duration_s`, `tool_calls`, and `cost_usd` are orchestrator-supplied like `reviewer_model` — written into the persisted yaml header via the review CLIs' `--duration-s`/`--tool-calls`/`--cost-usd` finalize flags, not reported by the reviewer itself. `tool_calls` and `cost_usd` are absent under agent-mode and psmux dispatch, and for the gemini provider — those paths carry no such signal. Files written before this feature existed carry none of the three. Readers must treat all three fields as optional.

`parse_verdict()` scans for the first fenced ` ```yaml ` block in the document and returns the `verdict` value. If no fenced block is found, it falls back to scanning for an unfenced `verdict:` line (case-sensitive, with leading whitespace allowed). It raises `ReviewError` if:
- No ` ```yaml ` opening fence is found AND no unfenced `verdict:` line is found.
- The yaml block is not closed by a ` ``` ` line.
- The `verdict:` field is absent from the block.
- The `verdict:` value is none of the three emitted values above (`APPROVE`, `REQUEST_CHANGES`, `NEED_CONTEXT`) **and** is not the historical `GAPS_FOUND` value, which `parse_verdict()` accepts without raising and normalises to `REQUEST_CHANGES` (see the Verdict vocabulary table below).
  This is the asymmetry the `gaps-found-back-compat` Decision creates: the emitted set is three values wide, the accepted-input set is four.

Note: `---`-style YAML frontmatter is reserved for SKILL.md and plugin manifests per the markdown skill. Review output files must never use `---` frontmatter.

---

## Body sections

### `## Findings`

Required section. Each finding uses this structure:

```markdown
### [BLOCKING|NIT][:design|scope|decision|consistency] <finding title>
**Section:** the plan section / file / step the finding applies to
**Issue:** what is wrong or missing
**Suggested fix:** concrete suggestion for resolution
```

**Finding severity:**
- `BLOCKING` — must be resolved before the artefact can be approved.
  Causes `verdict: REQUEST_CHANGES`.
- `NIT` — optional quality improvement.
  Does not block approval.

**Severity vocabulary is closed, and unrecognized labels fail loud, not silent.**
All three review types recognize exactly two severity labels: `BLOCKING` and `NIT`.
The reviewer prompt templates instruct reviewers to use ONLY these labels — never an invented word (e.g. `MAJOR`, `MINOR`, `CRITICAL`, `MEDIUM`, `HIGH`) — and to default an ambiguous finding to `BLOCKING` rather than `NIT`.
As a code-level backstop against a reviewer LLM emitting an off-vocabulary label anyway, `count_unrecognized_severity_findings()` in `_review_common.py` scans every finding in a review's output — whether expressed as a markdown `### [XXX]` heading OR as a `severity:` entry inside a fenced ` ```yaml ` `findings:` block — and, for any label matching neither `BLOCKING` nor `NIT`, folds it into the blocking-equivalent counter (`blocking_count`) instead of silently dropping it from both `blocking_count` and `nit_count`.
This runs inside `finalize_scope()` for every review, covering both output formats unconditionally so a mixed-format document (e.g. real `### [NIT]` headings alongside an unrecognized label expressed only in a YAML `findings:` entry) cannot hide an off-vocabulary finding in whichever format the two known severities did not use.

**Class is a second, independent axis.**
It is encoded inside the same bracket as severity, colon-separated: `### [BLOCKING:design] <title>`.
The class suffix is optional in grammar — a bare `### [BLOCKING] <title>` still parses — but required in practice: every reviewer prompt instructs the reviewer to always supply one.
A finding with no class, or with a class outside the four recognised names, is a reviewer defect: it keeps its stated severity, records `class: null` in the `findings` list, and is exempt from the `blocking_classes` ceiling described below.

### Class

The four recognised classes, identical in meaning across every review stage (discussion, plan, code):

- `design` — a decision is missing, wrong, or rests on a false premise.
- `scope` — the work inventory is incomplete, or the enumeration method is unreliable.
- `decision` — a named artifact with no stated disposition.
- `consistency` — the artefact contradicts itself, carries a superseded statement, or violates an established repo convention.

Each review role's `mill-config.yaml` entry carries a `blocking_classes` list — the per-stage **ceiling**.
A `BLOCKING` finding whose class is not in that stage's `blocking_classes` list is demoted to `NIT` when the review is finalized;
a finding already `NIT` is never touched, and no finding is ever promoted from `NIT` to `BLOCKING`.
The ceiling is demote-only, never a floor.

**Class governs who decides and when the loop stops, never whether a finding gets fixed.**

If there are no findings, write `(no findings)` under `## Findings`.

### `## Verdict`

Required section.
Contains exactly two lines:

```
APPROVE | REQUEST_CHANGES
<one-sentence summary of the verdict rationale>
```

The verdict line must match the `verdict:` field in the yaml block exactly.

---

## Canonical filenames

Review files are named by `write_review_file()` according to these patterns:

| Review type | Filename pattern |
|---|---|
| Discussion / code / plan holistic | `<ts>-<type>-review-r<N>.md` |
| Plan per-batch | `<ts>-plan-review-<batch-name>-r<N>.md` |

Where:
- `<ts>` = `YYYYMMDD-HHMMSS` UTC timestamp
- `<type>` = `discussion`, `code`, or `plan`
- `<N>` = 1-indexed round number
- `<batch-name>` = batch stem from `plan/NN-<name>.md`, matching `[a-z0-9-]+`

Examples:
- `20260418-001200-discussion-review-r1.md`
- `20260418-143300-code-review-r2.md`
- `20260418-143300-plan-review-r1.md`
- `20260418-143300-plan-review-03-templates-r1.md`

---

## Verdict vocabulary

| Verdict | Meaning | Appears in |
|---|---|---|
| `APPROVE` | Artefact is complete and correct. NITs recorded but do not block. | yaml block + `## Verdict` body |
| `REQUEST_CHANGES` | One or more BLOCKING findings survive the stage's `blocking_classes` ceiling. All three review types. | yaml block + `## Verdict` body |
| `GAPS_FOUND` | Historical discussion-review-only value. Never emitted by any current template, SKILL, or script. `parse_verdict()` still accepts it on read (e.g. archived review files) and normalises it to `REQUEST_CHANGES`. | never emitted; accepted on read only |
| `NEED_CONTEXT` | Reviewer cannot evaluate without source files not provided in the bulk. The body's `## Missing context` section lists which files. Orchestrator responds by re-firing with `--extra-file <path>` per needed file, and must also notify + self-report the incomplete plan reference. Never guess. | yaml block + `## Verdict` body |
| `ERROR` | Sub-review failed (LLM error, timeout, etc.). | `reviews[]` entries in `ReviewResult` only — never in review files |

`ERROR` never appears inside a review file.
It is only used in the `ReviewResult` JSON emitted by the API scripts when a sub-review fails at the LLM-provider layer.

`NEED_CONTEXT` is the reviewer's escape hatch when it cannot evaluate without reading a file the orchestrator did not bulk.
The discipline is: reviewers never fabricate file contents from filename/position clues.
If a claim cannot be verified against the provided source, emit `NEED_CONTEXT` — the orchestrator owns the retry.

---

## Findings envelope

`ReviewResult.to_dict()` serialises a `findings` list alongside the existing `blocking_count` and `nit_count` scalars.
Each entry has the exact shape:

```json
{"severity": "BLOCKING" | "NIT", "class": "design" | "scope" | "decision" | "consistency" | null, "title": "<heading text>", "demoted": true | false}
```

`blocking_count` and `nit_count` are derived from this list, not computed independently — counting the list's `severity` values reproduces both scalars exactly.
`demoted` is `true` when the `blocking_classes` ceiling rewrote the finding from `BLOCKING` down to `NIT` at finalize time; `false` otherwise.
The `findings` list appears per-scope inside each `reviews[]` entry, and again aggregated (concatenated across scopes) at the top level of the envelope — mirroring how `blocking_count` / `nit_count` already aggregate.
