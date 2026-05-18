# Batch: mill-go-cleanup-integration

```yaml
task: Keep psmux TUI alive across calls for session continuity
batch: mill-go-cleanup-integration
number: 4
cards: 2
verify: null
depends-on: [3]
```

## Batch Scope

Wires mill-go to call `_llm_claude.cleanup_session(session_id)` at every point a logical implementer session ends, so psmux sessions never accumulate beyond one logical batch (per discussion.md "cleanup model" rule 3). Two cards: card 12 covers the per-batch implement-review-fix loop sites (Execute step 2, 2b, 3 sub-step 4 APPROVE, sub-step 5 max-rounds, and Stuck escalation autonomous + user-block paths); card 13 covers the holistic implement-review-fix loop sites (Holistic step 5 REQUEST_CHANGES re-dispatch and steps 4/5/7 terminus paths). All cleanup invocations are inline `$MILL_PYTHON -c "..."` Bash blocks following the existing pattern in mill-go SKILL.md (see line 121 — the wiki-health-check block for the canonical shape).

External interface: none — SKILL.md changes only. Batch-local decision: every cleanup call uses the canonical `implementer_session` field already stored in `_mill/status.md` per batch entry (read via `_status.read_batches`). For the holistic loop the session id is read from the parsed JSON envelope of the most recent `millpy-implement-holistic.py` invocation — the Builder captures it into a Bash variable when the run returns. Cleanup blocks always swallow failures (because `cleanup_session` itself swallows `PsmuxError`); they never affect the flow control around them.

## Cards

