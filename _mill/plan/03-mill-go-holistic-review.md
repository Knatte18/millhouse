# Batch: mill-go-holistic-review

```yaml
task: 'Non-interactive pipeline: only mill-start''s interview may prompt the operator'
batch: mill-go-holistic-review
number: 3
cards: 3
verify: null
depends-on: [2]
```

## Batch Scope

`mill-go/SKILL.md`'s `## Holistic code review` section has the same shape of `pipeline.autonomous_mode: true`-gated branches as `### Stuck escalation` (batch 2), but spread across three separate, non-adjacent sub-steps: `3.6` (Rate-limit fallback), the `REQUEST_CHANGES` branch of step `5`, and step `7` (Rounds exhausted). Each sub-step is edited as its own card since they do not share anchor text and editing them independently carries no cross-card corruption risk (unlike batch 2's single interdependent bullet list). This batch depends on batch 2 because both edit `mill-go/SKILL.md` and the `parallel-modifies-overlap` validator check requires an ordering edge between any two batches touching the same file.

## Cards

### Card 5: Make holistic Rate-limit fallback unconditional

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `3.6. **Rate-limit fallback (no round consumed)**`, sub-item `5.` currently reads exactly:

```
   5. If `pipeline.autonomous_mode: true` AND `fallback_reviewer is None` AND a rate-limit was detected on both 3.5 passes: halt with `BLOCKED: holistic rate-limited, no fallback_reviewer configured`. The operator-visible message is intentional -- silent infinite fallback is wrong.
```

  Replace it with:

```
   5. If `fallback_reviewer is None` AND a rate-limit was detected on both 3.5 passes: halt with `BLOCKED: holistic rate-limited, no fallback_reviewer configured`. The operator-visible message is intentional -- silent infinite fallback is wrong.
```

  Immediately after sub-item 5 (and after its enclosing numbered list), the paragraph currently reads exactly:

```
   Operator interactive path (no `autonomous_mode`, no `fallback_reviewer`): user prompt remains identical to today (the existing step 5 ROUND-EXHAUSTION sub-section handles this case).
```

  Delete this paragraph entirely — it describes an operator-interactive path that no longer exists (Card 7 in this batch makes step 7's round-exhaustion unconditional too, so there is no "user prompt" left for this paragraph to point at).
- **Commit:** `docs(mill-go): make holistic rate-limit fallback halt unconditional`

### Card 6: Make holistic REQUEST_CHANGES stuck_type branches self-resolve-then-escalate

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In step `5. On \`REQUEST_CHANGES\`:`, the three `stuck_type` bullets currently read exactly:

```
   - `stuck_type: infrastructure`: **interactive** mode — surface with options `1) Re-fire fresh (Recommended)` / `2) Skip holistic / 3) Block task`; user picks. On re-fire: invoke the holistic cleanup block, then re-invoke `millpy-fix.py --scope holistic` once (fresh). If the re-fire also fails with `infrastructure`: present user with same three options. **`autonomous_mode: true`** — auto-retry ONCE with a fresh re-fire. If the re-fire also fails: invoke the holistic cleanup block, set batch state -> `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. State that the re-fire is fresh (killed session cannot be reattached).
   - `stuck_type: transient`: one-retry policy (re-invoke once). If still transient: surface to user — retry fresh / skip holistic / block task. On user-chosen block: invoke the holistic cleanup block, then go to *Blocked*.
   - `stuck_type: verify` or `logic`: surface to user — edit plan and retry / skip holistic and proceed to Handoff / block task. On user-chosen block: invoke the holistic cleanup block, then go to *Blocked*.
```

  Replace the three bullets with:

```
   - `stuck_type: infrastructure`: auto-retry ONCE with a fresh re-fire: invoke the holistic cleanup block, then re-invoke `millpy-fix.py --scope holistic` once (fresh). If the re-fire also fails with `infrastructure`: invoke the holistic cleanup block, set batch state -> `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review"`, and go to *Blocked*. The re-fire is fresh (killed session cannot be reattached).
   - `stuck_type: transient`: one-retry policy (re-invoke once) — this retry IS the one-shot self-resolve attempt. If still transient after it: invoke the holistic cleanup block, set batch state -> `blocked`, `blocked_reason: "transient: unresolved after retry"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review"`, and go to *Blocked*.
   - `stuck_type: verify` or `logic` (first occurrence) → self-resolve once: investigate the finding using the same judgment an implementer/fixer already applies when picking "edit plan and retry" — read the holistic review file, edit the plan file(s) if the failure traces to an ambiguous or incorrect card. Before re-invoking, record the self-resolve: `_status.append_phase(status_path, "self-resolved-verify-logic", _timestamp.now_utc_iso())`, `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-go: self-resolved verify/logic stuck (holistic)"`. Then re-invoke `millpy-fix.py --scope holistic` once (fresh) for this round. If the retry produces the *same* `verify`/`logic` failure: invoke the holistic cleanup block, set batch state -> `blocked`, `blocked_reason: "verify/logic: unresolved after retry"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review"`, and go to *Blocked*.
```

  The `- On success: increment H and loop.` bullet immediately following stays unchanged — do not touch it.
- **Commit:** `docs(mill-go): make holistic fix-stuck branches self-resolve-then-escalate`

### Card 7: Make holistic Rounds-exhausted unconditional

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Step `7. **Rounds exhausted**` currently reads exactly:

```
7. **Rounds exhausted** (`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned): If the deep-merged config has `pipeline.autonomous_mode: true`: `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; `_status.update_field(status_path, "blocked_reason", f"holistic review exhausted {max_holistic_rounds} round(s) (autonomous-mode)")`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review (autonomous-mode)"` and push; invoke the holistic cleanup block; halt with "Autonomous mode: holistic review exhausted. Task left as [active]." Otherwise surface to user with a **blocked-task halt** (not blocked-batch):
   > Holistic review exhausted {max_holistic_rounds} round(s). Task is blocked.
   > 1) Rethink — revise discussion and re-run mill-plan.
   > 2) Skip holistic — accept remaining findings and proceed to Handoff.
   > 3) Block — halt and leave for manual resolution.
   On user choice of "3) Block": invoke the holistic cleanup block, then halt and leave for manual resolution. Wait for user choice before proceeding.
```

  Replace the whole step with:

```
7. **Rounds exhausted** (`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned): `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; `_status.update_field(status_path, "blocked_reason", f"holistic review exhausted {max_holistic_rounds} round(s)")`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review"` and push; invoke the holistic cleanup block; halt with "Holistic review exhausted {max_holistic_rounds} round(s). Task left as [active] for manual review."
```

  This deletes the entire numbered-options blockquote and the "Wait for user choice" paragraph — exhausted holistic rounds always end in a clean halt, matching mill-plan's max-rounds escape (batch 1, Card 2).
- **Commit:** `docs(mill-go): make holistic rounds-exhausted halt unconditional`

## Batch Tests

`verify: null` — this batch edits only `plugins/mill/skills/mill-go/SKILL.md`'s `## Holistic code review` section, a prose file interpreted by Claude Code at skill-invocation time, not executable Python. There is no runnable test surface. Correctness is verified by plan review (byte-exact old/new text matching against the actual worktree source) and, downstream, by mill-go's code review reading the resulting diff.
