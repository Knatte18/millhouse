# Batch: orchestrator-integration

```yaml
task: Wiki-daemon + bg-worker + test-suite robustness on Windows
batch: orchestrator-integration
number: 3
cards: 2
verify: null
depends-on: [2]
```

## Batch Scope

Wires the batch-2 `_bg.wait_for_bg_terminal` helper into the two orchestrator
SKILL.md files so a bg worker killed mid-flight (Windows logout) is detected
instead of polled-on forever. mill-go gains a new `stuck_type: infrastructure`
classification with a fresh-re-fire recovery; mill-start, being always
interactive, surfaces an error and halts. This batch is pure prose/instruction
editing — there is no runnable surface, so `verify: null` (the mechanism it
calls is unit-tested in batch 2). It `depends-on: [2]` because the SKILL prose
references `wait_for_bg_terminal`, which must exist first.

## Cards

### Card 8: mill-go in-session liveness detection + `infrastructure` stuck

- **Context:**
  - `plugins/mill/scripts/_bg.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `mill-go/SKILL.md` to add bg-worker liveness detection
  to the in-session poll and a new `infrastructure` stuck type:
  (1) **Poll replacement.** Every place that currently instructs "Poll the log
  file with `cat <log-path>` until `[mill-bg] EXIT` appears" (the per-batch
  implement step, the per-batch review step, the per-batch NIT-fix step, the
  fix step, the holistic review step, and the holistic NIT-fix step) must
  instead invoke a single blocking call to `_bg.wait_for_bg_terminal(log_path)`
  via a documented Bash one-liner of the form
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; ..."`
  that prints the `("exit", code)` / `("dead", pid)` result as JSON, and branch:
  on `("exit", code)` proceed exactly as today (run `grep '^{' <log> | tail -1`
  to extract the JSON summary, then the existing exit-handling rule — "only
  treat exit 1 as unrecoverable when the JSON line is absent"); on
  `("dead", pid)` classify as `stuck_type: infrastructure` and route to Stuck
  escalation. Preserve every existing post-EXIT instruction verbatim.
  (2) **Stuck escalation.** In the *Stuck escalation* section, add an
  `infrastructure` case: **interactive** — surface to the user with options
  `re-fire (fresh)` / `block` (numbered list, recommended option 1 = re-fire
  fresh per the conversation rule); **`autonomous_mode: true`** — auto-retry
  ONCE with a fresh re-fire of the same CLI (no `--resume`), and if the re-fire
  also returns `("dead", …)` set batch state -> `blocked`,
  `blocked_reason: "infrastructure: bg worker died (logout?)"`, append a
  `blocked` phase, commit + push, and go to *Blocked*. State explicitly that the
  re-fire is identical to the existing `running`-state Resume (fresh start; the
  killed session is dead and cannot be re-attached).
  (3) **Holistic variant.** Mirror the same `infrastructure` handling in the
  holistic-review stuck section.
  Do not alter the crash-recovery branch (c) at resume (it already probes
  `is_bg_worker_alive`) beyond optionally noting it shares the helper. Keep all
  added shell/log strings ASCII (` -- `, ` -> `).
- **Commit:** `feat(mill-go): detect dead bg worker as infrastructure stuck with fresh-refire recovery`

### Card 9: mill-start dead-worker detection -> surface and halt

- **Context:**
  - `plugins/mill/scripts/_bg.py`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Edit `mill-start/SKILL.md`'s Phase: Discussion Review so the
  "Poll the log file with `cat <log-path>` until `[mill-bg] EXIT` appears"
  instruction (in the review step and the ERROR-only-retry step) uses the same
  `_bg.wait_for_bg_terminal(log_path)` blocking call as card 8, branching on its
  result: on `("exit", code)` proceed exactly as today (extract the JSON summary
  and continue); on `("dead", pid)` surface a clear message to the operator —
  "discussion-review worker died (logout?); re-run the discussion-review step" —
  and **halt** with no auto-re-fire. State explicitly that mill-start is always
  interactive and has no `stuck_type` / autonomous machinery, so it differs from
  mill-go's `infrastructure` one-retry path. Keep all added strings ASCII.
- **Commit:** `feat(mill-start): surface and halt on dead discussion-review worker`

## Batch Tests

`verify: null` — both cards edit SKILL.md instruction prose, which has no
automated test surface. The mechanism these instructions invoke
(`_bg.wait_for_bg_terminal`, `is_bg_worker_alive`) is unit-tested in batch 2
(`test-bg-liveness.py`). Correctness of the prose is confirmed by the holistic
plan/code review and the documented manual logout-recovery checklist in the
task result (per discussion.md Testing section).
