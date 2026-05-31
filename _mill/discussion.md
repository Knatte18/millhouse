# Discussion: haiku-4-5 implementer reliability (hang + path mangle)

```yaml
task: haiku-4-5 implementer reliability (hang + path mangle)
slug: haiku-implementer-reliability
status: discussing
parent: main
```

## Problem

Two model-specific bugs observed exclusively with `roles.implementer.model: haiku` (i.e. `claude-haiku-4-5-20251001`). Sonnet and Opus implementers do not exhibit either. Bug 1: three successive batch-1 attempts each ran the haiku implementer CLI to the full 1800s timeout without producing JSON output, file writes, or commits — the bg-log showed only `WORKER START` until `Claude CLI timed out after 1800s`. Bug 2: on one run haiku materialised six files at the worktree root with underscore-flattened names (e.g. `plugins_mill_scripts_config.py` instead of `plugins/mill/scripts/_config.py`) and also edited two files outside the declared batch scope; none were committed, so the existing overstep guard never fired.

If haiku is to remain a supported implementer tier (cheap-tier dispatch, mass-batch, future local dispatch), both bugs need mitigation. The hang must produce a clear early signal rather than silently consuming 30 min; the path mangle must be both less likely to happen (brief fix) and reliably detected if it does (cleanliness check).

## Scope

**In:**
- `millpy-implement.py` — add brief-size guard (emit `stuck/transient` before LLM call if prompt exceeds threshold) and per-reviewer timeout override.
- `millpy-fix.py` — same per-reviewer timeout override (fixer also uses haiku).
- `plugins/mill/templates/mill-agents.yaml` — add optional `timeout:` field to the agent spec schema; set `timeout: 600` on `haiku`.
- `plugins/mill/scripts/_cleanliness.py` — add `compute_scope_violations(worktree)` that returns untracked files outside `_mill/`.
- `plugins/mill/scripts/_implementer_common.py` — call `compute_scope_violations` in `_forward_output`; include results in JSON output.
- `plugins/mill/templates/implementer-brief.md` — add explicit path-format reminder paragraph.
- `plugins/mill/unit_tests/test-cleanliness.py` — tests for `compute_scope_violations`.
- `plugins/mill/unit_tests/test-implementer-common.py` — tests for scope-violations field in `_forward_output` output.
- `plugins/mill/unit_tests/test-millpy-implement.py` — test for oversized-prompt → `stuck/transient`.
- `mill-config.yaml` (hub config) — add `llm.max_implementer_prompt_chars` default.

**Out:**
- No changes to `_llm_claude.py` or `_subprocess_util.py` — the per-reviewer timeout is consumed at the `millpy-implement.py` layer before the LLM call, and the brief-size guard fires before the subprocess is spawned.
- No root-cause investigation script for the hang — the defensive layers are sufficient without identifying the exact haiku stream-json issue.
- No changes to `mill-go` skill or its stuck-handling logic — `stuck/transient` from the brief-size guard is handled by the existing retry path.
- No changes to `_reviewers.py` validation — the `timeout` field is read via `impl_spec.get("timeout")` and unknown extra keys in the agent spec already emit a stderr warning rather than hard-failing.
- No change to `compute_new_dirt` — untracked-file detection is a separate function rather than a breaking change to the existing API.
- No change to the inferred-success path in `_forward_output` — scope violations are reported as an extra field alongside the existing status, not as a new `stuck_type`.

## Decisions

### per-reviewer timeout override via mill-agents.yaml

- Decision: Add an optional `timeout:` integer field to agent specs in `mill-agents.yaml`. In `millpy-implement.py` (and `millpy-fix.py`), resolve `timeout = impl_spec.get("timeout") or cfg.get("llm", {}).get("implementer_timeout", 1800)`. Set `timeout: 600` on the `haiku` entry in the plugin template.
- Rationale: haiku is faster than Sonnet when it works; 1800s is appropriate for Sonnet but silently wastes 30 min for haiku. A 600s timeout surfaces the hang as `stuck/transient` (retryable) in one-third of the time. Per-reviewer override keeps the config co-located with the model spec rather than duplicating it in `mill-config.yaml`.
- Rejected: A separate `llm.haiku_timeout` key in `mill-config.yaml` — splits the haiku config across two files.
- Rejected: No-progress monitor in `_subprocess_util` that kills on empty stdout — complex on Windows (the watchdog accumulates lines in a buffer; detecting "no new lines in N seconds" requires threading changes) and would affect all models.

### brief-size guard in millpy-implement.py

