# Batch: mill-go-skill

```yaml
task: "mill-go / mill-plan loop hardening"
batch: mill-go-skill
number: 5
cards: 3
verify: null
depends-on: [2, 4]
```

## Batch Scope

Updates `mill-go/SKILL.md` prose for the three mill-go-side fixes whose code landed in
batches 2 and 4: #360 (apply NITs on APPROVE), #373 (crash-recovery freshness probe), and
#362/#378 (stage the holistic review file on APPROVE). All three cards edit the single
`SKILL.md` file; they are sequenced as separate cards because they touch distinct sections.
`verify: null` — SKILL prose has no runnable surface.

`depends-on: [2, 4]` so the prose references the finalized `nit_count` envelope field
(batch 2) and `phase_entry_timestamp` helper (batch 4).

## Cards

### Card 10: apply NITs on APPROVE in both code-review paths

- **Context:**
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `mill-go/SKILL.md` so both APPROVE branches apply NITs (#360). The JSON envelope now carries a top-level `nit_count`. (1) Per-batch Code Review loop, step 4 `APPROVE` branch: before setting batch state to `approved`, add: "If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass via `millpy-fix.py --scope batch --batch-name <batch_name> --review-file <review_file_path> --round <N>` (same dispatch as REQUEST_CHANGES; the fixer loads `mill-receiving-review` and applies the NITs from the APPROVE'd review file), parse its JSON report the same way as Implement step 2, then proceed to approve. Do NOT re-review — the NIT fix is trusted." The NIT-fix session commits its own source-file changes atomically; the subsequent approve commit then stages `status_path` and `review_file_path` as before (unchanged staging behaviour). (2) Holistic code review, step 4 `APPROVE`: add the analogous rule using `millpy-fix.py --scope holistic --review-file <abs-path> --round {H}` when `nit_count > 0`, before appending `holistic-approved`. Keep the Builder lean: it reads only `nit_count` from the envelope, never the findings. State that a stuck report from the NIT-fix pass routes through the existing Stuck escalation.
- **Commit:** `docs(mill-go): apply NITs on APPROVE via nit_count dispatch (#360)`

### Card 11: crash-recovery review-file freshness probe

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `mill-go/SKILL.md` to make both crash-recovery review-file probes freshness-validated (#373), using `_status.phase_entry_timestamp`. (1) Per-batch Code Review loop: change the round-start phase append so it records `reviewing-{batch_name}-r{N}` for EVERY round N (today only `r1` is appended before the loop) — move/add the `_status.append_phase(status_path, f"reviewing-{batch_name}-r{N}", ...)` to the top of each round-N iteration, so the freshness probe has a per-round reference row. Then in step 3 sub-step 1 (Crash-recovery check): after globbing `*-code-review-{batch_name}-r{N}.md`, before trusting a match, fetch `ref_ts = _status.phase_entry_timestamp(status_path, f"reviewing-{batch_name}-r{N}", occurrence=1)`; treat the file as this round's review ONLY if `ref_ts` is not None AND the file's mtime (UTC) is at or after `ref_ts`; otherwise ignore the file and fall through to firing the CLI. (2) Holistic code review step 1 branch (a): glob `*-code-review-r{H}.md`; fetch `ref_ts = _status.phase_entry_timestamp(status_path, "holistic-reviewing", occurrence=H)` (the Hth occurrence corresponds to round H); apply the same mtime-vs-`ref_ts` freshness gate before using the file; on stale/None, fall through to branch (b)/(c) handling (fire the CLI). Provide the inline-Python comparison snippet in the SKILL (parse the ISO `ref_ts` to a tz-aware UTC datetime and compare against `datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)`). State explicitly that ERROR-only retries still do NOT consume the round counter; freshness — not counter consumption — is what rejects stale pre-retry files.
- **Commit:** `docs(mill-go): freshness-validate crash-recovery review files (#373)`

### Card 12: stage holistic review file on APPROVE

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `mill-go/SKILL.md` Holistic code review step 4 (`On APPROVE`). Today it reads "append `holistic-approved`. Commit status. Invoke the holistic cleanup block. Proceed to Handoff." Change the commit so it stages the holistic review file alongside `status.md`: `git -C <worktree> add <status_path> <review_file_path> && git -C <worktree> commit -m "mill-go: holistic approve {slug}"`, where `<review_file_path>` is the `file` field from `reviews[0]` of the JSON envelope (or the crash-recovery branch (a) scan path). This mirrors the per-batch APPROVE branch, which already stages its review file, and fixes #362/#378 (the holistic review file was previously dropped at cleanup). If card 10's NIT-fix pass ran for the holistic scope this round, the fixer already committed its own changes; this commit still stages the review file plus the `holistic-approved` status row.
- **Commit:** `docs(mill-go): commit holistic review file on APPROVE (#362, #378)`

## Batch Tests

`verify: null` — this batch edits only `mill-go/SKILL.md`. Correctness is verified by the
holistic plan/code reviewer reading the prose against the helper signatures finalized in
batches 2 (`nit_count`) and 4 (`phase_entry_timestamp`).
