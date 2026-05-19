# Discussion: Dedicated fixer agent for post-holistic-review fix cycles

```yaml
task: Dedicated fixer agent for post-holistic-review fix cycles
slug: holistic-fix-agent
status: discussing
parent: main
```

## Problem

The per-batch fix cycle in mill-go resumes a warm psmux Sonnet session (`millpy-implement.py --resume`). This requires the session to be kept alive across the entire review period (implementation → review → fix), which adds psmux keepalive complexity. The holistic fix cycle already uses a cold-start dispatch (`millpy-implement-holistic.py`), but it uses the full implementer model (sonnethigh) and has no escalation mechanism when a review finding contradicts the plan. Neither fix path has a dedicated model — both share `roles.implementer.model`.

Task 30 (autonomous orchestrator) needs fix flows that are simple, uniform, and stateless. The current warm-session resume is a prerequisite blocker: it requires the builder to track session IDs across phases and keep psmux alive, which is complexity the orchestrator cannot easily manage.

## Scope

**In:**
- New `millpy-fix.py` CLI with `--scope batch|holistic` flag — unified fixer for both fix cycles
- Extend `_reviewers.validate_role_refs` to check `roles.fixer.model` (same pattern as the existing `roles.implementer.model` check)
- New `plugins/mill/templates/fixer-batch-brief.md` — prompt for batch fixer
- New `plugins/mill/templates/fixer-holistic-brief.md` — prompt for holistic fixer
- New `roles.fixer.model` config key in `mill-config.yaml` (hub template) and `wiki/config.yaml`, defaulting to `haiku`
- Delete `millpy-implement-holistic.py` (replaced by `millpy-fix.py --scope holistic`)
- Delete `--resume` branch from `millpy-implement.py` (no longer called by mill-go)
- Delete `plugins/mill/templates/implementer-fix.md` (only used by the deleted resume branch)
- Delete `plugins/mill/templates/implementer-holistic-brief.md` (replaced by `fixer-holistic-brief.md`)
- Update `mill-go` SKILL.md: both per-batch fix dispatch and holistic fix dispatch
- Per-batch psmux cleanup: move cleanup to immediately after per-batch implementation completes (before review), removing the need for keepalive across the review window
- Unit tests: `plugins/mill/unit_tests/test-millpy-fix.py`

**Out:**
- Per-batch initial implementation (still Sonnet via `millpy-implement.py`, unchanged)
- Per-batch review dispatch (unchanged)
- Holistic review dispatch (unchanged)
- psmux infrastructure itself — psmux is still used for per-batch implementation; only the fix cycle changes
- mill-go resume logic for `implementing` / `reviewing` phases (only `fixing` phase resume changes)
- Config flag for keep-alive fix sessions (YAGNI — can be added later if needed)

## Decisions

### Scope: both batch and holistic fix cycles

- Decision: Replace both per-batch AND holistic fix cycles with the new fixer. Both dispatch `millpy-fix.py` (cold-start Haiku).
- Rationale: Eliminates psmux keepalive across the review window for all fix cycles. Gives task 30 a single uniform fix interface. The per-batch warm-session resume added complexity without clear benefit — the plan file and review file are sufficient context for a targeted fixer.
- Rejected: Holistic only — would leave per-batch with warm-session resume, not achieving the infrastructure simplification.

### Escalation: stuck_type: logic for plan conflicts

- Decision: When a review finding contradicts the plan, the fixer reports `stuck_type: logic` with `reason: "plan conflict: <finding title>"`.
- Rationale: Reuses existing stuck machinery. Mill-go already surfaces logic-stuck to the user with options (edit plan / skip / block). No new mill-go code needed.
- Rejected: New `stuck_type: conflict` — would require mill-go changes and a new routing branch for marginal gain.

### Model config: roles.fixer.model

- Decision: New `roles.fixer.model` key in config, default `haiku`. The fixer resolves the model via `_reviewers.resolve(registry, model_name)`, same as the implementer.
- Rationale: Follows existing pattern (implementer, reviewer all use named registry entries). Operator can override per-hub in `config.local.yaml`.
- Rejected: Hard-coded Haiku — inflexible; rejected per user requirement.
- Rejected: Reuse `roles.implementer.model` — fixer and implementer have different cost/quality tradeoffs.

### Script: single millpy-fix.py with --scope flag

