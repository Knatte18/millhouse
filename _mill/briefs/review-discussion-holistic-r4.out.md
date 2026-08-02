MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] #757 fix routes two of four widened phases to a Resume path that can't locate a batch
**Section:** Decision `757-phase-gate-widening`
**Issue:** `mill-go/SKILL.md`'s `### Resume` section (verified: lines 607-656) locates "the single entry whose state is non-terminal: running, reviewing, or fixing" — but `phase: approved-{batch_name}` (verified appended at line 451/533) occurs *between* batches, when the just-finished batch is `state: approved` and the next is still `state: pending` (per `_status.init_batches`, `_status.py:957`); and `phase: holistic-reviewing` (line 740) occurs *after all* batches are `approved`. In both cases no batch entry is `running`/`reviewing`/`fixing`, so Resume's own batch-locating step 1 has nothing to match — "route to Resume exactly as the existing row does" does not actually work for these two of the four new regex targets.
**Fix:** Either extend `### Resume`'s step 1 to also handle "no non-terminal batch found" (continue the Execute loop from the next `pending` batch; delegate `holistic-reviewing` to the Holistic Code Review's own crash-recovery scan at lines 701-710) or have the plan explicitly scope the regex widening's *destination* per phase value instead of routing all four uniformly to `### Resume`.

### [NOTE] #758's `## Prior failure` section placement is underspecified relative to existing sections
**Section:** Decision `758-mandatory-reason-annotation`, annotation target/format
**Issue:** `plan-batch.md` (verified) already has `## Rename mechanic` and `## Batch Scope` both preceding `## Cards`; "near the top ... before `## Cards`" doesn't say whether `## Prior failure` goes before or after those two existing sections.
**Fix:** Pin the exact insertion point (e.g., "immediately after the frontmatter, before any other section") so repeated self-resolve rounds append predictably.

### [NOTE] #759's exact prose-edit mechanic (replace vs. append) is unstated
**Section:** Decision `759-missing-import`
**Issue:** The target line (verified, `mill-plan/SKILL.md:193`) is a single inline-backtick prose paragraph, not currently in either of the two cited conventions (`signature:` line or fenced-python-snippet); the decision says which *form* to add but not whether the existing paragraph's explanatory prose is kept as-is with a new fenced snippet inserted beside it, or restructured.
**Fix:** State explicitly that the existing paragraph's prose is preserved unchanged and a new fenced `python` snippet (mirroring the `quote_scalar` example) is inserted immediately adjacent to it.

## Verdict
GAPS_FOUND
One GAP: #757's Resume-routing doesn't cover the between-batch/post-batch phase values it widens for.
MILL_REVIEW_END
