I now have a complete picture. The discussion is well-grounded; all "exact current state" claims match source.

One feasibility nuance worth surfacing for #470: `resolve_main_worktree_root` returns the **main worktree** (i.e. `<container>/wts/<repo>` in container-form), so the primary clone's `mill-config.yaml` is simply `resolve_main_worktree_root(worktree_root) / "mill-config.yaml"` — not a hand-rolled `<container>/wts/<repo>` join. The discussion's step (2) describes "derive container via `resolve_container_path`; repo via the main worktree name," which would reconstruct the same path more circuitously and risks a hand-rolled join that the constraints forbid. This is a NOTE-level clarification, not a blocker.

Let me assess remaining criteria and compose the review. The discussion has explicit decisions with rationale + rejected alternatives for all six fixes, clear scope in/out, constraint coverage, failure modes (idempotency, non-git wiki, untracked branch, stacked base), and a testing strategy per fix. The auto-picks in the Q&A log are consistent with the Decisions.

MILL_REVIEW_BEGIN
# Review: Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-15
```

The discussion is thorough and source-grounded. I verified every "exact current state" claim against the files: bare `git push` at `_sync.py:231`, silent repo-config skip at `_config.py:196-199` via `resolve_mill_config_path`, U+2014 em dash at `_review_common.py:1241`, blanket gate at `mill-go/SKILL.md:650`, unconditional `git rm -r` at `mill-finalize/SKILL.md:58`, literal `$GIT_ROOT/_mill/status.md` at `git-pr/SKILL.md:40`, and the already-correct `_server.py` mapping (`WikiPushError → ERR_PUSH_FAILED`, `ERR_NOT_FOUND` only on `get_task is None`). All claims hold. Each of the six fixes has a `### Decision:` with rationale + rejected alternatives, scope is cleanly partitioned in/out, constraints are acknowledged (ASCII output, `_paths` helpers, no wiki-cd, `resolve_mill_config_path` contract preserved, `PYTHONPATH=` verify prefix, no silent layer drop), and failure modes (idempotent re-run, non-git wiki, untracked-default-branch clone, stacked base) plus per-fix tests are specified. Two non-blocking NOTEs below.

## Findings

### [NOTE] #470 container-clone path may invite hand-rolled join
**Section:** Decisions §470-resolve-repo-config-from-clone, step (2)
**Issue:** "derive container via `resolve_container_path`; repo via the main worktree name" reconstructs `<container>/wts/<repo>` circuitously; `resolve_main_worktree_root(worktree_root)` already returns exactly that dir, and the verbose phrasing risks a hand-rolled `container/"wts"/repo` join the constraints forbid.
**Fix:** State the primary-clone path as `resolve_main_worktree_root(worktree_root) / "mill-config.yaml"` so the plan writer avoids reassembling the path manually.

### [NOTE] #469 setup-tracking via "git config" vs "--set-upstream" left as either/or
**Section:** Decisions §469-explicit-refspec-push
**Issue:** The setup-path defence offers two interchangeable mechanisms ("`git config branch.<b>.remote/.merge`, or push `--set-upstream` on first push") without picking one; the orphan path already uses the `git config` form (`_setup.py:175-189`).
**Fix:** Pin the `git config branch.<b>.remote/.merge` form for the plain-clone paths to match the existing orphan-path convention and keep setup deterministic.

## Verdict

APPROVE
Source-grounded, all decisions resolved with rationale; two minor clarifications only.
MILL_REVIEW_END