- Decision: After rendering `prompt_text` and before calling `_implementer_claude.run()`, check `len(prompt_text) > cfg.get("llm", {}).get("max_implementer_prompt_chars", 0)`. If the guard fires (and `max_implementer_prompt_chars > 0`), print `{"status": "stuck", "stuck_type": "transient", "reason": "brief exceeds max_implementer_prompt_chars (N chars)"}` and return 0. Default `0` means the guard is disabled unless explicitly configured. Add `max_implementer_prompt_chars: 0` to `mill-config.yaml` hub template at the `llm:` block.
- Rationale: haiku's effective context is 200K tokens (~800K chars). A batch brief embedding large file content can exceed this silently, causing the subprocess to hang. Character count is a cheap proxy that avoids a tokeniser dependency. The guard emits `stuck/transient` so mill-go retries; if the retry hits the same brief, the operator sees a repeated transient and can intervene.
- Rejected: Model-specific character limit in `mill-agents.yaml` (e.g. `max_prompt_chars: 800000` on haiku) — adds a second dimension to the agent spec before there's evidence the issue is actually brief size; the global config key is sufficient for now and can be per-reviewer if needed later.
- Rejected: Truncating the brief automatically — changes semantics (the implementer would receive an incomplete plan) and could cause correctness failures for any model.
- Same guard must be applied in `millpy-fix.py` (the fixer agent also uses haiku and renders a brief).

### scope-violations detection in _cleanliness.py + _forward_output

- Decision: Add `compute_scope_violations(worktree: Path) -> list[str]` to `_cleanliness.py`. It runs `git -C <worktree> status --porcelain --untracked-files=normal`, collects `?? ` lines, and returns those whose paths do NOT start with `_mill/`. In `_forward_output`, call this after the main status determination. If violations is non-empty, merge it into the JSON output as `"scope_violations": [...]`. For the inferred-success path specifically, if violations exist, downgrade the result to `{"status": "stuck", "stuck_type": "logic", "reason": "untracked files outside scope: ...", "scope_violations": [...]}`. For the explicit-JSON path (LLM-emitted JSON), add `scope_violations` as an extra field without changing `status`.
- Rationale: The path-mangle scenario (haiku writes 6 files at root, none committed) is invisible to `compute_new_dirt` which uses `--untracked-files=no`. `compute_scope_violations` uses `--untracked-files=normal` (ignores `.gitignore`d files automatically) and filters to files outside `_mill/`, which is the only writable per-batch directory. The function is separate rather than extending `compute_new_dirt` to avoid breaking its existing API and tests.
- Inferred-success downgrade: if haiku committed AND wrote untracked mangled files at root, the inferred-success path would otherwise report success. Downgrading to `stuck/logic` when violations exist is conservative but correct — if the implementer wrote outside scope, the operator must verify.
- Rejected: Extending `compute_new_dirt` to include untracked — breaks the API contract relied on by `test-cleanliness.py` (all cases assume tracked-only output).
- Rejected: Checking only in `millpy-implement.py` post-run — misses the fixer path (`millpy-fix.py` also calls `_forward_output`).

### brief path-format reminder

- Decision: Add a paragraph to `implementer-brief.md` under the existing `## Tools` section (or as a new `## Path format` section before `## Cross-worktree isolation`) that reads: "**File paths are POSIX-style relative paths from `<PROJECT_ROOT>`.** Never flatten path separators into underscores. `plugins/mill/scripts/_config.py` is a file at `plugins/mill/scripts/` named `_config.py` — not a file named `plugins_mill_scripts_config.py` at the worktree root. When in doubt, verify with `Read` before writing."
- Rationale: The mangle evidence (`plugins_mill_scripts__config.py` at root) is consistent with a tokenisation confusion where haiku treated `/` as a separator between path components and `_` as a naming prefix, then flattened the whole path. An explicit reminder with a concrete counterexample is low-risk (no code change) and cheap.
- Rejected: Rewriting the batch-file path format (using absolute paths instead of relative in Context/Edits/Creates) — changes the plan template schema, affects all models, and the root cause is not confirmed to be the path format in the batch file.

### no change to mill-go stuck-handling for scope violations

- Decision: `stuck_type: logic` is the correct type for scope violations. mill-go already halts on `logic` and asks the operator to intervene. No new stuck type is added.
- Rationale: Scope violations require human review — the operator must inspect and `git checkout` the stray files. A new `stuck_type: scope` would require mill-go skill changes outside this task's scope and would complicate the stuck-type taxonomy without adding recovery value (since the only recovery is manual cleanup anyway).
- Rejected: `stuck_type: scope` — new type, requires mill-go changes, out of scope.

## Technical context

### Relevant files

- `plugins/mill/scripts/millpy-implement.py` — the per-batch implementer CLI. Calls `_implementer_claude.run()` after rendering the brief. `impl_spec` is already resolved from `_reviewers.resolve(registry, model_name)` and available for the timeout override. The brief-size guard and timeout override both live between brief rendering and the `_implementer_claude.run()` call.
- `plugins/mill/scripts/millpy-fix.py` — the fixer CLI. Same structure: resolves `fixer_spec`, reads `timeout` from config. Needs the same per-reviewer timeout override.
- `plugins/mill/scripts/_implementer_common.py` — `_forward_output(output, project_root, *, start_sha, snapshot_path, session_id)`. The function that determines the final JSON status from the implementer's raw output. The scope-violations call goes here. The function already imports `_cleanliness` and calls `compute_new_dirt`.
- `plugins/mill/scripts/_cleanliness.py` — `capture_snapshot` and `compute_new_dirt`. The new `compute_scope_violations(worktree)` is a peer function here.
- `plugins/mill/templates/mill-agents.yaml` — canonical agent specs. `haiku` entry currently has `model`, `provider`, `type` — no `timeout`. The `timeout` field is optional; agents that don't set it fall back to `llm.implementer_timeout`.
- `plugins/mill/templates/implementer-brief.md` — the prompt template. Has `## Cross-worktree isolation` and `## Tools` sections. The path reminder goes between them (new `## Path format` section) or appended to `## Tools`.

