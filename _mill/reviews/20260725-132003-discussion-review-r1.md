MILL_REVIEW_BEGIN
# Review: mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] #680 Resume premise contradicts current mill-go/SKILL.md dispatch routing
**Section:** Decision "mill-go Resume: preserve start_sha, route through resolve_dispatch_mode"
**Issue:** `mill-go/SKILL.md`'s Resume `running`-case (lines 512-525) already branches on dispatch mode: `dispatch == agent` already re-runs the Agent-mode dispatch pattern (`--stage prepare`), and `millpy-implement.py`'s existing `_prepare_reuse_entry` branch (lines 439-450, 487-494) already preserves `start_sha`/`session_id` on a `--stage prepare` re-run against a `running` batch. Only the `subprocess`/`psmux` bare `--stage full` call (SKILL.md lines 520-524) hits the fresh-mint branch (`millpy-implement.py:495-516`) and discards `start_sha`. So the claimed #672-guard/#680 interdependency (guard fires when resolved stage is `full` AND dispatch is `agent`) doesn't arise on either of Resume's actual current paths — agent-mode Resume never reaches `--stage full`, and the bare/full-stage call never runs under `dispatch == agent`.
**Fix:** Re-verify the "hardcoded bare/full-stage call under agent-mode" claim against current source before planning; re-scope the decision to the real remaining gap (subprocess/psmux resume's fresh-mint branch discarding `start_sha` since `_prepare_reuse_entry` requires `args.stage == "prepare"`), and drop or re-justify the #672/#680 landing-together sequencing constraint.

### [GAP] briefs_dir fix assumes slug/container_path already in scope; false for at least one site
**Section:** Decision "briefs_dir call sites routed through resolve_active_hub"
**Issue:** `resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` requires both `container_path` and `slug`. None of the 6 affected files currently compute `container_path` (no `resolve_container_path` call in any of them). In `millpy-merge-in-subagent.py` specifically, `_marker.slug_from_branch(git_root, wiki_path, cfg)` (line 264) is called but its return value is discarded — no `slug` variable exists at that file's 3 briefs_dir sites (347/393/428), contradicting the rationale's "already have a slug in scope."
**Fix:** State explicitly that `millpy-merge-in-subagent.py` needs a captured `slug = _marker.slug_from_branch(...)`, and all 6 files need a new `container_path = _paths.resolve_container_path(git_root)` binding, before the `resolve_active_hub` call can be made.

### [NOTE] Merged find_active_slug/load_task_title API shape unspecified
**Section:** Decision "On-disk-first slug/title resolution"
**Issue:** `load_task_title` is currently called from `prepare()` in `_review_code.py`/`_review_plan.py`/`_review_discussion.py`, a different function/file than where `find_active_slug` resolves `slug` (each CLI's `main()`) — so "merge the two functions" doesn't correspond to one existing call site today.
**Fix:** Note in Technical Context that slug/title resolution currently span a function/file boundary, so the plan needs to define how a resolved title threads from `main()` into `prepare()`.

## Verdict

GAPS_FOUND
Resume decision's #672 interdependency and briefs_dir's "already in scope" premise both conflict with current source.
MILL_REVIEW_END
