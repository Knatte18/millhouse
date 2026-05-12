Now I have sufficient evidence to write the review.

# Review: Replace uv-run-project with direct venv Python in SKILL.md invocations

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: task/discussion.md
date: 2026-05-12
```

## Findings

### [GAP] Nested bg calls cannot use PYTHONPATH= prefix
**Section:** §Decisions — "Source-tree forms stay…"; §Technical context (invocation patterns)
**Issue:** 9 of the 22 mill-go body calls appear after `--` inside `millpy-bg.py` invocations (e.g. lines 87–89, 140–142, 156–158, …). `PYTHONPATH="..." "$MILL_PYTHON"` is a shell env-assignment prefix and cannot appear after `--`: bash passes the literal string `PYTHONPATH=...` as the first argv token to millpy-bg.py, whose worker passes it to `subprocess.run` (without `shell=True`), which tries to exec a binary named `PYTHONPATH=…` — this fails. The outer call sets PYTHONPATH in the process environment, which is inherited through launcher → worker → background subprocess automatically, so the inner calls need no prefix; just `"$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-X.py"` is correct for nested calls.
**Fix:** Add a paragraph distinguishing direct calls (use PYTHONPATH prefix) from nested calls after `--` (omit prefix — inherited from outer shell env); update "All 22 body calls change to `PYTHONPATH=... $MILL_PYTHON ...`" to reflect that the nested form is `"$MILL_PYTHON" "$PLUGIN_ROOT/scripts/..."` without the prefix.

### [GAP] Technical context fallback block is a stale pre-r1 artifact
**Section:** §Technical context — "mill-go PLUGIN_ROOT fallback block (keep `uv run --project`, add comment)"
**Issue:** The block shown (heading: "keep `uv run --project`, add comment"; trailing comment: "subsequent calls use `uv run --project` for the fallback path because the source-tree venv may not exist yet; uv creates it on demand") is the old design that was superseded by the r1 revision. The Decisions section contradicts it: all 22 body calls change, the fallback block sets `MILL_PYTHON`, and the note is an echo inside the `if` rather than a comment after `fi`. A plan writer following Technical context instead of Decisions would implement something different.
**Fix:** Replace the stale Technical context block with the canonical Step 0 block already shown in the Decisions section, or delete the Technical context fallback block entirely and add a cross-reference to the Decisions block.

## Verdict

GAPS_FOUND
Two gaps: nested bg calls must not carry the PYTHONPATH prefix; Technical context fallback block contradicts Decisions.