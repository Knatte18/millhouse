# Batch: idempotent-checkpoint

```yaml
task: "Fix stale checkpoint safety, Go binary ephemeral allowlist, and bare agent-tier name trap"
batch: idempotent-checkpoint
number: 3
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes issue #567: `mill-merge-in` step 2 creates the rollback checkpoint with `git branch "$CHK"`, which fails silently (`fatal: ... already exists`) when a checkpoint branch from a prior run is still present, leaving the rollback target pointing at a stale commit. Because the checkpoint is deliberately left in place on success, hitting an existing checkpoint on a re-run is the normal state — so step 2 must be idempotent. This batch edits the `mill-merge-in` SKILL.md prose only. Verification is prose-only per the discussion decision (#567 is a behavioral skill-doc change with no Python module to unit-test, and the existing integration harness does not cleanly drive skill prose), hence `verify: null`.

## Cards

### Card 6: Make checkpoint creation idempotent with an audit note

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-merge-in/SKILL.md` "### 2. Create checkpoint", replace the unconditional `git branch "$CHK"` with a detect-then-force sequence so the checkpoint always points at the current (true pre-merge) HEAD: (1) capture the existing checkpoint sha if present via `git rev-parse --verify --quiet "$CHK"` (empty when absent); (2) run `git branch -f "$CHK"` to (re)create the checkpoint at current HEAD; (3) if the checkpoint pre-existed, emit an informational, non-blocking note recording the move using ASCII arrows, e.g. `[mill-merge-in] note: existing checkpoint <CHK> moved from <old-sha> -> <new-sha> (current pre-merge HEAD)`. Update the surrounding prose in step 2 (and any wording in the `## Rollback` section that implies the checkpoint is created only once) to state the checkpoint is force-refreshed to the true pre-merge HEAD on every run and that this is safe because step 1's no-op check has already confirmed we are at a clean pre-merge HEAD. Do NOT change the rollback contract (`git reset --hard "$CHK"`), the "preserve checkpoint on failure" rule, or the `mill-merge` consumer that resets to the same checkpoint name. The checkpoint branch name is never the currently checked-out branch, so `git branch -f` is always legal. Keep all shell snippets POSIX and ASCII only.
- **Commit:** `fix(mill-merge-in): force-refresh checkpoint to current HEAD with audit note`

## Batch Tests

`verify: null` — this batch edits SKILL.md prose only; there is no runnable code surface. Per the discussion `#567` testing decision, verification is by inspection of the edited step 2 + Rollback prose (confirming `git branch -f` and the audit note) plus the manual repro from issue #567 (create checkpoint, re-run, confirm `$CHK` points at the current pre-merge HEAD and the run does not error). No automated test is added because no Python module owns this skill step and the integration harness does not drive skill prose.
