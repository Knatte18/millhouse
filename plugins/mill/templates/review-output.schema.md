# Review Output Schema

This file documents the canonical format for all review output files produced by the Layer 02 review system. Every file written by `_review_common.write_review_file()` must conform to this schema. `parse_verdict()` in `_review_common.py` validates against this schema — specifically the `verdict:` field inside the fenced yaml block.

---

## File format

```markdown
# Review: <title>

```yaml
verdict: APPROVE | REQUEST_CHANGES
reviewer_model: <reviewer name from config, e.g. sonnetmax>
reviewed_file: <path to the artefact that was reviewed>
date: <UTC YYYY-MM-DD>
```

## Findings

### [BLOCKING|NIT] <finding title>
**Section:** ...
**Issue:** ...
**Suggested fix:** ...

## Verdict

APPROVE | REQUEST_CHANGES
<one-sentence summary>
```

---

## Metadata block fields

The fenced ` ```yaml ` block placed immediately after the `# Review: ...` heading contains review metadata. Fields:

| Field | Type | Required | Values |
|---|---|---|---|
| `verdict` | string | yes | `APPROVE` or `REQUEST_CHANGES` |
| `reviewer_model` | string | yes | reviewer name from config (e.g. `sonnetmax`, `sonnetmax_tool`) |
| `reviewed_file` | string | yes | path to the artefact reviewed (discussion file, batch file, or `plan/`) |
| `date` | string | yes | UTC date in `YYYY-MM-DD` format |

`parse_verdict()` scans for the first fenced ` ```yaml ` block in the document and returns the `verdict` value. It raises `ReviewError` if:
- No ` ```yaml ` opening fence is found.
- The yaml block is not closed by a ` ``` ` line.
- The `verdict:` field is absent from the block.
- The `verdict:` value is not `APPROVE` or `REQUEST_CHANGES`.

Note: `---`-style YAML frontmatter is reserved for SKILL.md and plugin manifests per the markdown skill. Review output files must never use `---` frontmatter.

---

## Body sections

### `## Findings`

Required section. Each finding uses this structure:

```markdown
### [BLOCKING|NIT] <finding title>
**Section:** the plan section / file / step the finding applies to
**Issue:** what is wrong or missing
**Suggested fix:** concrete suggestion for resolution
```

**Finding severity:**
- `BLOCKING` — must be resolved before the artefact can be approved. Causes `verdict: REQUEST_CHANGES`.
- `NIT` — optional quality improvement. Does not block approval.

If there are no findings, write `(no findings)` under `## Findings`.

### `## Verdict`

Required section. Contains exactly two lines:

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
| `REQUEST_CHANGES` | One or more BLOCKING findings must be resolved. | yaml block + `## Verdict` body |
| `ERROR` | Sub-review failed (LLM error, timeout, etc.). | `reviews[]` entries in `ReviewResult` only — never in review files |

`ERROR` never appears inside a review file. It is only used in the `ReviewResult` JSON emitted by the API scripts when a sub-review fails at the LLM-provider layer.
