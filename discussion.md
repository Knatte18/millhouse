# Discussion: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8)

```yaml
task: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8)
slug: dispatch-cli-and-resume
status: discussing
parent: main
```

## Problem

The Builder in mill-go orchestrates per-batch implementation by manually executing a 10-step sequence for every batch: look up the batch entry, resolve paths, read config, render the implementer brief, capture `start_sha`, generate a `session_id`, write three `_status.set_batch_field` calls, commit on the task branch, spawn the implementer, and parse the JSON report. There is no CLI that encapsulates this. Builders have been writing one-off orchestration scripts in `.scratch/` or inlining all 10 steps as tool calls — both are wrong and produce untested, non-shared code.

The fix-cycle is additionally broken when the Builder uses `Agent` tool dispatch for the initial implementation pass. Agent sessions terminate after returning their result; `SendMessage` cannot reopen a completed agent. This means the warm-session resume (`claude --resume <session_id>`) that `_implementer_sonnet.run` supports is unavailable, and fix cycles must cold-start — re-reading all context from scratch, losing design-decision memory, and roughly doubling per-batch token cost when reviews return `REQUEST_CHANGES`.

## Scope

**In:**
- New script `plugins/mill/scripts/millpy-implement.py` that encapsulates the full initial-dispatch and fix-cycle-resume paths for a single batch
- New template `plugins/mill/templates/implementer-fix.md` for the fix-cycle resume prompt
- Updated `plugins/mill/skills/mill-go/SKILL.md`: replace the 10-step initial-dispatch block and the inline fix-cycle resume block with single `millpy-implement.py` calls
- Unit tests in `plugins/mill/unit_tests/test-millpy-implement.py`

**Out:**
- Holistic-review fix-dispatch path (separate follow-up)
- Agent tool as an implementer dispatch mechanism (dropped entirely; no hybrid mode)
- Changes to any other skill or CLI beyond mill-go's SKILL.md

## Decisions

### script-name

- **Decision:** `millpy-implement.py`
- **Rationale:** Mirrors the existing naming convention (`millpy-review-code.py`, `millpy-review-plan.py`, `millpy-review-discussion.py`). Name is short and unambiguous: "implement this batch."
- **Rejected:** `mill-go-batch.py` (emphasises the mill-go association at the cost of clarity; CLI is a reusable building block, not a mill-go-specific detail).

### cli-atomicity

- **Decision:** The CLI owns the full operation — reads config and plan, renders the prompt, sets batch state, generates `session_id`, commits and pushes on the task branch, runs the implementer, and prints the JSON result on stdout. The Builder does zero state-writing around this call.
- **Rationale:** The point of the CLI is to make the Builder lean. Splitting state mutations across Builder + CLI defeats that. Full atomicity also means tests cover the real execution path end-to-end.
- **Rejected:** CLI wraps only the implementer invocation (Builder still does set_batch_field + commit). Builder would remain non-lean and any test coverage gap on the state mutations would survive.

### drop-agent-dispatch

- **Decision:** Agent tool is removed as an implementer dispatch mechanism. `millpy-implement.py` always uses `_implementer_sonnet.run` (CLI subprocess), which supports `--session-id` and `--resume` natively.
- **Rationale:** Agent dispatch has no resume path. Once a batch returns `REQUEST_CHANGES`, a fresh Agent cold-start loses all warm-session context, re-reads the entire codebase, and roughly doubles token cost. The ~2x speed advantage of Agent for initial passes is outweighed by this when fix cycles are needed — and fix cycles happen regularly. The timing experiment data (`.scratch/timings.md`) shows Agent wins only when reviews approve on r1.
- **Rejected:** Hybrid (Agent initial + CLI fix-cycle): adds code paths for a marginal speedup on the r1-approve case only; B path adds complexity with no principled justification.

### fix-prompt-template

