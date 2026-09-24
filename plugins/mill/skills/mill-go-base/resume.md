# mill-go-base: Resume

A batch that reached `state: blocked` is NOT handled by this file's own resume routing — it is handled by the `### Entry: resuming a blocked batch after external fix` subsection in `mill-go-base/SKILL.md`'s Entry phase gate, which runs BEFORE this file is ever reached (this file's own step 1, "locate the entry whose state is non-terminal: running, reviewing, or fixing," never matches a `blocked` batch, by design — `blocked` is a terminal state until `resume_batch` moves it back to `pending`).

When mill-go's Entry-step 5 phase gate routes here (phase is `implementing`, `reviewing`, or `fixing`), the previous run was interrupted mid-batch.
The CLI that mutates task state (`millpy-implement.py`) is atomic — they record state-mutation commits before the heavy work starts and after each transition — so the resume playbook is simple: read the current batch entry and re-invoke the CLI for the current state.

1. Read `_mill/status.md`;
   locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`).
   **Fallback — no non-terminal entry found.** If `_status.read_batches(status_path)` finds no entry with a non-terminal state, this is the narrow window between Prepare's bare `implementing` phase-append and Execute's dispatch of the first batch — every batch entry is still `state: pending`. Skip the rest of this Resume file entirely and fall through directly to `plugins/mill/skills/mill-go-base/SKILL.md`'s `## Execute — sequential loop`, starting at the first `pending` batch in `order`.
2. Branch on the batch's `state`:
   - **`running`** — the implementer was mid-implementation.
     Re-invoke:

     The SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state.
     The prepare-stage pre-commit makes this idempotent;
     the brief at `_mill/briefs/<role>-<scope>-r<round>.md` is reused/re-rendered.
     Follow the Agent-mode dispatch pattern (see `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Agent-mode dispatch") with `<cli> = millpy-implement.py` and `<args> = <batch_name>`.
     The interrupted implementer session is dead and cannot be re-attached, so a fresh implementer dispatch is still the correct recovery — but `--resume-incomplete` preserves the original `start_sha`/`implementer_session` recorded by the interrupted run (reading them from `status.md` instead of re-capturing HEAD and minting a fresh UUID), so finalize's completeness recount and commit accounting reflect the batch's full history, not just the resumed dispatch's own commits — consistent with how agent-mode Resume already behaves via `_prepare_reuse_entry`.
     After parsing the report, continue at `plugins/mill/skills/mill-go-base/SKILL.md`'s "## Execute" step 2b (cleanliness gate).
   - **`reviewing` / `fixing`** — only per-batch code review, since removed, wrote these states, so the entry was left by an older plugin version. The implementer report was already consumed: continue at `plugins/mill/skills/mill-go-base/SKILL.md`'s Execute step 3 (`### 3. Complete batch`).
3. **No state mutation before resume.**
   Do NOT pre-emptively flip `state` or call `_status.append_phase` before re-invoking the CLI.
   The CLI handles state transitions atomically;
   double-writes corrupt the timeline.