### Card 12: insert per-batch cleanup_session sites in mill-go SKILL.md

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Define a canonical inline cleanup block once and reuse it at every insertion site. The block reads `implementer_session` from status.md for the current `<batch_name>` and calls `cleanup_session`:

  ```bash
  PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import sys
  sys.path.insert(0, r'${PLUGIN_ROOT}/scripts')
  from pathlib import Path
  import _paths, _status, _llm_claude
  status_path = _paths.resolve_task_path(_paths.resolve_git_root(), '_mill/status.md')
  batches = _status.read_batches(status_path)
  sid = next((b.get('implementer_session') for b in batches if b['name'] == '<batch_name>'), None)
  _llm_claude.cleanup_session(sid)
  " || true
  ```

  Insert (or document this block in the section's preamble and reference it by name "per-batch cleanup block" at each site) at the following five points in `plugins/mill/skills/mill-go/SKILL.md`:

  1. **Execute step 2, transient-retry path (around line 175):** the auto-retry-once on `stuck_type: transient` re-invokes `millpy-implement.py` (no `--resume`) which generates a fresh session id and overwrites `implementer_session` in status.md. Insert the cleanup block IMMEDIATELY BEFORE that re-invocation so the old (dead) psmux session is reaped first.
  2. **Execute step 2b, cleanliness-gate blocked path (around line 188):** insert the cleanup block IMMEDIATELY AFTER the `git commit` that records "mill-go: blocked on <batch_name> — dirty tree" and BEFORE the "Go to *Blocked*" jump.
  3. **Execute step 3 sub-step 4, APPROVE branch (around line 223):** insert the cleanup block IMMEDIATELY AFTER the `git commit -m "mill-go: approve batch {batch_name}"` and BEFORE the "Break out of the loop -> next batch" sentence.
  4. **Execute step 3 sub-step 5, max-rounds exhaustion (around line 256):** insert the cleanup block IMMEDIATELY AFTER the `git commit -m "mill-go: blocked on {batch_name} after {N} rounds"` and BEFORE the "Go to *Blocked* below" jump.
  5. **Stuck escalation, both autonomous-mode block and user-chosen block (around lines 260 and 265):** insert the cleanup block at the END of each respective branch — immediately after the blocked-commit, before the "go to *Blocked*" jump. The autonomous-mode block is the unconditional autonomous-mode body at the top of the Stuck escalation section; the user-chosen block is the "On user-chosen block:" line at the bottom of the section.

  Add a short prose sentence at the top of the Execute section (just before "### 0. Wiki health-check") explaining the cleanup contract:
  > **Per-batch session cleanup.** Every time the per-batch implement-review-fix loop terminates (APPROVE, max-rounds blocked, cleanliness-blocked, stuck-blocked) OR the Builder is about to re-dispatch the implementer with a fresh session (transient-retry-once), invoke the *per-batch cleanup block* defined below — it reaps the psmux TUI session associated with the batch's `implementer_session`, idempotent and failure-swallowing.

  Define the block literally in that preamble paragraph (the Bash snippet above) so each of the five sites can refer to it by name without restating it. Each insertion site then just says `Invoke the per-batch cleanup block.` on its own line at the indicated position.
- **Commit:** `mill-go: invoke cleanup_session at every per-batch loop terminus`

### Card 13: insert holistic-loop cleanup_session sites in mill-go SKILL.md

- **Context:**
  - `plugins/mill/scripts/_llm_claude.py`
  - `plugins/mill/scripts/millpy-implement-holistic.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The holistic implementer (`millpy-implement-holistic.py`) generates a fresh `session_id` per invocation and emits it on the final JSON line of stdout. Mill-go must capture that id into a Bash variable when each holistic-fix invocation completes (the variable is local to the Holistic section's loop iteration) and reuse it for cleanup. Add at the top of the Holistic section (immediately before "**Guard:**" on line 317), a paragraph:
  > **Holistic session cleanup.** Whenever a `millpy-implement-holistic.py` invocation completes (success, stuck, or any error path), capture the `session_id` field from the parsed JSON envelope into a local Bash variable `holistic_sid`. At any point where the holistic loop is about to dispatch a NEW `millpy-implement-holistic.py` round, AND at every loop terminus (APPROVE, autonomous-mode block, user-block, max-rounds), invoke the *holistic cleanup block* defined below.

  Define the block in that paragraph (sibling to card 12's per-batch block):

  ```bash
  PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import sys
  sys.path.insert(0, r'${PLUGIN_ROOT}/scripts')
  import _llm_claude
  _llm_claude.cleanup_session('${holistic_sid}')
  " || true
  ```

  Insertion sites in `plugins/mill/skills/mill-go/SKILL.md`:

  1. **Holistic step 4 APPROVE (around line 437):** at the end of the line, after "Commit status. Proceed to Handoff.", insert `Invoke the holistic cleanup block.` as a new sentence/bullet so the session is reaped before Handoff begins.
  2. **Holistic step 5 REQUEST_CHANGES re-dispatch (around line 439):** before the `PYTHONPATH=... millpy-implement-holistic.py ...` invocation on line 441, insert `Invoke the holistic cleanup block (reaps the previous round's session before the next one starts).` If `holistic_sid` is empty / unset on the very first round (no previous invocation), the cleanup block is a no-op because `cleanup_session(None)` and `cleanup_session("")` both return immediately (per batch 3 card 10).
  3. **Holistic step 5 stuck-block paths (around lines 445, 446):** for both the `stuck_type: transient` "still transient after retry -> user choice" branch (when the user chooses Block) and the `stuck_type: verify | logic` "user chooses Block task" branch, insert `Invoke the holistic cleanup block.` at the END of the user-chose-block branch, before the "go to Blocked" jump (the existing Blocked section text — note Holistic borrows the Blocked target from the per-batch flow).
  4. **Holistic step 7 rounds-exhausted (around line 451):** after the commit `mill-go: blocked on holistic review (autonomous-mode)` (autonomous path) AND after the user-block branch (the operator-interactive `3) Block — halt` branch), insert `Invoke the holistic cleanup block.` before the halt/return.

  Do NOT add a cleanup at the holistic-review CLI (`millpy-review-code.py --holistic`) invocations — only the implementer-holistic invocations leave a psmux implementer session. The reviewer LLM uses its own backend with no caller-driven session_id.
- **Commit:** `mill-go: invoke cleanup_session at every holistic loop terminus`

## Batch Tests

`verify: null` — this batch is SKILL.md edits only, no runnable surface and no automated regression coverage. Reviewer verifies by spot-checking each of the seven insertion sites against the discussion's "cleanup model" rule 3 and the canonical inline cleanup blocks defined in cards 12 and 13. Manual smoke (operator only, post-merge): run mill-go end-to-end on a small two-batch task with `llm.claude.psmux.via_psmux: true`; after the run completes (or fails) verify `psmux ls` shows no leftover `mill-*` sessions tied to the run's batch ids.