- **Decision:** New template `plugins/mill/templates/implementer-fix.md` for the fix-cycle resume prompt.
- **Rationale:** Consistent with `implementer-brief.md`. Templates are version-controlled and editable without touching Python. The fix prompt needs tokens (`<REVIEW_FILE>`, `<BATCH_FILE>`, `<SELF_FIX_ROUNDS>`); a template is the right home.
- **Rejected:** Hardcode the fix message in the CLI. Short now, but difficult to update without touching Python and re-testing.

### stdout-contract

- **Decision:** The CLI forwards the implementer's JSON report verbatim on stdout. No envelope wrapper.
- **Rationale:** The Builder already parses the implementer's JSON shape (`{"status":"success|stuck",...}`). Adding a wrapper creates a new contract layer for no consumer benefit. On parse failure (malformed/missing JSON from implementer), the CLI exits non-zero and prints a synthetic stuck JSON to stdout.
- **Rejected:** Wrap in `{"type":"implement","batch":"...","round":N,...}` envelope to mirror review-code.py. Adds a translation layer in the Builder for something that's already well-typed.

### session-error-handling

- **Decision:** On `LLMSessionError` (expired session during `--resume`), exit non-zero with JSON: `{"status":"stuck","stuck_type":"transient","reason":"session expired"}`. The Builder handles the fallback.
- **Rationale:** The Builder already has a one-retry policy for `stuck_type: transient`. Routing expired sessions through that path keeps error handling in one place. Auto-retry inside the CLI would hide the event from the Builder's state machine.
- **Rejected:** CLI auto-falls-back to a fresh session (no `--resume`) with a stderr warning. Breaks the Builder's crash-recovery check which uses `implementer_session` to correlate session IDs.

### crash-recovery-initial

- **Decision:** If the CLI is called for a batch already in state `running`, it treats it as a restart: generates a new `session_id`, overwrites the `running` state fields, and re-commits.
- **Rationale:** Consistent with mill-go's one-retry-on-transient policy. A crash mid-dispatch leaves the batch in `running` — forcing a manual reset to `pending` before restarting is unnecessary friction.
- **Rejected:** Error if batch is already `running`. Too strict; the common crash-recovery case should not require operator intervention.

### builder-lock

- **Decision:** `millpy-implement.py` does not acquire or check the builder lock. The lock is mill-go's entry concern.
- **Rationale:** The CLI is a building block invoked from within the lock. Checking it inside the CLI would be redundant and would couple the CLI to mill-go's orchestration model, reducing reusability.
- **Rejected:** CLI refuses to run without the lock. Belt-and-suspenders, but the lock check belongs at the orchestrator boundary.

### task-branch-push

- **Decision:** The CLI pushes to `origin/<task-branch>` after each state-change commit (start batch, fixing).
- **Rationale:** The task branch is an active working branch. Pushing after discrete state transitions provides crash-recovery visibility and matches the expectation for targeted, purposeful operations. The "no push" annotation in the existing mill-go skill applies to wiki commits only.
- **Rejected:** Commit only, no push. Withholding the push mid-task is conservative with no clear benefit — mill-merge is not the only legitimate moment to push the task branch.

### implementer-timeout-config

- **Decision:** Read `llm.implementer_timeout` from merged config (wiki `config.yaml` + `.millhouse/config.local.yaml`) if present; fall back to `run_implementer`'s 1800s default.
- **Rationale:** Consistent with how other config keys are consumed. Operators running slow or large batches can tune the timeout without editing code.
- **Rejected:** Always use the code default. Inflexible; the config system exists for exactly this.

### mill-go-skill-update

- **Decision:** Update `mill-go/SKILL.md` to replace both the initial-dispatch block (the 10-step sequence under "1. Implement") and the fix-cycle resume block (under "REQUEST_CHANGES" in the code review loop) with single `millpy-implement.py` subprocess calls. Verdict parsing logic stays in the skill.
- **Rationale:** The skill describes what the Builder does. After the CLI exists, the Builder's action is one subprocess call — the skill should say that and no more. Leaving the old steps in the skill alongside the new CLI call creates a divergent dual-mode description that will confuse future sessions.
- **Rejected:** Update only the initial-dispatch block. Leaves the fix-cycle resume block inline, meaning the Builder may still do ad-hoc resume logic on that path.

