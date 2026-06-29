Working tree is clean. `verify: null` for this batch — no test command to run.

The single card in this batch is complete. The edited file is `/plugins/mill/skills/mill-merge-in/SKILL.md`. The key changes made to "### 2. Create checkpoint":

- `git branch "$CHK"` replaced by a detect-then-force sequence: capture the existing sha with `git rev-parse --verify --quiet`, then `git branch -f "$CHK"` to atomically (re)create the checkpoint at the current pre-merge HEAD.
- When a pre-existing checkpoint is moved, an ASCII-only informational note is emitted.
- Surrounding prose updated to explain the force-refresh is safe because step 1's no-op check guarantees we are already at a clean pre-merge HEAD before step 2 runs.

{"status":"success","commit_sha":"06dbc059","session_id":"807706dc-1b57-4757-8d76-51c7f96d1f52"}
