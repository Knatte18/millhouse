# Batch: orchestration-skill-doc-fixes

```yaml
task: mill-go/mill-merge-in orchestration robustness gaps, round 2
batch: orchestration-skill-doc-fixes
number: 2
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Two pure documentation fixes, no code: `mill-merge-in/SKILL.md`'s step 4 skip-attribution recompute
(`_mill/discussion.md` Decision `merge-in-skip-attribution-topo-order-dict-mismatch`, #1091) and
`mill-go-base/SKILL.md`'s `TaskOutput`-unavailable fallback wording (Decision
`taskoutput-unavailable-fallback`, #1090). Neither touches the underlying Python — #1091 corrects a
SKILL.md paragraph to match the already-correct `_plan_dag.iter_batch_verifies` reference
implementation; #1090 documents an existing fallback branch's scope, it does not add new mechanics.
Grouped into one batch because both are single-paragraph `SKILL.md` prose edits with no runnable
surface.

## Cards

### Card 5: fix skip-attribution's `topo_order()` dict-index mismatch

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `mill-merge-in/SKILL.md`'s `### 4. Verify` section, the skip-attribution paragraph currently
  reads: "Independently recompute the raw, unfiltered batch-with-verify set: call
  `_plan_dag.extract_batch_index()` on the overview text and `_plan_dag.topo_order()` on the result,
  then for each batch in that order read its frontmatter via `_plan_dag._read_batch_frontmatter()`".
  `_plan_dag.topo_order(batches: list[dict]) -> list[str]` returns batch-name **strings**, not
  dicts, so "for each batch in that order read its frontmatter" (implying indexing a `topo_order()`
  element as a dict, e.g. `b["file"]`) raises `TypeError: string indices must be integers, not
  'str'`. Rewrite the paragraph to mirror the exact pattern `_plan_dag.iter_batch_verifies` already
  uses internally (`_plan_dag.py`, the block starting `batches = extract_batch_index(...)`, `order =
  topo_order(batches)`, `file_by_name = {entry["name"]: entry.get("file") for entry in batches}`):
  "Independently recompute the raw, unfiltered batch-with-verify set: call
  `_plan_dag.extract_batch_index()` on the overview text to get the raw batch dicts, call
  `_plan_dag.topo_order()` on that same list to get the ordering (a list of batch-name strings, not
  dicts), build `file_by_name = {entry['name']: entry.get('file') for entry in batches}` from the raw
  batch dicts, then for each `name` in `topo_order`'s ordering resolve `batch_path = plan_dir /
  file_by_name[name]` and read its frontmatter via `_plan_dag._read_batch_frontmatter(batch_path)` —
  this is the identical pattern `_plan_dag.iter_batch_verifies` already uses, cited here rather than
  reinvented." Leave the rest of the paragraph (normalizing `verify:` via `parse_verify_field`,
  collecting non-`None` command names) unchanged.
- **Commit:** `docs(mill-merge-in): fix skip-attribution's topo_order() dict-index mismatch (#1091)`

### Card 6: document the `TaskOutput`-unavailable fallback

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  `mill-go-base/SKILL.md` has four occurrences of a `TaskOutput(task_id: <agentId>, block: false)`
  probe each followed by an "or the probe call itself errors: proceed to <some branch> exactly as
  documented" fallback clause — confirmed by reading the whole file, not just "## Agent-mode
  dispatch" step 3: (1) step 3(b), the implementer's stopped/interrupted probe ("... If it reports
  the agent is no longer running, or the probe call itself errors: proceed to Clean mid-work stop
  below exactly as documented."); (2) step 3(c), the reviewer/fixer probe ("... or the probe call
  itself errors: proceed to the existing one-retry transient classification from (a)"); (3) step
  5.5's "Warm `SendMessage` resume" liveness probe ("If the probe reports the agent is no longer
  running, or the probe call itself errors: proceed as documented below."); (4) step 5.5's
  "`--resume-incomplete` fallback" defensive re-check ("If it reports the agent is no longer
  running, or the probe call itself errors: proceed with the `--resume-incomplete` dispatch exactly
  as documented below."). Add one sentence immediately after each of these four "or the probe call
  itself errors" clauses: "This includes the case where `TaskOutput` is not a callable tool in this
  host at all (confirmed via `ToolSearch(\"select:TaskOutput\")` returning no match, or an immediate
  \"unknown tool\" failure on the call itself) — treat that identically to a runtime probe error and
  proceed to the same branch; do not attempt to invent a replacement liveness check." Do not change
  any of the four branches' actual behavior — this documents an existing fallback's scope at every
  site sharing the same phrase, it does not add a new mechanism.
- **Commit:** `docs(mill-go-base): document the TaskOutput-unavailable fallback (#1090)`

## Batch Tests

Pure documentation batch, no runnable surface — `verify: null`. Self-check: after editing, re-read
`mill-merge-in/SKILL.md`'s step 4 paragraph and confirm it names `iter_batch_verifies`'s own three
variables (`batches`, `order`, `file_by_name`) in the same shape that function already uses, and
re-read all four edited sites in `mill-go-base/SKILL.md` (step 3(b), step 3(c), and step 5.5's two
probes) to confirm the new sentence appears immediately after each of the four existing "or the
probe call itself errors" clauses, not just the two in step 3.