- Decision: Single `millpy-fix.py --scope batch|holistic [--batch-name NAME] --review-file PATH --round N`.
- Rationale: Unified CLI for task 30. Shared config loading, model resolution, and status transition logic. `--batch-name` required when `--scope batch`.
- Rejected: Two separate scripts (`millpy-fix-batch.py` / `millpy-fix-holistic.py`) — more files, duplicated boilerplate.

### Templates: two separate files

- Decision: `fixer-batch-brief.md` and `fixer-holistic-brief.md` — separate templates.
- Rationale: Contexts differ meaningfully. Batch fixer gets: one batch plan file + verify command. Holistic fixer gets: all batch plan files + verify commands for all batches. A shared template with optional sections would be harder to maintain.
- Rejected: One shared template with conditional sections — complex rendering, harder for mill-plan to read.

### Delete --resume code from millpy-implement.py

- Decision: Remove the `--resume` branch entirely. Delete `implementer-fix.md` template.
- Rationale: Dead code once mill-go switches to `millpy-fix.py`. Clean break.
- Rejected: Leave dead code with a comment — introduces confusion about whether the path is still valid.

### Psmux cleanup timing for per-batch

- Decision: The per-batch psmux cleanup block is invoked right after per-batch implementation completes (state transitions to `reviewing`), before review dispatch. No cleanup at fix dispatch (no session to clean up).
- Rationale: With cold-start Haiku fixer, the warm session is no longer needed after implementation. Cleaning up immediately removes keepalive requirement. At APPROVE, the session was already cleaned up.
- Rejected: Keep today's timing (cleanup at APPROVE/blocked/done) — session kept alive unnecessarily through review.

## Technical context

### Current scripts and their fate

| Script | Fate |
|---|---|
| `millpy-implement.py` | Keep; remove `--resume` branch only |
| `millpy-implement-holistic.py` | Delete; replaced by `millpy-fix.py --scope holistic` |
| `millpy-fix.py` | New |

### Current templates and their fate

| Template | Fate |
|---|---|
| `implementer-brief.md` | Keep (initial batch dispatch, unchanged) |
| `implementer-fix.md` | Delete (used only by the deleted --resume branch) |
| `implementer-holistic-brief.md` | Delete; replaced by `fixer-holistic-brief.md` |
| `fixer-batch-brief.md` | New |
| `fixer-holistic-brief.md` | New |

### millpy-fix.py structure

The script must:
1. Parse args: `--scope batch|holistic`, `--batch-name NAME` (required if scope=batch), `--review-file PATH`, `--round N`
2. Resolve git root, wiki path, slug, config
3. Resolve model: `cfg["roles"]["fixer"]["model"]` → `_reviewers.resolve(registry, model_name)` → `impl_model`, `impl_effort`
4. For scope=batch: read batch entry from status.md, resolve batch plan file path from `_mill/plan/`
5. Set status transition:
   - batch: `_status.set_batch_fields(status_path, batch_name, {"state": "fixing", "review_round": round, "review_file": str(review_file)})` + `_status.append_phase(status_path, f"fixing-{batch_name}-r{round}", ...)`
   - holistic: `_status.append_phase(status_path, "holistic-fixing", ...)`
6. `git add status_path review_file_arg && git commit -m "mill-go: fixing <scope> <batch_name|holistic> round {round}"` + push
7. Render template → prompt_text
8. `_implementer_claude.run(prompt_text, model=impl_model, effort=impl_effort, session_id=session_id, resume=False, cwd=project_root, timeout=timeout)`
9. `_forward_output(output, project_root, session_id=session_id)`

Follows `millpy-implement-holistic.py` closely. The batch variant adds batch-specific status fields (same logic as the deleted `--resume` branch in `millpy-implement.py`).

### Key imports already available

- `_implementer_claude`, `_llm_claude`, `_marker`, `_paths`, `_plan_dag`, `_render`, `_review_common`, `_reviewers`, `_status`, `_timestamp`, `_subprocess_util`
- `_implementer_common._forward_output`

### fixer-batch-brief.md tokens

```
<TASK_TITLE>, <SLUG>, <BATCH_NAME>, <BATCH_FILE>, <OVERVIEW_FILE>,
<REVIEW_FILE>, <PROJECT_ROOT>, <WIKI_PATH>, <SESSION_ID>, <ROUND>, <SELF_FIX_ROUNDS>
```

Content: load `mill-receiving-review` before reading findings; apply findings; escalate plan conflicts via `stuck_type: logic`; run only this batch's verify command; emit JSON report.

### fixer-holistic-brief.md tokens

