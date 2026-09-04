The conflict in `/home/knatte/Code/millhouse/wts/plan-validate-batch-index-drift-and-misc-checks/plugins/mill/skills/mill-plan/SKILL.md` has been resolved and staged.

Resolution summary:
- **`context-completeness` row**: combined both sides — kept origin/main's symbol-vs-path branching logic (the `"which resolves to '"` extraction case), and appended this branch's inline-signature escape-hatch sentence at the end. These were non-overlapping extensions of the same row.
- **`requirements-quote-indent-drift` row**: origin/main's copy was the unmodified original (single-direction "strip N" wording only); this branch's rewrite is a strict extension covering both strip and add directions per the task's discussion.md scope, so I kept this branch's version wholesale (nothing from origin/main's copy was lost — it's byte-for-byte preserved as the "stripping" case within the rewritten row).
- **`verify-batch-mismatch` row**: new row only on this branch (the new check from this task), kept as-is.

I checked for moved-duplicate content (`grep` for the new phrases) and found no stray duplicates elsewhere in the file — the `batch-oversized` row's existing reference to the escape hatch is a pre-existing cross-reference from this same branch, not something to deduplicate. Re-read the merged section afterward; no contradictory or stale claims survive.

{"status":"success"}
