# Discussion: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution

```yaml
task: mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution
slug: mill-merge-and-merge-in-bugs
status: discussing
parent: main
```

## Problem

`mill-merge` and `mill-merge-in` have four independent bugs, each filed as a GitHub issue (#824, #819, #817, #816) and bundled into this one task. Three are latent correctness bugs in the merge/merge-in machinery that surface only in specific git-state edge cases (non-linear parent history, a torn-down or never-pushed parent branch, a semantically-inconsistent conflict resolution); one is a documentation/behavior mismatch that misleads whoever next reads the SKILL. None of the four share a root cause — they're grouped because they all live in the merge path and were reported around the same time.

## Scope

**In:**
- #824: fix the squash-push non-fast-forward rejection at `mill-merge/SKILL.md` Step 5, by fast-forwarding the parent worktree's local branch to `origin/<parent_branch>` immediately before the squash (only when `mode == 'worktree'`; the pre-squash dirty-check at `SKILL.md:243` already gates this to worktree mode and confirms the worktree is clean first).
- #824 (second-order bug, same area): fix the Steps 1-5 rollback (`SKILL.md:421-424`) to reset the parent worktree to `origin/<parent_branch>` instead of the child's `mill-checkpoint-<name>` ref — the current ref is a child-worktree checkpoint and applying it to the parent checks the parent out to unrelated child history.
- #819: narrow the stale-worktree entry gate (`SKILL.md:29-39`) so the disambiguation procedure — including its `status.md` write/commit/push side effects at lines 38-39 — only runs when there's genuine ambiguity (an `_inplace.is_inplace()` result that's itself suspect, or a `git worktree list --porcelain` entry for `<slug>` that's stale/absent/branch-mismatched), instead of on every normal invocation.
- #817: add dead-parent-branch detection at `mill-merge`/`mill-merge-in`'s parent-resolution step. Covers both facets reported (parent branch never pushed to origin, and parent branch already merged-and-torn-down) via one liveness check: verify `parent_branch` exists in `git branch -a` / `git worktree list`; if not, derive the parent's slug from its branch name using `cfg.spawn.branch_prefix` (`removeprefix`, same pattern `_marker.py:87` already uses) and check for an `archive/<slug>` tag (`_archive_tag.py`); if found, walk that task's own former parent (or fall back to `cfg.git.base_branch` if none); halt with an actionable message and require operator confirmation before rebinding `status.md`'s `parent:` field.
- #816: add a required self-verification instruction to `templates/merge-in-conflict-brief.md` — after resolving conflicts (step 7, before the Report section), the sub-agent must re-read each resolved file and explicitly confirm no contradictory losing-side claims survive, before emitting `{"status":"success"}`.
- Integration tests (`plugins/mill/integration_tests/`) for the three git-plumbing fixes: #824 parent-ff, #824 rollback-ref, #817 dead-parent detection.

**Out:**
- A second independent LLM consistency-checker pass for conflict resolution (#816 fix-option 2) — deferred; only added later if the prompt-level self-verification proves insufficient.
- Model-tier bumping for prose-heavy conflicts (#816 fix-option 3) — orthogonal, not pursued now.
- Broadening Step 5's push-failure classification to catch plain non-ff as a *second*, independent recovery path (#824 fix-option 2) — the pre-squash fast-forward (option 1) prevents the failure outright, making a reactive classification-based recovery redundant for this specific race. Not ruled out forever, just not needed to close these issues.
- Any change to `_parent_branch.resolve()`'s core lookup order (status.md → interactive prompt) — the fix adds a liveness *check* on top of the existing resolution, it doesn't change how the parent branch name itself is looked up.
- Automated tests for #819 and #816 — both are non-executable (SKILL.md prose, prompt text); verified by review, not test.

## Decisions

### 824-parent-fast-forward

- Decision: before Step 5's `merge --squash`, when `mode == 'worktree'`, fast-forward the parent worktree's local branch to `origin/<parent_branch>` (fetch + reset, or fetch + FF-only merge) immediately after the existing dirty-check confirms the parent worktree is clean.
- Rationale: the actual root cause is that mill-merge-in only advances the *child* branch to `origin/<parent_branch>`, never the parent worktree's own local ref — so Step 5's squash-then-push runs against a stale parent ref whenever `origin/<parent_branch>` moved after the child last synced. This is a race, not specifically "non-linear history" (a linear fast-forward-only advance on origin triggers it just as easily as a merge commit does) — the wiki brief's framing is imprecise but the underlying bug and fix are as described here.
- Rejected: reactive push-failure-classification + retry (catches the symptom after a failed push instead of avoiding it); leaving the race and fixing only the rollback ref (treats the second-order bug but not the root cause).

### 824-rollback-ref

- Decision: fix the Steps 1-5 rollback (`SKILL.md:421-424`) to `git -C <parent-path> reset --hard origin/<parent_branch>` instead of `mill-checkpoint-<name>`.
- Rationale: `mill-checkpoint-<name>` is created in the *child* worktree by mill-merge-in and points at child pre-merge-in history; applying it to the parent worktree checks the parent out to unrelated commits — actively destructive, independent of which trigger caused the rollback to fire.
- Rejected: leaving it as-is on the assumption the 824-parent-fast-forward fix makes this path rare — the ref is wrong for *any* Steps 1-5 failure, not just the non-ff one, so it stays broken for other trigger paths.

### 819-stale-worktree-gate

- Decision: narrow the entry gate at `SKILL.md:29-39` to only run the full disambiguation procedure (and its status.md write/commit/push) when `_inplace.is_inplace()`'s result is itself suspect, or the `git worktree list --porcelain` entry for `<slug>` is stale/absent/branch-mismatched.
- Rationale: today's three listed conditions are true on essentially every normal worktree-mode run, so the procedure — including side effects — fires unconditionally despite being framed as edge-case handling. The reporter's complaint about misleading wording is really pointing at unnecessary side effects on the common path; narrowing the gate fixes the underlying defect, not just the prose describing it.
- Rejected: doc-only fix (clarify wording, leave gate/side-effects unchanged) — technically lower-risk but leaves the actual defect (redundant git operations + status.md churn on every invocation) in place.

### 817-dead-parent-detection

- Decision: add a parent-branch liveness check at the point mill-merge/mill-merge-in resolve `parent_branch` (wrapping/extending the existing `_parent_branch.resolve()` call site, not its internals). On a dead parent, attempt to resolve a successor via the `archive/<slug>` tag chain (deriving slug from branch name via `cfg.spawn.branch_prefix`); otherwise fall back to `cfg.git.base_branch`; halt for operator confirmation before rebinding `status.md`.
- Rationale: the wiki brief ("never pushed") and the actual GH issue title ("merged and torn down") describe two shapes of the same problem — a `parent_branch` that `resolve()` returns unvalidated, which currently only fails opaquely at the worktree-lookup step. One liveness check at one location naturally covers both shapes.
- Rejected: scoping narrowly to only the "merged and torn down" case from the issue title — would require revisiting this same code path again for the "never pushed" shape with no real savings now.
- Rejected: auto-rebinding `status.md` without operator confirmation — faster but risks silently merging against the wrong base if the archive-chain walk has an edge case; the wiki task's own history is not something to silently rewrite.

### 816-conflict-self-verification

- Decision: add a required self-verification instruction to `templates/merge-in-conflict-brief.md`, after step 7 and before the Report section — the sub-agent re-reads each resolved file and confirms no contradictory losing-side content survives before reporting `{"status":"success"}`.
- Rationale: `_verify_conflict_markers` (`millpy-merge-in-subagent.py:119-196`) only checks for staged conflict markers and unmerged paths — purely mechanical, no semantic check. The template's step 3 ("combine both edits" for disjoint regions) is exactly where self-contradiction risk lives, and there's currently no instruction requiring the agent to re-read its own combined output for coherence. This matches the original reporter's own suggested fix.
- Rejected: a second independent LLM consistency-checker pass (more robust, but adds cost/latency to every conflict — deferred as a backstop if the prompt-level fix proves insufficient); model-tier bump for prose conflicts (orthogonal, needs new classification logic, not needed to close this issue).

### testing-approach

- Decision: add/extend `plugins/mill/integration_tests/` coverage for the three git-plumbing fixes (824-parent-fast-forward, 824-rollback-ref, 817-dead-parent-detection) using real git repos per existing integration-test convention. 819 and 816 get no automated test.
- Rationale: the git-plumbing fixes have subtle non-ff/rollback/liveness semantics that integration tests are the existing mechanism for protecting. 819 is a SKILL.md prose/gate-condition change and 816 is prompt text — neither has executable logic an automated test could assert against beyond what a reviewer already checks by reading the rendered template/gate condition.
- Rejected: manual-only verification for the plumbing fixes — too easy to regress silently given no other test currently exercises these git-state edge cases.

## Technical context

- `mill-merge/SKILL.md` — Entry Steps 1-5 resolve `mode` (`inplace` vs `worktree`) via `_inplace.is_inplace()` and `git worktree list --porcelain`; Step 5 ("Direct squash", `SKILL.md:230+`) does the squash/commit/push against `<parent-path>` (worktree mode) or the current tree in-place. The pre-squash dirty-check (`SKILL.md:243-250`) already gates on `mode == 'worktree'` — the new parent-fast-forward step should sit right after that check, same gate.
- `mill-merge-in/SKILL.md` syncs the *child* branch from `origin/<parent_branch>` (the no-op check around `SKILL.md:25-39` in that file) — it never touches the parent worktree's own local ref, which is the root of #824.
- `_parent_branch.py` — `resolve(status_path, *, interactive=True, expected_slug=None)` reads `status.md`'s `parent:` row (or prompts) with zero liveness validation of the returned branch name. The new #817 check wraps this call site, not the function itself.
- `_marker.py:77-87` already derives slug from branch name via `cfg.get("spawn", {}).get("branch_prefix", "")` + `branch.removeprefix(prefix)` — reuse this pattern for the archive-tag slug lookup in #817's fix rather than reimplementing it.
- `_archive_tag.py` creates tags named `archive/<slug>` (or `archive/<slug>-NN` on collision, `_archive_tag.py:131-151`) — the #817 chain-walk needs to handle the `-NN` suffix form too when scanning for a match.
- `mill-config.yaml`: `spawn.branch_prefix: hanf/` (this repo's convention).
- `millpy-merge-in-subagent.py:119-196` (`_verify_conflict_markers`) is the mechanical post-resolution gate for #816 — called from `_run_conflicts` (~line 485) and the finalize path (~line 414). The semantic self-verification instruction is a template change, not a code change to this gate.
- `templates/merge-in-conflict-brief.md` — step 3 ("combine both edits" for disjoint-region conflicts) is where #816's self-contradiction risk originates; the new self-verification instruction belongs after step 7, before the `## Report` section.
- Rollback section: `## Rollback (Steps 1-5 only)` in `mill-merge/SKILL.md` (~lines 419-440) documents the current (buggy) `mill-checkpoint-<name>` reset and the "Dirty-parent-worktree halt" exemption — the #824 rollback-ref fix only changes the reset target, not the exemption logic.

## Constraints

None beyond the existing repo conventions already enforced by CLAUDE.md (no `sed`, ASCII-only `print()`/`_log()` output, `PYTHONPATH=` prefix on Python verify commands, no inline path construction outside `_paths.py`).

## Testing

- **824-parent-fast-forward / 824-rollback-ref**: integration test in `plugins/mill/integration_tests/` that constructs a real parent+child worktree pair, advances `origin/<parent>` past the parent worktree's local ref (simulating another thread's concurrent squash-merge), then runs mill-merge's Step 5 flow and asserts the push succeeds without hitting the rollback path. A second case forces a Step 1-5 failure and asserts the rollback correctly restores the parent worktree to `origin/<parent_branch>`, not to unrelated child history.
- **817-dead-parent-detection**: integration test covering both reported shapes — (a) `parent:` branch that was squash-merged and torn down (archive tag present, chain-walk resolves), and (b) `parent:` branch that was never pushed to origin (no archive tag, falls back to `cfg.git.base_branch`) — asserting the halt-and-confirm behavior in both cases rather than an opaque worktree-lookup failure.
- **819**: no automated test; verified by re-reading the narrowed entry gate against the three original conditions plus the two added suspect-determination conditions.
- **816**: no automated test; verified by reading the updated `merge-in-conflict-brief.md` for the added self-verification instruction placement and wording.
- TDD candidates: 824-parent-fast-forward and 817-dead-parent-detection are the two most amenable to write-test-first, since both are pure git-state assertions with a clear pass/fail boundary independent of LLM output.

## Q&A log

- **Q:** How should the #824 non-ff push rejection be fixed? **A:** [auto-pick] Fast-forward the parent worktree's local branch to `origin/<parent_branch>` before Step 5's squash. **Why:** prevents the race outright rather than reacting to a failed push; the pre-squash dirty-check already gates this to worktree mode and confirms cleanliness first.
- **Q:** Should the Steps 1-5 rollback's use of the child's `mill-checkpoint-<name>` ref (destructive when applied to the parent) be fixed as part of this task? **A:** [auto-pick] Yes — reset to `origin/<parent_branch>` instead, regardless of the #824 root-cause fix. **Why:** it's actively destructive today and independent of the #824 fix — any other Steps 1-5 failure still hits this broken rollback.
- **Q:** Should #819's fix narrow the stale-worktree entry gate's actual conditions, or just clarify the prose? **A:** [auto-pick] Narrow the gate conditions. **Why:** the real defect is unconditional side effects (status.md write/commit/push) on every normal run, not just misleading wording — fixing only the prose leaves the defect in place.
- **Q:** Should #817's fix cover only the "merged and torn down" case from the actual GH issue title, or the broader "dead parent branch" problem (also covering "never pushed", per the wiki brief's framing)? **A:** [auto-pick] Cover both via one liveness check. **Why:** both are the same underlying defect (`_parent_branch.resolve()` returns an unvalidated branch name) surfacing two ways; one check at one call site naturally covers both, and splitting them would mean revisiting the same code path twice for no benefit.
- **Q:** Should #816 be fixed with a prompt-level self-verification instruction, a second independent LLM consistency-checker pass, or a model-tier bump for prose conflicts? **A:** [auto-pick] Prompt-level self-verification instruction only. **Why:** cheapest fix directly matching the original reporter's own suggestion; a second-pass checker or tier bump can be added later as a backstop if this proves insufficient — no need to over-engineer now.
- **Q:** What's the testing approach for these four fixes? **A:** [auto-pick] Integration tests (real git repos, existing `plugins/mill/integration_tests/` convention) for the three git-plumbing fixes (824-parent-fast-forward, 824-rollback-ref, 817-dead-parent-detection); review-only for 819 (SKILL.md prose/gate) and 816 (prompt text), since neither has executable logic to assert against. **Why:** the plumbing fixes touch subtle non-ff/rollback/liveness git-state semantics that are exactly what integration tests exist to protect; the other two are inherently non-executable changes.
