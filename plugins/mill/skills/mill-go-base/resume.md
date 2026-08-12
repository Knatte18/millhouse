# mill-go-base: Resume

When mill-go's Entry-step 5 phase gate routes here (phase is `implementing`, `reviewing`, or `fixing`), the previous run was interrupted mid-batch.
The CLIs that mutate task state (`millpy-implement.py`, `millpy-review-code.py`) are atomic — they record state-mutation commits before the heavy work starts and after each transition — so the resume playbook is simple: read the current batch entry and re-invoke the CLI for the current state.

1. Read `_mill/status.md`;
   locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`).
2. Branch on the batch's `state`:
   - **`running`** — the implementer was mid-implementation.
     Re-invoke:

     The SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state.
     The prepare-stage pre-commit makes this idempotent;
     the brief at `_mill/briefs/<role>-<scope>-r<round>.md` is reused/re-rendered.
     Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-implement.py` and `<args> = <batch_name>`.
     The interrupted implementer session is dead and cannot be re-attached, so a fresh implementer dispatch is still the correct recovery — but `--resume-incomplete` preserves the original `start_sha`/`implementer_session` recorded by the interrupted run (reading them from `status.md` instead of re-capturing HEAD and minting a fresh UUID), so finalize's completeness recount and commit accounting reflect the batch's full history, not just the resumed dispatch's own commits — consistent with how agent-mode Resume already behaves via `_prepare_reuse_entry`.
     After parsing the report, continue at Execute step 2b (cleanliness gate).
   - **`reviewing`** — the implementer report was already consumed;
     the reviewer was running.
     Re-invoke the per-batch code-review CLI from the start of round `review_round` (read this field from the batch entry):

     The SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state.
     Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name>`.
     The CLI's crash-recovery scan handles a written-but-uncommitted review file.
     After parsing the JSON verdict, continue at Execute step 3 sub-step 3 (load `mill-receiving-review`) and step 4 (branch on verdict).
   - **`fixing`** — the reviewer returned `REQUEST_CHANGES`;
     the fix-implementer was running.
     Re-invoke:

     The SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state.
     Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <review_round>`.
     The `<review-file-abs-path>` is the most recent `_mill/reviews/*-code-review-<batch_name>-r<review_round>.md` file.
     After parsing the report, continue at Execute step 3 sub-step 5 (max-rounds check) or back to step 3 round N+1 if the fix produced an APPROVE-eligible state on next review.
3. **No state mutation before resume.**
   Do NOT pre-emptively flip `state` or call `_status.append_phase` before re-invoking the CLI.
   The CLI handles state transitions atomically;
   double-writes corrupt the timeline.
4. **`mill-receiving-review` remains the fixer's responsibility.**
   When resume re-dispatches the fixer (`millpy-fix.py --scope batch ...`), the fix-prompt itself instructs the fixer to load the skill before reading findings.
   Builder still does not load it.