```
<TASK_TITLE>, <SLUG>, <OVERVIEW_FILE>, <REVIEW_FILE>, <PROJECT_ROOT>,
<WIKI_PATH>, <SESSION_ID>, <ROUND>, <SELF_FIX_ROUNDS>, <BATCH_FILES>
```

Content: same as fixer-batch-brief.md but runs ALL batch verify commands after fixing. No `<BATCH_SESSION_IDS>` token (removed — no warm sessions, no IDs needed).

### mill-go SKILL.md changes

Two sections update:

**Per-batch fix dispatch (step 5 of the implement-review-fix loop):**
```bash
# Before:
millpy-implement.py <batch_name> --resume --round <N> --review-file <path>
# After:
millpy-fix.py --scope batch --batch-name <batch_name> --review-file <path> --round <N>
```

**Per-batch psmux cleanup timing:** Cleanup block moves from APPROVE/blocked/done to right after implementation completes (immediately before `state → reviewing`). Remove cleanup call from fix dispatch (no session to clean up).

**Holistic fix dispatch (step 5 of holistic loop):**
```bash
# Before:
millpy-implement-holistic.py --review-file <path> --round <H>
# After:
millpy-fix.py --scope holistic --review-file <path> --round <H>
```

Holistic cleanup block: remains in place (psmux session from Haiku fixer still needs cleanup if `via_psmux: true`). The `session_id` returned in the JSON report is used for cleanup, same as today.

**mill-go resume section:** Update the `fixing` sub-case for per-batch from `millpy-implement.py --resume` to `millpy-fix.py --scope batch`.

### config.yaml additions

```yaml
roles:
  fixer:
    model: haiku
```

Add to both `plugins/mill/templates/mill-config.yaml` (hub template) and `wiki/config.yaml`.

`SELF_FIX_ROUNDS` is read from `roles.implementer.self_fix_rounds` (same key as `millpy-implement-holistic.py` uses today). No new `roles.fixer.self_fix_rounds` key — cross-role reuse is intentional.

### Reviewers registry

`haiku` must be a valid entry in `reviewers.yaml`. Confirm it exists before writing the plan.

## Constraints

No CONSTRAINTS.md found at hub root.

- All Python output must be ASCII-only (`_log()` / `print()` — no em-dashes, no Unicode).
- Scripts in `plugins/mill/scripts/` are flat Python (no submodules). No new subdirectory.
- Config reads use deep-merge of `wiki/config.yaml` + `.millhouse/config.local.yaml` via `_config.load_config`.
- `wiki/config.yaml` is a shared resource: any schema change must be backwards-compatible OR coordinated with all running worktrees (per Home.md warning).
- Adding a new `roles.fixer` block is additive — no existing key is removed — so backwards compat is automatic.

## Testing

### test-millpy-fix.py (unit tests)

Follow the pattern of existing unit tests in `plugins/mill/unit_tests/`: in-memory or tempfile fixtures, no real git or LLM.

Key scenarios to cover:

**Batch scope:**
- Missing `--batch-name` → exits 1 with message
- `--batch-name` not in status.md → exits 1
- Review file not found → exits 1
- Happy path: correct status transitions written, correct template rendered, correct args to `_implementer_claude.run`
- `resume=False` is always passed (never True)

**Holistic scope:**
- Missing review file → exits 1
- Missing `plan/00-overview.md` → exits 1
- Happy path: correct phase appended, correct template rendered, `BATCH_SESSION_IDS` token absent from prompt

**Both scopes:**
- `stuck_type: logic` from implementer → forwarded as-is (no retry in the script itself)
- `LLMError` → synthetic stuck JSON on stdout, exit 1

## Q&A log

- **Q:** Scope — holistic only or both fix cycles? **A:** Both per-batch AND holistic.
- **Q:** Psmux config flag for optional keep-alive? **A:** No flag now — always cold-start fixer. Can be added later if needed.
- **Q:** Escalation for plan-conflicting findings? **A:** `stuck_type: logic` with reason "plan conflict: <finding>". Reuse existing stuck machinery.
- **Q:** Model config: new key or reuse implementer? **A:** New `roles.fixer.model`, default `haiku`. Never hard-coded.
- **Q:** Script structure? **A:** Single `millpy-fix.py --scope batch|holistic`.
- **Q:** Templates? **A:** Two separate: `fixer-batch-brief.md` + `fixer-holistic-brief.md`.
- **Q:** Delete `--resume` from `millpy-implement.py`? **A:** Yes. Delete that branch and `implementer-fix.md` template.
- **Q:** Unit tests? **A:** Yes, `test-millpy-fix.py` covering batch + holistic happy paths and error cases.
