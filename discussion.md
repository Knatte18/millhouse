# Discussion: 14 (D) — Holistic-fix agent for cross-batch funn (conflicts with 15)

```yaml
task: 14 (D) — Holistic-fix agent for cross-batch funn (conflicts with 15)
slug: holistic-fix-agent
status: discussing
parent: main
```

## Problem

Holistic code review findings are cross-batch by nature — they surface issues that span files owned by different batch implementers (e.g. "three files in three batches duplicate the same helper", "missing test for a helper created in batch 08"). No single batch implementer session owns the fix.

The current mill-go SKILL.md has a stub for holistic REQUEST_CHANGES that calls `_implementer_sonnet.run(prompt_text, ...)` directly, with no description of how `prompt_text` is built and no CLI script or template to back it. In practice this means the Builder would have to construct the prompt inline — a "lean Builder" violation, and a path that's untested. The per-batch dispatch (`millpy-implement.py`) is fully implemented with commit/push atomicity, template rendering, and unit tests; the holistic fix path needs the same treatment.

## Scope

**In:**
- New CLI script `plugins/mill/scripts/millpy-implement-holistic.py` — analogous to `millpy-implement.py` but for cross-batch holistic fix dispatch.
- New template `plugins/mill/templates/implementer-holistic-brief.md` — prompt for the holistic implementer session.
- Updated `plugins/mill/skills/mill-go/SKILL.md` — Holistic code review section rewritten to call the new CLI instead of `_implementer_sonnet.run()` inline.
- New config key `review.code.holistic_rounds` in `wiki/config.yaml` (default: 1).
- Shared helper `plugins/mill/scripts/_implementer_common.py` — extract `_forward_output()` from `millpy-implement.py` to avoid duplicating the regex extraction logic; update `millpy-implement.py` to import from it.
- Unit tests `plugins/mill/unit_tests/test-millpy-implement-holistic.py`.
- Update `test-millpy-implement.py` to reflect the `_forward_output` relocation.

**Out:**
- Task 15 (implementer self-spawner reviewer in warm session) — a separate task that conflicts with this one by design; the two are complementary alternatives for different loop types.
- Per-batch implement flow — no changes to `millpy-implement.py` beyond extracting `_forward_output`.
- Holistic review invocation — `millpy-review-code.py` and `_review_code.py` are unchanged; only the *fix dispatch* changes.
- Parallel batch execution.
- Changes to `_status.py`, `_plan_dag.py`, or other shared helpers (consumed but not changed).

## Decisions

### cli-over-inline

- **Decision:** Holistic fix is dispatched via a new `millpy-implement-holistic.py` CLI script, not via an inline `_implementer_sonnet.run()` call in the SKILL.
- **Rationale:** Keeps the Builder lean (no prompt construction in the skill), matches the per-batch pattern, makes the dispatch testable and auditable independently of mill-go.
- **Rejected:** Inline `_implementer_sonnet.run()` with prompt built in the skill — violates lean-Builder principle, untestable in isolation.

### max-holistic-rounds

- **Decision:** New config key `review.code.holistic_rounds` (integer, default 1). Mill-go reads it and applies the same review-fix loop structure as per-batch, but with this separate budget.
- **Rationale:** Proposal #31 specifies "max 1 dispatch to avoid loops." Cross-batch fix cycles are expensive (full-repo scope) and hard to diagnose in repeated rounds. Default 1 enforces that; user can override.
- **Rejected:** Reusing `review.code.rounds` — conflates per-batch and holistic budgets. Hardcoding 1 — inflexible.

### verify-all-batches

- **Decision:** After holistic fix, the implementer runs `verify:` from ALL batch frontmatters (in plan order). Batches with `verify: null` are skipped.
- **Rationale:** Cross-batch edits can break any batch's verify command. Running all of them catches regressions the implementer may not have anticipated.
- **Rejected:** Run only verify commands for "affected" batches derived from parsing review findings — requires fragile review-file parsing in the template, and the holistic implementer cannot reliably know which batches' verify commands are sensitive to its changes.

### session-id-ephemeral

- **Decision:** The CLI generates a fresh UUID per dispatch, injects it into the template as `<SESSION_ID>`, and does NOT persist it to status.md. Holistic is always cold-start; there is no `--resume` path for holistic.
- **Rationale:** The only reason per-batch stores `implementer_session` in status.md is to support `--resume`. Holistic never resumes, so storing the ID adds schema complexity with no use.
- **Rejected:** Adding `holistic_session:` as a top-level status.md field — adds a field to the status schema that serves no operational purpose.

### holistic-brief-inputs

