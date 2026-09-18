# Batch: entry-gate-parallel-baseline

```yaml
task: "mill-go-base: orchestration robustness gaps"
batch: entry-gate-parallel-baseline
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python -c "import pathlib; t = pathlib.Path('plugins/mill/skills/mill-go-base/SKILL.md').read_text(encoding='utf-8'); assert 'baseline_preflight_log' in t, 'missing baseline_preflight_log marker'; assert '--module-wide-only' in t, 'missing --module-wide-only marker'; assert 'Restart/orphan reconciliation' in t, 'missing restart/orphan reconciliation marker'; print('ok')"
depends-on: [2, 5]
```

## Batch Scope

Fixes #1031: overlaps mill-go-base's entry-gate wait for `phase: planned` with the "0.5. Baseline pre-flight" step's module-wide substage, and closes the restart/orphan race a review round surfaced against the naive version of this fix (see `_mill/discussion.md`'s `1031-parallel-entry-baseline` Decision for full rationale and the round-by-round review history). Depends on batch 2 for `_status.set_baseline_preflight_log`/`get_baseline_preflight_log`/`clear_baseline_preflight_log` and `millpy-implement.py --stage baseline --module-wide-only` (real dependency). Additionally depends on batch 5 (`review-loop-fixes`) — not a real feature dependency, but required to serialize this batch against every other `SKILL.md`-editing batch (5, 4, 6, all pairwise `SKILL.md`-overlapping), per the validator's `parallel-modifies-overlap` check; batch 5 already transitively depends on 4 and 4 on 6, so this single edge covers the whole chain. Single card, single file (`SKILL.md`); estimated context: SKILL.md edit (≈26,700 tokens) + Context reads of `_status.py` (≈15,306) and `millpy-implement.py` (≈12,664) ≈ 54,670 tokens, under the cap.

## Cards

### Card 5: overlap entry-gate wait with speculative module-wide-only baseline launch

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/millpy-implement.py`
- **Edits:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Two edits to `SKILL.md`, both required together for a working feature.

  **Edit A — "Entry-gate wait for upstream mill-plan" section.** Locate the bullet block beginning `- **If `matched` is `True` and `entry_wait` is `True`:**` (inside `### Entry-gate wait for upstream mill-plan`). Immediately after its `- State one sentence to the user: waiting for the upstream mill-plan run to reach `phase: planned`.` bullet, and immediately BEFORE its `- Call the `Monitor` tool with `command=cmd`, ...` bullet, insert a new bullet performing a one-shot speculative baseline launch:
  - First read `status.md`'s top yaml block for an existing `baseline_preflight_log:` field via `_status.get_baseline_preflight_log(status_path)`.
    - If a log path is already recorded (a prior session, interrupted and restarted, already launched a job): do NOT launch a second job. Instead run the existing `_bg.check_bg_status` liveness check (the same helper "0.5. Baseline pre-flight" already uses) against that log path and branch: `"running"` → take no further action here (the job is still in flight; "0.5. Baseline pre-flight" will find and poll it when reached); `"exit"` → leave the field as-is (Edit B below consumes and clears it); `"dead"` → call `_status.clear_baseline_preflight_log(status_path)`, then proceed to the launch step below as if no field had been present (mirrors "0.5. Baseline pre-flight"'s own existing `"dead"` handling: log the reason, don't halt, don't leave a stale pointer).
    - If no log path is recorded: check whether `<plan_dir>/00-overview.md` exists on disk with `approved: true` in its frontmatter (the same extraction pattern the rest of this file already uses for that field). If both hold, launch the job: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" --slug baseline-preflight-early -- "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" --stage baseline --module-wide-only` (fire-and-forget — do not poll it here), then immediately call `_status.set_baseline_preflight_log(status_path, <the millpy-bg log path returned>)` and commit that single-field status.md change on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "<VARIANT_LABEL>: speculative baseline pre-flight launch for {slug}"`) — do not push yet, this commit rides along with whatever the wait's next natural push point is (do not add a new push call here). If the overview isn't present/approved yet (a genuinely fresh mill-plan run still in progress), do nothing — proceed straight to the existing `Call the Monitor tool` bullet unchanged.
  - Label this new bullet's own explanatory text with a `**Restart/orphan reconciliation:**` lead-in sentence stating: this makes the earlier launch discoverable across a `/mill-go` restart (the builder lock's documented stale-self-lock reclaim means a restart can re-enter this same wait with no memory of an in-flight detached `millpy-bg` process from the interrupted session — persisting the log path in `status.md`, not only in a local variable, is what closes that race).

  **Edit B — "0.5. Baseline pre-flight (first batch of the task only)" section.** At the very top of this section (immediately after its heading, before the existing "Immediately before `### 1. Implement` fires..." paragraph, or interleaved into it — whichever reads more naturally as one continuous procedure), insert a first-check step: call `_status.get_baseline_preflight_log(status_path)`.
  - If it returns a log path: check `_bg.check_bg_status` against it. `"exit"` → run `grep '^{' <log-path>` to extract the two JSON summary lines exactly as this section's existing polling logic already does, treat the module-wide-only line as this batch's module-wide result (its `substage: "module_wide"` line), then call `_status.clear_baseline_preflight_log(status_path)`, then proceed to run a SECOND, ordinary (no `--module-wide-only`) `--stage baseline` invocation for the per-batch substage only — safe now, since `## Prepare` has already run `_status.init_batches` by this point in Execute, so `## Batches` exists. The module-wide half of this second call is itself a free no-op per its own existing `"cached"` short-circuit (`_module_wide_skip_or_cached_payload`), so this is not double work. `"running"` → poll that same log exactly as this section's existing polling loop already does (do not launch a fresh job), then once `[mill-bg] EXIT` appears follow the same `"exit"` handling above (extract, clear the field, run the second per-batch-only call).
  - If it returns `None` (no early launch happened — the overview wasn't approved yet at entry-gate-wait time, or this is a run where `pipeline.entry_wait` is `False` and Edit A's block never executed): fall back to launching the full (both-substage) job exactly as this section already documents today, completely unchanged.
- **Commit:** `mill-go-base: overlap entry-gate wait with speculative baseline pre-flight (#1031)`

## Batch Tests

This batch edits only `SKILL.md` (an LLM-read instruction file, no executable Python surface of its own), so `verify:` (see frontmatter above) is a `python -c` assertion rather than a test-file invocation: it confirms the three code-identifier-like markers Card 5's Requirements mandate (`baseline_preflight_log`, `--module-wide-only`, `Restart/orphan reconciliation`) are all present in the edited file — one check covering both Edit A and Edit B together, since they form one indivisible feature (per this plan's "prose-only batches verify via exact-marker grep/python assertions" Shared Decision in `00-overview.md`).
