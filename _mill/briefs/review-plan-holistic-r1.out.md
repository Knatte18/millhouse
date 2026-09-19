MILL_REVIEW_BEGIN
# Review: mill-finalize/mill-merge-in citation-scan pathspec `:!_mill` fails on git 2.53+ — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-19
```

## Findings

None.

Verified against source: the exact byte-for-byte substring Card 1 targets matches `plugins/mill/skills/mill-finalize/SKILL.md` lines 86-87 (indentation included), and Card 2's target matches `plugins/mill/skills/mill-merge/SKILL.md` lines 286-287 identically. A repo-wide grep for `':!` confirms these are the only two occurrences in `plugins/` — the "scope excludes mill-merge-in" Decision is correct: `plugins/mill/skills/mill-merge-in/SKILL.md` contains no citation-scan step and no `:!` pathspec anywhere. Batch Index DAG is a single valid node (no cycle, file present, no forward deps). Both cards have all required fields, `Moves: none` is bare and valid, no `## Rename mechanic` section is correctly omitted since neither card has a Move. `Context: none` is consistent with the Edits-implicitly-read convention and Requirements name no symbol from an unlisted file. `## All Files Touched` matches the union of both cards' `Edits:`. The batch `verify:` and overview Batch Index `verify:` are identical and both start with the required `PYTHONPATH= ` prefix; the module-wide overview `verify:` is `null`, so the full-suite-verify rule does not apply. Batch Tests' rationale for using `'.'` instead of the citation pattern itself, and for testing `_mill` instead of `<task_dir>`, is sound and correctly scoped to "does this pathspec list parse," independent of the git-2.53 external-tool behavior claim (which rests on a stated local repro, not a production-code mechanism claim).

## Verdict

APPROVE
Plan is complete, correctly scoped, and its substitution targets verified byte-for-byte against both source files.
MILL_REVIEW_END
