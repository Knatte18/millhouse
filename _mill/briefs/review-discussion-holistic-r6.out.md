MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact minor version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [BLOCKING:design] `blocked_resume_round` binds `reviews_dir` before it exists
**Section:** revise-blocked-resume (#852), "On the `blocked` branch" step 4. **Issue:** Step 4 binds `blocked_resume_round = _review_common.discover_round(reviews_dir, "plan", "holistic")` inside Entry step 4's pre-check, but `mill-plan/SKILL.md`'s own "Path Setup" (Entry) section states verbatim that `reviews_dir` "will be derived during Phase: Plan (writes) or Phase: Plan Review (reads)" — i.e. not yet bound at Entry step 4. Step 5 ("fall through into Phase: Plan Review") is listed *after* step 4, so the numbered ordering has step 4 reading a variable the file's own architecture says doesn't exist until Phase: Plan Review's own Path Setup runs. **Fix:** state explicitly whether Entry step 4 independently re-derives `reviews_dir = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])` (duplicating Phase: Plan Review Path Setup's derivation), or whether `blocked_resume_round`'s computation is instead deferred to Phase: Plan Review's own Path Setup (immediately after `reviews_dir` is bound there, before applying the `revise_requested and not revise_from_blocked` namespacing branch) — currently neither is said, and the ordering in the Decision implies the former without saying so.

### [NIT:consistency] `git add <plan_dir>` on the blocked-resume commit is a no-op
**Section:** revise-blocked-resume (#852), "On the `blocked` branch" step 3. **Issue:** The blocked branch's commit stages `<plan_dir>` alongside `<status_path>`, but step 1 explicitly says the overview's `approved:` field (the only plan-dir mutation the planned+approved branch makes) is untouched here — nothing in `plan_dir` changes on this branch, so `add <plan_dir>` is copied from the sibling `planned+approved` branch's git command without adjustment. **Fix:** drop `<plan_dir>` from this commit's pathspec (harmless as-is since `git add` on an unchanged path is a no-op, but the pathspec should reflect what actually mutates).

## Verdict

REQUEST_CHANGES
`blocked_resume_round`'s `reviews_dir` binding point contradicts the file's own stated Path Setup architecture.
MILL_REVIEW_END
