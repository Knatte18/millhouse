# Review: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8) — 02-tests-and-skill

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-tests-and-skill
date: 2026-05-05
```

## Findings

### [BLOCKING] Tests 5 and 5b omit --round from --resume invocation
**Step:** Card 4, Test 5 and Test 5b
**Issue:** Both tests call `main(["test-batch", "--resume", "--review-file", str(review_file)])` without `--round`. Edit 2 of Card 5 specifies the resume invocation as `--resume --round <N> --review-file <path>`, implying `--round` is part of the required resume interface. If batch 01 implements `--round` as required (consistent with the CLI spec), `argparse` will exit with code 2 (not 1) and produce no JSON on stdout — the assertions `exit code 1` and `stdout JSON has "stuck_type": "transient"` both fail for the wrong reason, masking the LLM-error handling they are meant to cover.
**Fix:** Add `"--round", "1"` to the `main(...)` argv in both Test 5 and Test 5b.

### [NIT] `### 2. Parse implementer report` not updated to match CLI retry
**Step:** Card 5, Edit 5 (Stuck escalation) / Plan section `### 2. Parse implementer report`
**Issue:** After Edit 5, Stuck escalation says "re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag". But `### 2.` still says "retry once with a fresh session (new UUID, `resume=False`)" — language that implies the Builder calls `_implementer_sonnet.run` directly. The two sections describe the same retry but in incompatible terms; a Builder reading `### 2.` in isolation would attempt a direct helper call the CLI now owns.
**Fix:** Update the transient bullet in `### 2.` to say "re-invoke the CLI without `--resume`" instead of "new UUID, `resume=False`".

## Verdict

REQUEST_CHANGES
Tests 5/5b will fail at argparse (exit 2, no JSON) rather than testing the LLM-error path they are meant to cover.