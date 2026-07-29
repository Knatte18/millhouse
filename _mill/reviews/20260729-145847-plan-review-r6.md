MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not directly knowable)
reviewed_file: plan/
date: 2026-07-29
```

## Findings

None. Cross-checked every cited line number, function signature, and docstring claim against the actual source files (`wiki/_sync.py`, `wiki/_server.py`, `wiki/_client.py`, `_paths.py`, `_worktree.py`, `_subprocess_util.py`, `_junction.py`, `_pygit2_util.py`, `_status.py`, `millpy-implement.py`, `millpy-abandon.py`, `millpy-validate-plan.py`, `millpy-fix.py`, `millpy-merge-in-subagent.py`, `_review_common.py`, `_plan_validate.py`, `mill-resume/SKILL.md`, `test-wiki-sync.py`, `_test_helpers.py`, `test-fold.py`, `test-worktree.py`, `run-all.py`'s `SKIP` set) — all matched exactly, including the more unusual claims (e.g. `SKIP = frozenset({"test-wiki-sync.py"})`, `_junction.create`'s `ValueError`-on-existing-link_path guard, `_subprocess_util.run`'s `cwd=None` inherits-caller-cwd docstring, `find_active_slug`'s `hub_root` first-param name, `_check_verify_not_isolated`'s `project_root` doubling-for-`hub_root` docstring at `_plan_validate.py:1455`).

Batch Index DAG is acyclic, all four `file:` entries exist, all `depends-on: []` are consistent with the batches' genuine file-independence. Global card numbering (1-16) is sequential with no gaps across all four batches. `## All Files Touched` is an exact match for the union of `Edits:`/`Creates:` targets across all 16 cards (no `Moves:` anywhere in this plan, so the Rename-mechanic criterion is correctly inapplicable). All `verify:` commands (overview + all 4 batches) carry the mandatory `PYTHONPATH= ` prefix per the Shared Decision. ASCII-only stdout/stderr decision is honored in every new `print(...)`/SKILL.md message cited (`--` for em-dash, no Unicode arrows). Requirements throughout name exact function/line identifiers rather than vague prose, and every function/class referenced in a card's `Requirements:` is present in that card's own `Context:`/`Edits:` list.

Verified the two most intricate cross-cutting design points end to end against source:
- Batch 1 Card 2's `liveness_only` early-return ordering (checked *before* the `WIKI_DAEMON_SKIP_GIT` gate) is necessary and correctly reasoned: `_client.py:643`'s reuse-probe payload (Card 3's fix) hits `_handle_health` on every dispatched op with a hardcoded 1.0s timeout, and Card 4's test (f) exercises exactly this path.
- Batches 3/4's `cfg`-reload-after-`resolve_active_hub()` fix is correctly scoped per file: verified the exact downstream `cfg` read line numbers in `millpy-implement.py` (287, 324-338), `millpy-fix.py` (340, 342, 343, 359, 378, 628), and `millpy-abandon.py` (75, 114) all sit after the cards' prescribed reload insertion points.

## Verdict

APPROVE
Plan is internally consistent, DAG-valid, and every source-grounded claim checked out against the actual codebase.
MILL_REVIEW_END