### Timeout resolution chain (after fix)

```
impl_spec.get("timeout")            # per-reviewer, e.g. 600 for haiku
  or cfg["llm"]["implementer_timeout"]  # global, default 1800
  or 1800                               # hardcoded fallback
```

### compute_new_dirt vs compute_scope_violations

`compute_new_dirt(worktree, snapshot_path)` — tracked-file diff (pre-snapshot vs post). Uses `--untracked-files=no`. API stable; do not change.

`compute_scope_violations(worktree)` — new, point-in-time. Runs `git status --porcelain --untracked-files=normal` and returns `?? ` lines outside `_mill/`. No snapshot comparison — assumes a clean worktree at batch start (which mill-spawn guarantees). Returns `list[str]` of path strings (without the `?? ` prefix).

### _forward_output call sites

`_forward_output` is called from:
- `millpy-implement.py` (initial dispatch)
- `millpy-fix.py` (fixer dispatch)

Both already pass `project_root`. No signature change needed — `compute_scope_violations` takes only `project_root`.

### Existing unit test coverage

- `test-cleanliness.py` — 6 cases for `compute_new_dirt`. Does not test `compute_scope_violations` (new).
- `test-implementer-common.py` — 5 cases for the inferred-success paths. Does not test scope violations (new) or brief-size guard (in a different module).
- `test-millpy-implement.py` — 8 cases (`TestMillpyImplement`) + 8 cases (`TestForwardOutput`). Does not test oversized prompt (new).
- `test-llm-claude.py` — argv construction, stream-json parsing, rate-limit, session reuse. Not affected.

## Constraints

- `print()` / `_log()` output must be ASCII only — no Unicode (`—`, `→`, etc.) in new strings added to Python scripts.
- All new scratch files go under `.scratch/`, never `/tmp/` or `$env:TEMP`.
- `PYTHONPATH=` (empty value, single space) prefix required on `verify:` commands in plan batch files.
- No backwards-compat shims — if a function is renamed or a field added, update all callsites.
- `_cleanliness.compute_new_dirt` signature and behaviour must remain unchanged — existing test cases must still pass.

## Testing

### test-cleanliness.py — new cases for compute_scope_violations

- Clean worktree → returns `[]`.
- Untracked file at worktree root (e.g. `plugins_mill_scripts_foo.py`) → returned in list.
- Untracked file under `_mill/` (e.g. `_mill/some-scratch.txt`) → NOT returned (filtered out).
- Untracked file in a subdirectory outside `_mill/` (e.g. `plugins/mill/scripts/new_file.py`) → returned.
- Uses a real `git init` fixture (same pattern as `test-implementer-common.py`) since `compute_scope_violations` calls `git status`.

### test-implementer-common.py — new cases for scope violations in _forward_output

- Stuck/logic output + untracked violation file → `scope_violations` field present in JSON.
- Inferred-success scenario (commit advanced, clean tracked tree) + untracked violation → status downgraded to `stuck/logic`, `scope_violations` field present.
- No violations → output unchanged from existing behaviour.
- Mock `_cleanliness.compute_scope_violations` to return controlled values (avoid needing a real git repo).

### test-millpy-implement.py — new case for brief-size guard

- `max_implementer_prompt_chars: 10` in config, brief rendered to more than 10 chars → `_implementer_claude.run` NOT called, exit 0, JSON `{"status": "stuck", "stuck_type": "transient", "reason": contains "max_implementer_prompt_chars"}`.
- `max_implementer_prompt_chars: 0` (disabled) → guard does not fire, normal dispatch proceeds.

### Regression: all existing tests must still pass

Run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` after each batch to verify no regressions in the full suite.

## Q&A log

- **Q:** Fix the hang defensively (brief-size guard + per-reviewer timeout) without root-cause investigation, or probe haiku stream-json first? **A:** Defensive fix only. Root cause is not needed to make the hang surface faster and to prevent silently consuming 1800s.
- **Q:** Fix path mangle via prevention (brief) AND detection (cleanliness), or one only? **A:** Both. Brief reminder prevents; cleanliness check catches it when it happens anyway.
- **Q:** Where does untracked-file detection live? **A:** New `compute_scope_violations` in `_cleanliness.py`; called from `_forward_output` in `_implementer_common.py`. Not a change to `compute_new_dirt`.
- **Q:** Should scope violations produce a new `stuck_type`? **A:** No. `stuck_type: logic` covers it; mill-go already halts for operator intervention on logic. New type would require mill-go changes outside this task's scope.
- **Q:** Should `millpy-fix.py` also get the per-reviewer timeout? **A:** Yes. The fixer also uses haiku by default and renders a brief; identical timeout logic applies.