- **Decision:** The holistic brief receives: (1) the holistic review file path, (2) `00-overview.md` path, (3) a list of all batch plan file paths (so the implementer knows which files to read and which verify commands to run), (4) the list of all `implementer_session_id`s from status.md as read-only context.
- **Rationale:** This matches the spec in issue #31. Session IDs are included for context only — the implementer must not use `--resume` with them; the brief must make this explicit.
- **Rejected:** Omitting session IDs — the spec listed them; they give the implementer traceability context for the work already done.

### forward-output-extraction

- **Decision:** Extract `_forward_output()` from `millpy-implement.py` into a new `_implementer_common.py` helper. Both `millpy-implement.py` and `millpy-implement-holistic.py` import from it.
- **Rationale:** `_forward_output()` contains non-trivial regex parsing logic. Duplicating it creates two copies that can diverge silently. This is a factoring of existing logic to support the new file, not a speculative abstraction.
- **Rejected:** Duplicate `_forward_output` in both scripts — creates a maintenance hazard for non-trivial regex code.

### status-tracking

- **Decision:** Holistic state is tracked only via `_status.append_phase()` with dedicated phase names (`holistic-reviewing`, `holistic-fixing`, `holistic-approved`). No new batch entry, no new top-level YAML field.
- **Rationale:** This is already described in the SKILL.md and avoids schema churn. The timeline entries are sufficient to understand holistic state on resume.
- **Rejected:** Adding a pseudo-batch entry named "holistic" — would require changes to `_status.init_batches()` and `_status.set_batch_field()`.

## Technical context

### Key files to read before implementing

- `plugins/mill/scripts/millpy-implement.py` — canonical reference; the new script mirrors its structure (arg parsing, common setup, git commit+push, template render, `_implementer_sonnet.run`, `_forward_output`).
- `plugins/mill/scripts/_implementer_sonnet.py` — `run(prompt_text, *, session_id, resume, cwd, timeout) -> tuple[str, str]`.
- `plugins/mill/scripts/_status.py` — `read_batches(status_path)` returns list of dicts with `name`, `implementer_session`, etc.; `append_phase(status_path, phase, timestamp)`; `read_branch(status_path, cfg, slug)`.
- `plugins/mill/scripts/_plan_dag.py` — `extract_batch_index(overview_text) -> list[dict]`, each entry has `name`, `file`, `depends-on`, `verify` fields.
- `plugins/mill/templates/implementer-brief.md` — reference template; note the `<SESSION_ID>` injection pattern and the exact JSON report shape the implementer must emit.
- `plugins/mill/skills/mill-go/SKILL.md` — lines 155–163 is the stub to replace.
- `plugins/mill/unit_tests/test-millpy-implement.py` — test fixture and mock setup patterns to mirror.

### CLI contract for `millpy-implement-holistic.py`

```
Usage: millpy-implement-holistic.py --review-file PATH [--round N]

Flags:
  --review-file PATH   abs or relative path to holistic review output (required)
  --round N            dispatch round number (int, default 1; passed to template for context)

Exit codes:
  0 — implementer ran; JSON report on stdout (success or stuck)
  1 — pre-launch error (bad config, missing slug, git failure, missing file); message on stderr, no JSON on stdout
```

No positional batch name — holistic operates on the whole worktree. No `--resume` flag — holistic is always cold-start.

### Template tokens for `implementer-holistic-brief.md`

```
<TASK_TITLE>          — human task title
<SLUG>                — task slug
<OVERVIEW_FILE>       — abs path to plan/00-overview.md
<REVIEW_FILE>         — abs path to the holistic review file
<PROJECT_ROOT>        — abs path to worktree root (cwd for git/verify commands)
<WIKI_PATH>           — abs path to wiki clone
<SESSION_ID>          — fresh UUID; implementer must copy verbatim into JSON report
<ROUND>               — dispatch round number (integer string)
<SELF_FIX_ROUNDS>     — from config review.code.self_fix_rounds
<BATCH_FILES>         — newline-separated list of abs paths to all batch plan files
<BATCH_SESSION_IDS>   — YAML-like list of "name: session_id" pairs (one per line, from status.md); for context only, NOT for --resume
```

`<BATCH_FILES>` and `<BATCH_SESSION_IDS>` are multi-line tokens. The `_render.render()` function does verbatim substitution, so the template must include these as a fenced block or bullet list. See `_render.py` for how substitution works before writing the template.

### Status.md phase sequence for holistic

```
holistic-reviewing    — holistic review round started (N)
holistic-fixing       — implementer dispatched for holistic fix (round N)
holistic-approved     — holistic review returned APPROVE
```

Round N tracks as the mill-go loop counter (same variable as `N` in the per-batch section). Phase names do NOT embed the round number (unlike per-batch `reviewing-{batch}-rN`) because there is no batch name to embed.

