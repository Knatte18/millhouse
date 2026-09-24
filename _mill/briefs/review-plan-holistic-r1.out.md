MILL_REVIEW_BEGIN
# Review: status.md: rename parent to parent_branch, add parent_thread — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-24
```

## Findings

None.

Verified against source, not inferred:

- Card 1 (`_status.py`): current `render_initial` signature and docstring, `status-discussing.md`'s `parent: <PARENT_BRANCH>` row, and every cited `test-status.py` assertion (`"parent: main" in out`, `assert "parent" in r["yaml"]`, `result["parent"]`) match the plan's before-state exactly.
- Card 2/3 (`_status.py`): `update_field`'s line-scan pattern (the model for `set_parent_branch`) and `set_module_verify_baseline`/`_signatures`'s current "insert after `parent:`" scan (the code `_baseline_anchor_index` replaces) match the plan's description line-for-line.
- Card 4 (`_parent_branch.py`): `_parse_parent_from_yaml_text`, `resolve`, `resolve_dead_parent` and both `"No parent:"` test assertions match.
- Cards 5-7 (`_spawn_core.py`, `millpy-spawn.py`): `write_initial_status`/`render_initial` call sites, the `args = parser.parse_args(argv)` / `resolve_git_root()` insertion point, and `--dry-run` block all confirmed.
- Cards 9-10 (skills): every quoted skill sentence and `_status.update_field(status_path, "parent"/"parent_branch", ...)` call site cited in `mill-merge`, `mill-merge-in`, `mill-go-base/SKILL.md`+`handoff.md`, `mill-finalize`, `mill-start` was located verbatim at the plan's stated location.
- Card 12 (`test-merge.py`): the 8 hand-written `parent:` fixtures were individually located and the migrate/keep-legacy split (3 migrate, 5 keep for fallback coverage) is exhaustive and correct against the actual fixture set.

Batch Index DAG is acyclic, batch dependencies (`[1]`, `[1]`) have no forward refs, global step numbering is 1-12 with no gaps, `## All Files Touched` is the exact union of Edits/Creates across all 12 cards, and every `Moves:`/`Deletes:` is `none` (no Rename mechanic section required). Shared Decisions (`legacy-parent-fallback-is-permanent`, `parent-thread-is-write-only`, `fixture-migration-policy`, `integration-tests-excluded-from-verify`, `done-gate-recommendation`) are faithfully carried into the cards that apply to them; `parent-thread-is-write-only` is honored (no reader added, `millpy-claim.py` untouched).

## Verdict

APPROVE
Every card's Requirements are precisely grounded in current source; no design, scope, decision, or consistency gaps found.
MILL_REVIEW_END
