# Batch: millgo-holistic-recovery

```yaml
task: '66 (A) -- Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv'
batch: millgo-holistic-recovery
number: 6
cards: 1
verify: null
depends-on: [5]
```

## Batch Scope

Update `plugins/mill/skills/mill-go/SKILL.md` so Holistic step 1 (Crash-recovery) explicitly enumerates the three resume scenarios that surfaced in #333. The new wording calls `_bg.is_bg_worker_alive` (added in batch 5) when a bg log exists for the current round, then chooses to wait for the live worker or re-fire the CLI for the dead one. The new wording also documents the skip-step-2 invariant: on every recovery branch that proceeds to fire the CLI, mill-go MUST skip step 2's `_status.append_phase("holistic-reviewing", ...)` because the phase entry was already appended on the original (pre-crash) run; appending a duplicate would corrupt the timeline.

External interface: SKILL.md prose only. The Bash invocation patterns this card adds reference `_bg.is_bg_worker_alive` -- which is why this batch depends on batch 5.

`verify: null` because this batch is pure documentation; no runnable Python surface. The Test plan below describes the manual verification (re-read SKILL.md end-to-end and confirm the three branches read as a coherent decision tree).

## Cards

### Card 16: update mill-go SKILL.md Holistic step 1 to three-branch recovery + skip-step-2 invariant

- **Context:**
  - `plugins/mill/scripts/_bg.py`
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the current Holistic step 1 (single sentence at line 331) with the three-branch decision tree below. Keep step 0 (Wiki health-check, lines 310-329) unchanged. Keep step 2 (line 333) unchanged in shape, but add the skip-step-2 invariant note so a reader knows the branches in step 1 may bypass step 2.

  New step 1 text:

  > 1. **Crash-recovery.** Three-way branch based on what is on disk in `_mill/reviews/` and `.scratch/`:
  >    - **(a) Review file present.** Scan `reviews/` for a file matching `*-code-review-r{H}.md` (holistic code review files have format `{ts}-code-review-r{N}.md` -- no batch-name segment, no `-holistic-` substring; per-batch files embed `{batch_name}` so the glob never collides). If found, skip the CLI and use that file's verdict directly. Proceed to step 4 (verdict branch); do NOT execute step 2 (the phase entry was already appended on the original run) and do NOT execute step 3.
  >    - **(b) No review file, no bg log for round H.** Proceed normally to step 2 (append `holistic-reviewing` phase) and step 3 (fire CLI via `millpy-bg`).
  >    - **(c) No review file, bg log exists for round H** (matching glob `.scratch/bg-*-review-code-holistic-r{H}.log`). Pick the most recent matching file and call `_bg.is_bg_worker_alive(log_path)`:
  >       - **Alive** -> poll `cat <log-path>` until `[mill-bg] EXIT` appears, then resume at step 4 (parse JSON, branch on verdict). Do NOT execute step 2; do NOT execute step 3.
  >       - **Dead** -> log `[mill-go] previous holistic round H bg worker died (pid=N); re-firing CLI` to stderr, then jump directly to step 3 (fire fresh CLI via `millpy-bg`). Do NOT execute step 2 (the phase entry was already appended on the original run).
  >
  >    Inline Python helper for branches (a) and (c):
  >
  >    ```bash
  >    PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  >    from pathlib import Path
  >    import _paths, _bg, json, sys
  >    git_root = _paths.resolve_git_root()
  >    reviews_dir = git_root / '_mill/reviews'
  >    scratch_dir = git_root / '.scratch'
  >    H = ${H}
  >    # (a) review file scan
  >    matches = sorted(reviews_dir.glob(f'*-code-review-r{H}.md')) if reviews_dir.exists() else []
  >    if matches:
  >        print(json.dumps({'branch': 'a', 'review_file': str(matches[-1])}))
  >        sys.exit(0)
  >    # (c) bg log liveness probe
  >    bg_logs = sorted(scratch_dir.glob(f'bg-*-review-code-holistic-r{H}.log')) if scratch_dir.exists() else []
  >    if bg_logs:
  >        alive, pid = _bg.is_bg_worker_alive(bg_logs[-1])
  >        print(json.dumps({'branch': 'c', 'log_path': str(bg_logs[-1]), 'alive': alive, 'pid': pid}))
  >        sys.exit(0)
  >    # (b) nothing on disk
  >    print(json.dumps({'branch': 'b'}))
  >    "
  >    ```
  >
  >    Parse the JSON line. Branch dispatch is exactly as enumerated above. The helper is one-shot; do not poll it.

  Update step 2's leading sentence from `\`_status.append_phase(status_path, "holistic-reviewing", _timestamp.now_utc_iso())\`. Commit:` to `**Skip this step when step 1 returned branch (a) or any sub-branch of (c).** \`_status.append_phase(status_path, "holistic-reviewing", _timestamp.now_utc_iso())\`. Commit:`. Keep the existing commit command unchanged.

  Do NOT modify step 3 (CLI invocation), step 3.5 (ERROR-only retry), step 4 (APPROVE), step 5 (REQUEST_CHANGES), step 6 (NEED_CONTEXT), or step 7 (Rounds exhausted) bodies. The only edits in this card are the rewritten step 1 and the skip-step-2 prefix on step 2's leading sentence.

  Verify by re-reading the edited file end-to-end that the three-branch decision tree is coherent and that no other step references step 1's old single-branch wording.
- **Commit:** `docs(mill-go): three-branch holistic crash-recovery with skip-step-2 invariant (#333)`

## Batch Tests

No runnable test surface (`verify: null`). Manual verification: after the SKILL.md edit lands, re-read Holistic step 1 in full and walk through the three branches against a hypothetical resume scenario. Confirm that on every branch that proceeds to step 3, the operator does NOT append a duplicate `holistic-reviewing` phase entry.
