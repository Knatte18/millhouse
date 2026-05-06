# Review: 14 (D) — Holistic-fix agent for cross-batch funn (conflicts with 15) — 02-holistic-implement

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-holistic-implement
date: 2026-05-06
```

## Findings

### [BLOCKING] Holistic crash-recovery glob matches no real files
**Step:** Card 6, step 2
**Issue:** The crash-recovery scan specifies `*-code-review-holistic-r{H}.md`, but `write_review_file` in `_review_common.py` produces `{ts}-code-review-r{N}.md` when `scope="holistic"` (the else-branch is taken because `scope != "holistic"` is false). No file written by the review CLI will ever contain the literal substring "holistic" in its name, so the glob silently finds nothing every time and crash-recovery is dead code.
**Fix:** Change the scan pattern to `*-code-review-r{H}.md` — this matches holistic reviews and cannot collide with per-batch reviews (those embed the batch name: `*-code-review-{batch_name}-r{N}.md`).

### [NIT] `_llm_claude` absent from Card 5 Context: list
**Step:** Card 5, Context:
**Issue:** Requirements mention `_llm_claude.LLMError` in step 19 and list `_llm_claude` in the import block, but `_llm_claude` is not in the card's Context: field. The implementer can infer usage from `millpy-implement.py` (which is in Context:), so cold-start risk is low but the completeness criterion is technically violated.
**Fix:** Add `plugins/mill/scripts/_llm_claude.py` to Card 5's Context: list.

### [NIT] Card 6 step 5 APPROVE commit underspecified
**Step:** Card 6, step 5
**Issue:** "Commit status" is ambiguous — the per-batch APPROVE path explicitly commits both `status.md` and the review file (`git add status.md <review_file_path>`), preserving the review in branch history. The holistic APPROVE step omits the review file.
**Fix:** Specify `git -C <worktree> add status.md <holistic-review-file-path> && git -C <worktree> commit -m "mill-go: holistic approved round {H}"`.

## Verdict

REQUEST_CHANGES — one BLOCKING: crash-recovery glob never matches real holistic review filenames.