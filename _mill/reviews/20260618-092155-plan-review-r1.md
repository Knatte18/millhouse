All context files are valid and the referenced helpers exist.

Now let me consider the verify-command-shape constraint from CLAUDE.md. The batch verifies use `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/...`. CLAUDE.md says verify commands for Python projects must start with `PYTHONPATH=` (literal empty), and unit tests use `uv run --project plugins/mill`. These verifies start with `PYTHONPATH=` and use `uv run --project plugins/mill` — compliant.

One more check: Card 1 says follow `test-parent-branch.py` shape, computing `HUB = Path(__file__).resolve().parent.parent.parent.parent`. test-parent-branch.py uses exactly 4 `.parent` (line 8). The card says "mirror test-parent-branch.py's HUB/SCRIPTS derivation" — correct. But note test-parent-branch.py derives `SCRIPTS` inline via `HUB / "plugins" / "mill" / "scripts"`; the card explicitly states the same. Good.

I have enough to render the verdict. The plan is well-grounded, DAG is valid, all helpers exist, regression-lock substrings match source exactly, decisions are faithfully implemented. The minor items (load_config second-arg nuance, the `_archive_tag` phrasing) are not blocking.

MILL_REVIEW_BEGIN
# Review: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-18
```

## Findings

### [NIT] load_config second-arg semantics vs mill-go's pattern
**Location:** Batch 2 / Card 3
**Issue:** Card 3 uses `_config.load_config(_paths.resolve_hub_path(), git_root)`; `_config.load_config(hub_root, worktree_root)` reads the local stub from arg2's `.millhouse/`. mill-go/`_review_common` instead source cfg from `hub/.millhouse` (see `_review_common.py:313-317` note: mill-claim writes the stub only at the hub in in-place mode).
**Fix:** Acceptable as written since hub-level `mill-config.yaml` (read from arg1) supplies the keys mill-merge consumes; the Decision explicitly sanctions it. No change required — flagged only so the implementer does not "correct" arg2 to `hub/.millhouse` mid-stream.

### [NIT] Card 7 assertion (c) cites a non-existent `_archive_tag` helper in the test
**Location:** Batch 3 / Card 7
**Issue:** Card phrases the archive-tag step as "reuse the same `_archive_tag`/git approach the existing flat scenario uses," but the existing flat scenario uses raw `git tag archive/<slug>` (test-merge.py:291), not an `_archive_tag` helper.
**Fix:** Treat the phrasing as "reuse the existing raw `git tag` approach"; the implementer is already pointed at the correct existing pattern, so no behavioral change.

## Verdict

APPROVE
Source-grounded, DAG valid, helpers/substrings verified; two cosmetic phrasing nits only.
MILL_REVIEW_END