## Technical context

### Existing helpers the CLI must use

| Helper | Purpose |
|---|---|
| `_paths.resolve_git_root()` + `_paths.resolve_wiki_path(git_root)` | Locate project root and wiki |
| `_review_common.load_config(wiki_path, mill_dir)` | Deep-merge wiki + local config |
| `_active.read_slug(Path(".millhouse"))` | Read task slug |
| `_status.read_full(status_path)` | Read task_title from top yaml block |
| `_status.read_batches(status_path)` | Read existing batch state for crash-recovery check |
| `_status.set_batch_field(status_path, name, key, value)` | Mutate batch state fields |
| `_plan_dag.extract_batch_index(overview_text)` | Parse batch entries from 00-overview.md |
| `_render.render(template_path, values)` | Render implementer-brief.md and implementer-fix.md |
| `_implementer_sonnet.run(prompt, *, session_id, resume, cwd)` | Spawn the implementer subprocess |
| `_timestamp.now_utc_iso()` | Timestamps for status mutations |
| `_subprocess_util.run(argv, ...)` | Used internally by `_llm_claude`; not called directly |

### Batch state machine (relevant transitions)

- `pending` → `running`: initial dispatch (set state, start_sha, implementer_session + commit + push)
- `running` → `reviewing`: set by mill-go after the CLI returns success (not the CLI's job)
- `reviewing` → `fixing`: fix-cycle resume (set state, review_round, review_file + commit + push)
- Any → `running` (on crash-recovery restart): overwrite running-state fields, new session_id

Allowed fields per `_status._BATCH_ALLOWED_KEYS`: `state`, `implementer_session`, `commit_sha`, `start_sha`, `review_round`, `review_file`, `blocked_reason`.

### Template tokens

**`implementer-brief.md`** (already exists):
`TASK_TITLE`, `SLUG`, `BATCH_NAME`, `BATCH_FILE`, `OVERVIEW_FILE`, `PROJECT_ROOT`, `WIKI_PATH`, `SELF_FIX_ROUNDS`, `ROUND`

**`implementer-fix.md`** (to be created):
`REVIEW_FILE`, `BATCH_FILE`, `SELF_FIX_ROUNDS`

The fix prompt is short: load `mill-receiving-review`, read the review file, apply fixes per VERIFY/HARM CHECK/FIX or PUSH BACK decision tree, re-run `verify:` from batch frontmatter, report the same JSON shape.

### CLI surface

```
millpy-implement.py <batch_name>
millpy-implement.py <batch_name> --resume --round N --review-file <abs-path>
```

Flags:
- `<batch_name>` — positional, required. Must match a name in `plan/00-overview.md`'s Batch Index.
- `--resume` — triggers the fix-cycle path. Requires `--round` and `--review-file`.
- `--round N` — fix-cycle round number; injected into fix prompt as context; defaults to 1.
- `--review-file <abs-path>` — absolute path to the review file the implementer must read.

Exit codes:
- `0` — implementer returned JSON (success or stuck); JSON on stdout
- `1` — pre-launch error (missing plan, batch not found, bad args, etc.); message on stderr

### `_review_common.load_config` signature

```python
load_config(wiki_root: Path, mill_dir: Path) -> dict
```

Returns the deep-merged config dict. Key paths used by the CLI:
- `cfg["review"]["code"]["self_fix_rounds"]` → `<SELF_FIX_ROUNDS>` token
- `cfg.get("llm", {}).get("implementer_timeout", 1800)` → timeout for `run_implementer`

### Where git operations run

`_implementer_sonnet.run` accepts `cwd=<project_root>`. The git operations in the CLI (start_sha, commit, push) run via `subprocess` against `project_root` (= `Path.cwd()`). The task branch is inferred from `status.md`'s `branch:` field via `_status.read_branch(status_path, cfg=cfg, slug=slug)`.

### Mill-go SKILL.md change — what gets replaced

Under **"### 1. Implement"**: the bullets from "Resolve the batch's file path" through "Spawn implementer: `_implementer_sonnet.run(...)`" are replaced by a single `millpy-implement.py <batch_name>` call.

Under **"### 3. Code Review loop → REQUEST_CHANGES"**: the "Resume the implementer session with a new user message... Spawn via `_implementer_sonnet.run(fix_prompt, session_id=session_id, resume=True, ...)`" block is replaced by `millpy-implement.py <batch_name> --resume --round N --review-file <abs-path>`.

The `## Principles` note "Implementer owns receive-review" stays unchanged.

## Testing

### `test-millpy-implement.py`

Test `main()` in-process (same importlib pattern as `test-millpy-validate-plan.py`). Use `tempfile.TemporaryDirectory` for a fake worktree with:
- `plan/00-overview.md` with a Batch Index containing at least one batch
- `status.md` with the top yaml block and a `## Batches` section
- `.millhouse/` dir with a minimal `config.local.yaml`

Mock at the module level (via `unittest.mock.patch`):
- `_implementer_sonnet.run` — return a synthetic `(last_line_json_string, "fake-session-id")`
- `_wiki.sync_pull` (if the CLI calls it — it doesn't; it calls `_paths` helpers directly)
- `subprocess.run` / `_subprocess_util.run` for the git operations (start_sha, commit, push)
- `uuid.uuid4` to get a deterministic session_id in assertions

**Scenarios to cover:**

1. **Initial dispatch — success**: batch in `pending` state → CLI generates session_id, sets `running`, commits, pushes, calls `run`, forwards `{"status":"success",...}` on stdout. Exit 0.
2. **Initial dispatch — crash-recovery (batch already `running`)**: CLI generates new session_id, overwrites fields, re-commits, re-pushes, calls `run`. Exit 0.
3. **Initial dispatch — implementer reports `stuck`**: CLI exits 0, forwards the stuck JSON verbatim.
4. **Resume path — success**: `--resume --round 2 --review-file <path>` → reads `implementer_session` from status.md, sets state `fixing`, commits, pushes, calls `run` with `resume=True`. Exit 0.
5. **Resume path — `LLMSessionError`**: `run` raises `LLMSessionError` → CLI exits 1, stdout contains `{"status":"stuck","stuck_type":"transient","reason":"session expired"}`.
6. **Batch not found**: batch_name not in overview → stderr error, exit 1.
7. **Malformed / missing JSON from implementer**: implementer returns text with no valid JSON on last line → CLI exits 0, stdout is `{"status":"stuck","stuck_type":"logic","reason":"no structured report"}`.
8. **`--resume` without `--review-file`**: argparse error, exit 2.

No real git, no real LLM. All git subprocesses mocked.

## Q&A log

- **Q:** Script name — `millpy-implement.py` or `millpy-go-batch.py`? **A:** `millpy-implement.py`.
- **Q:** Should the CLI own ALL state mutations (set_batch_field, git commit, push)? **A:** Yes — fully atomic.
- **Q:** Drop Agent dispatch or keep hybrid mode? **A:** Drop entirely. With Agent dispatch we lose the resume ability — acceptable tradeoff.
- **Q:** Fix-prompt in a template or hardcoded? **A:** New template `implementer-fix.md`.
- **Q:** LLMSessionError on resume — synthetic JSON exit or auto-fallback? **A:** Synthetic stuck JSON, exit non-zero. Builder handles fallback.
- **Q:** CLI stdout — forward verbatim or wrap in envelope? **A:** Forward verbatim.
- **Q:** Mill-go SKILL.md — replace initial dispatch only or both dispatch and fix-cycle? **A:** Both.
- **Q:** Testing scope — unit only or also integration? **A:** Unit only.
- **Q:** Crash-recovery: allow restart if batch already `running`? **A:** Yes — generate new session_id, overwrite fields.
- **Q:** Builder lock — does CLI check it? **A:** No.
- **Q:** `implementer_timeout` from config? **A:** Yes, read `llm.implementer_timeout` from merged config.
- **Q:** Push after task-branch commits? **A:** Yes — commit and push. "No push" in mill-go skill applied to wiki commits only.
