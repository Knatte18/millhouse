No dirty tracked files. `verify: null` so no test run needed. All requirements for Card 3 are implemented and committed.

Summary of changes to `/plugins/mill/skills/mill-merge/SKILL.md`:

- **Step 5 phase-gate table**: both `done` and `pr-pending` rows now route to `*PR-state gate*` instead of "continue to Step 1" and "*PR-path re-entry*" respectively.
- **Caching block**: clarified it applies only `When phase: done`, while status.md still exists.
- **New `### PR-state gate`** (inserted between Entry Step 5 and `## Steps`): captures `CHILD_BRANCH`, resolves state via `_pr_state.resolve_pr_state`, and routes `merged` / `open` / `closed` / `none` with the full semantics specified in the batch requirements.
- **`## PR-path re-entry`**: replaced with a single pointer sentence; the old divergent routing table is gone.

{"status":"success","commit_sha":"ba4f2a4c8b6303bdb76ac42ee78754de4a302dc0","session_id":"33a89e54-42c9-4c2a-8b08-9415e9e262ae"}