### SKILL.md rewrite scope

Replace lines 155–163 (the entire `## Holistic code review` section). The new section must:
1. Read `review.code.holistic_rounds` (not `review.code.rounds`).
2. Invoke `millpy-implement-holistic.py --review-file <path> --round <N>` via Bash (not via Python helper).
3. Parse JSON from stdout with same pattern as per-batch implement.
4. Use `_status.append_phase` for all state transitions (no `set_batch_field`).
5. Document crash-recovery: scan `reviews/` for an existing `*-code-review-holistic-r{N}.md` before firing the review CLI (mirrors per-batch crash-recovery check).
6. On rounds-exhausted: surface to user with blocked-task halt (NOT blocked-batch — holistic failure blocks the whole task, not a single batch).
7. Inline the `_implementer_sonnet.run` signature entry can be removed (the CLI handles it).

### `_render.py` multi-line token behaviour

Check `plugins/mill/scripts/_render.py` before writing the template — confirm whether `_render.render()` handles tokens whose replacement value contains newlines. If it performs verbatim string replace, multi-line values work as-is. If it has line-oriented logic, the template design for `<BATCH_FILES>` and `<BATCH_SESSION_IDS>` may need adjustment.

## Constraints

No `CONSTRAINTS.md` found at the hub root. Constraints derived from CLAUDE.md and the codebase:

- **`${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths in SKILL.md.** The new CLI is invoked from the skill as `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement-holistic.py"` — never hardcode the source-tree path.
- **Junctions are never code paths.** The new script resolves paths via `_paths.resolve_git_root()` and `_paths.resolve_wiki_path()`, never via `.millhouse/wiki` or `.others`.
- **Working state on the task branch.** The CLI must `git add status.md && git commit` (and push) after each state mutation — same discipline as `millpy-implement.py`.
- **Unit tests use in-memory fixtures.** No real git, no real LLM. All subprocess calls and `_implementer_sonnet.run` patched in `setUp`. See `test-millpy-implement.py` for the pattern.
- **No `if __name__ == "__main__": smoke-test` blocks in helper files.** Only CLIs have `main()` + `if __name__ == "__main__":`.

## Testing

### `_implementer_common.py`

`_forward_output()` is already covered by `TestForwardOutput` in `test-millpy-implement.py`. After extraction, update that test to import from `_implementer_common` (or load the function via the module's imported reference). No new test file needed for `_implementer_common` — the existing class covers it.

### `test-millpy-implement-holistic.py`

Mirror `test-millpy-implement.py` structure. Required cases:

1. **Fresh dispatch success** — `--review-file <path>` → success JSON on stdout, `holistic-reviewing` phase in timeline, then `holistic-fixing` phase after dispatch, `holistic-approved` after APPROVE (note: the CLI does not set approved itself; that's the Builder's job after re-running the review — but the test should verify phases up to dispatch).
2. **LLMError from `_implementer_sonnet.run`** → exit 1, stuck/transient JSON on stdout.
3. **No JSON from implementer output** → exit 0, stuck/logic JSON on stdout.
4. **Missing `--review-file`** → exit 1, no JSON.
5. **Review file path does not exist** → exit 1, no JSON.
6. **Verify token rendering** — confirm `<BATCH_FILES>` and `<BATCH_SESSION_IDS>` are injected correctly into the rendered prompt (inspect the `prompt_text` argument to `_implementer_sonnet.run`).

### `test-millpy-implement.py` update

After extracting `_forward_output` to `_implementer_common.py`, the `TestForwardOutput` class must still call `_forward_output` correctly. The simplest fix: load it via `millpy_implement._implementer_common._forward_output` or re-import `_implementer_common` directly. Confirm the import path in the updated test.

## Q&A log

- **Q:** Max holistic-fix rounds — configurable or fixed? **A:** Configurable, new key `review.code.holistic_rounds`, default 1 (per proposal #31 rationale).
- **Q:** Verify after fix — all batches or only affected? **A:** All batches with non-null `verify:` commands, run in plan order.
- **Q:** Session ID — store in status.md? **A:** No, ephemeral; holistic never resumes so no stored ID is needed.
- **Q:** Template inputs — include all `implementer_session_id`s? **A:** Yes, as read-only context (`<BATCH_SESSION_IDS>` token). Brief must explicitly say they are NOT for `--resume`.
- **Q:** CLI name? **A:** `millpy-implement-holistic.py`.
- **Q:** Extract `_forward_output` or duplicate? **A:** Extract to `_implementer_common.py`.
- **Q:** Task 15 conflict — design dependency? **A:** No dependency. Task 15 changes warm per-batch self-review; holistic is always cold-start and cross-batch. Design independently.
