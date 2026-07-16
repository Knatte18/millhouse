# Batch: windows-long-path-mitigation

```yaml
task: Batch verify/baseline/completeness gates produce false positives or time out
batch: windows-long-path-mitigation
number: 6
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-verify-baseline.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Mitigates #629: `_verify_baseline.compute_baseline`'s transient-worktree checkout can hit a Windows `WinError 3` (MAX_PATH) on repos with deeply-nested test fixtures, because `.scratch/verify-baseline-<uuid4().hex>/` (32 hex characters) adds substantial path-prefix length on top of an already-long fixture path. This batch applies the one low-risk, cross-platform-verifiable mitigation identified in `_mill/discussion.md`'s `windows-long-path-mitigation` decision: shortening the transient-worktree directory name to reclaim path budget. It deliberately does NOT attempt a `\\?\`-extended-length-path-prefix change to the `git worktree add` invocation (unverifiable without a Windows machine, real regression risk if wrong) — see the discussion decision for the full rationale. This batch is a root batch, independent of every other batch in this plan.

## Cards

### Card 19: Shorten the transient-worktree directory name

- **Context:** none beyond this batch's own Edits
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change the line `tmp_path = scratch_dir / f"verify-baseline-{uuid.uuid4().hex}"` (in `compute_baseline`) to use a shortened hex slice: `tmp_path = scratch_dir / f"verify-baseline-{uuid.uuid4().hex[:12]}"` (12 hex characters — still ~2^48 combinations, effectively collision-free for a short-lived per-invocation scratch directory). Update the module docstring / `compute_baseline`'s own docstring wherever it references the directory-name shape (e.g. any example path shown) to match the shortened form. Add a one-line comment at the `tmp_path` assignment explaining this is a best-effort Windows MAX_PATH mitigation (#629), not a guaranteed fix — the existing non-blocking fail-safe in `_run_baseline_stage` (which never raises; on any failure it leaves the baseline field unset and the next `_run_verify_gates` call runs the gate strictly) remains the actual safety net regardless of whether this shortening is sufficient for any given repo's fixture depth.
- **Commit:** `fix(_verify_baseline): shorten transient-worktree directory name to reclaim Windows path budget`

### Card 20: Unit test for the shortened directory-name pattern

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a case (continuing this file's existing single-`main()`-with-inline-numbered-case style) that exercises `compute_baseline`'s transient-worktree path construction (mocking `git worktree add` and the verify-command subprocess calls, consistent with however this file's existing tests already avoid running a real git worktree operation) and asserts the generated directory basename matches `re.match(r"^verify-baseline-[0-9a-f]{12}$", name)` — confirming both the shortened length and that the value is still derived from `uuid.uuid4().hex` (lowercase hex characters only, not some other identifier scheme).
- **Commit:** `test(verify-baseline): assert shortened transient-worktree directory-name pattern`

## Batch Tests

`verify:` (frontmatter above) runs `test-verify-baseline.py`, the only test file this batch touches (Card 20's new case, run alongside the file's existing coverage — including the existing `core.longpaths` assertion test, which this batch does not modify and which must continue passing unchanged).
