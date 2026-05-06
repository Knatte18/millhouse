# Review: 23 (A) — mill infra bugfix-batch — 01-bugfix-batch

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-bugfix-batch
date: 2026-05-06
```

## Findings

### [NIT] Edited file repeated in Context field
**Step:** Cards 2, 3, 4, 5
**Issue:** Each card lists its primary edited file in both `Context:` and `Edits:` (e.g. `millpy-implement.py` in Card 2); convention says edited files are implicitly read and must not appear in `Context:`.
**Fix:** Remove the edited file from each card's `Context:` list; keep only files read but not modified.

### [NIT] Card 5: subprocess mock return value unspecified for existing tests
**Step:** Card 5
**Issue:** "patch subprocess.run to avoid real git calls in those tests" leaves the mock return value open; a `returncode=0` mock would overwrite `commit_sha` in the forwarded JSON, breaking assertions in `test_fo_1`–`test_fo_4` and `test_fo_6`.
**Fix:** Specify that the subprocess.run mock for existing `test_fo_*` tests must return `returncode=1` so original JSON is forwarded unchanged.

### [NIT] Card 4 naming convention mismatch
**Step:** Card 4
**Issue:** Requirements reference "existing sequential-letter naming convention" but `test-status.py` uses flat descriptive `PASS:` print messages in a single `main()`, not the `(a)/(b)/…` letter labels from `test-millpy-bg.py`.
**Fix:** Clarify that new tests follow `test-status.py`'s descriptive-message pattern, not lettered labels.

### [NIT] Card 6 label vs. placement conflict
**Step:** Card 6
**Issue:** "Add test `(m)` after the last existing launcher test `(g)`" would insert `(m)` between `(g)` and `(h)`, producing an out-of-sequence label in the file (a–g, **m**, h–l).
**Fix:** Either place the test physically at the end of `main()` (after `(l)`) to keep labels in order, or clarify that "after (g)" is the intended physical placement despite the label gap.

## Verdict

APPROVE
All findings are NITs; the bug fixes are correctly scoped, requirements are specific, and test coverage addresses both success and failure paths for each change.