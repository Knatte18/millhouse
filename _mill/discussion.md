# Discussion: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate

```yaml
task: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate
slug: mill-verify-and-layout-gaps
status: discussing
parent: main
```

## Problem

Five bugs were surfaced across separate user sessions. They cluster around two themes: path-resolution gaps in nested-hub layouts, and missing gates in the mill-go Handoff.

1. **#552** `parse_blocking_count` in `_review_common.py` scans only for `### [BLOCKING]` ATX headings. When a reviewer emits a YAML `findings:` list inside a fenced block instead of headings, the heading scan returns 0 despite real findings. The `verdict:` field parses correctly (REQUEST_CHANGES), but `blocking_count`/`nit_count` in the JSON envelope are 0, breaking any skill that gates on those counts.
2. **#553** `millpy-review-discussion.py --stage prepare` resolves `brief_path` under `git_root/_mill/briefs/` using `resolve_git_root()`. In nested-hub layouts (hub is a subdir of the git root), the brief lands outside the project root. mill-start Handoff stages `_mill/briefs/` from the hub root (`worktree_root`), so the brief is never committed.
3. **#554** `millpy-implement.py --stage finalize` calls `finalize_from_output` with `project_root` (= hub path from `resolve_hub_path()`). `_run_verify_gate` runs the batch verify command with `cwd=project_root`. In nested layouts, plan verify commands are written git-root-relative (e.g. `dotnet test src/csharp/Foo/Foo.Tests`). Running that from the hub dir (`src/csharp/Foo`) doubles the path and fails with MSB1009.
4. **#556** `dotnet test` on Windows spawns testhost and build-server processes that persist after the test run. Repeated verify attempts in a self-fix loop accumulate 20-30 orphaned processes that hold file locks, causing subsequent verify runs to fail with transient lock errors indistinguishable from real failures.
5. **#561** mill-go has no repo-wide test gate before it appends `done` and flips the wiki to `ready-to-merge`. Per-batch verifies are scoped to touched paths. Holistic review sees what the reviewer was given. Both can be green while a package outside the batch scopes is broken. git-pr's full-suite verify (in mill-finalize) catches the regression only after done is already set.

## Scope

**In:**
- `plugins/mill/scripts/_review_common.py` — extend `parse_blocking_count` to count YAML `findings:` list entries as fallback when heading count is 0 (#552)
- `plugins/mill/scripts/millpy-review-discussion.py` — fix brief_path to use `hub_dir` instead of `git_root` in the prepare stage (#553)
- `plugins/mill/scripts/_implementer_common.py` — add `git_root: Path | None` kw-arg to `finalize_from_output`, `_forward_output`, `_run_verify_gates`, `_run_verify_gate`; use `git_root` as verify cwd when provided (#554)
- `plugins/mill/scripts/millpy-implement.py` — pass `git_root` to `finalize_from_output` in the `--stage finalize` branch (#554)
- `plugins/mill/scripts/_implementer_common.py` — run `dotnet build-server shutdown` as best-effort after any `dotnet`-type verify on Windows (#556)
- `plugins/mill/templates/mill-config.yaml` — add `pipeline.done_gate: null` config key (#561)
- `plugins/mill/skills/mill-go/SKILL.md` — add pre-done gate step in Handoff, between scope-violations check and `_status.append_phase("done")` (#561)
- Unit tests: `test-review-common.py`, `test-review-discussion-flow.py`, `test-implementer-common.py`

**Out:**
- Reviewer prompt changes for #552 (the template already mandates `### [BLOCKING]`; the parser is the fix)
- Plan verify-command conventions (fix the finalize cwd, not the plan authoring rules)
- Non-Windows process cleanup for #556
- mill-merge-in verify scope (separate concern, has its own allowlist)
- mill-finalize or mill-merge changes
- Automatic language detection for #561 (explicit config only)

## Decisions

### #552 — parse_blocking_count YAML fallback

- **Decision:** When `parse_blocking_count` finds zero headings matching `### [<severity>]`, it also scans all fenced yaml blocks in `raw_output` for a `findings:` key. Each list entry whose `severity` field (case-insensitive match) equals the severity argument is counted. The combined result is `heading_count` if `heading_count > 0`; otherwise `yaml_count`. `_warn_if_prose_diverge` is called with whichever count was used.
- **Rationale:** Heading-first with yaml fallback avoids double-counting (the two formats are mutually exclusive per review output in practice). The fix is fully internal to `parse_blocking_count`; no API change. The `finalize_scope` in `_review_common.py` that calls `parse_blocking_count` needs no changes.
- **Rejected:** Strengthen prompt only — unreliable, LLMs drift; sum both — double-counting if a reviewer ever mixes formats.

### #553 — discussion-review brief anchor is hub_dir

- **Decision:** In `millpy-review-discussion.py` line 98, change `resolve_task_path(git_root, "_mill/briefs/")` to `resolve_task_path(hub_dir, "_mill/briefs/")`. `hub_dir` is already resolved via `resolve_hub_path()` at line 71.
- **Rationale:** All other task-state paths (reviews_dir, status_path) use `hub_dir` as anchor. The brief is task state and must use the same anchor. This is a one-line change; the `hub_dir` variable is already in scope.
- **Rejected:** Add git_root == hub_dir validation and raise — does not fix the bug in nested layouts.

### #554 — verify cwd follows git_root not project_root

- **Decision:** Add `git_root: Path | None = None` as a keyword-only parameter to `finalize_from_output`, `_forward_output`, `_run_verify_gates`, and `_run_verify_gate` in `_implementer_common.py`. In `_run_verify_gate`, use `git_root` as subprocess `cwd` when provided; fall back to `project_root` when None. In `millpy-implement.py` `--stage finalize`, pass `git_root=git_root` (already in scope).
- **Rationale:** In flat layouts `git_root == project_root`, so the fallback is zero-risk. In nested layouts the fix makes finalize match what the implementer agent does (it adapts its own cwd). The API change is additive (new kw-arg with default None); all existing callers compile unchanged.
- **Rejected:** Make plan verify commands hub-relative — breaks existing plans, changes user convention; try git_root then project_root — semantically wrong (two verify outcomes for one command).

### #556 — dotnet build-server shutdown after verify

- **Decision:** In `_implementer_common._run_verify_gate`, after the verify subprocess exits (success or failure), if `sys.platform == 'win32'` and the normalized verify command contains the substring `dotnet` (case-insensitive), run `subprocess.run(["dotnet", "build-server", "shutdown"], capture_output=True, timeout=30)` and discard the result. The main verify exit code is reported as before; the shutdown is best-effort.
- **Rationale:** `dotnet build-server shutdown` is the canonical release for testhost/MSBuild process locks on Windows. Running it unconditionally after every dotnet verify is idempotent and cheap. The platform guard prevents no-op calls on POSIX. The string check avoids firing on non-dotnet commands.
- **Rejected:** `/p:UseSharedCompilation=false` — requires modifying all existing plan verify commands; may slow incremental builds; `--no-build` is semantically different. Cleanup on failure only — file locks accumulate from successful runs too.

### #561 — done_gate config key

- **Decision:** Add `pipeline.done_gate: null` to `plugins/mill/templates/mill-config.yaml`. When non-null, mill-go Handoff runs the command from `git_root` before `_status.append_phase("done")`. On non-zero exit, halt with `BLOCKED: done gate failed` (do not set phase done). Update mill-go SKILL.md Handoff to document the pre-done gate step. mill-plan SKILL.md gets a note that operators should consider populating `done_gate` for languages with a fast full-suite command (e.g. `go test ./...`).
- **Rationale:** Explicit config gives operators full control; works across all languages; zero-cost when null (backward compat for all existing configs). Language auto-detection is brittle for multi-language repos and repos with non-standard layouts.
- **Rejected:** Auto-detect language and always gate — too many false positives in unusual setups; use plan overview `verify:` as final gate — same scope as existing batch verifies, doesn't add cross-scope coverage.

## Technical context

**Files and line references (verified against current branch):**

- `_review_common.py:1328` — `parse_blocking_count(raw_output, *, severity)`: regex-only scan, no yaml fallback. Fenced-yaml parsing for verdict is at line 1233; the same extraction pattern applies to the fallback scan.
- `_review_common.py:1286` — `_warn_if_prose_diverge`: takes `(raw_output, severity, heading_count)`. Passes through unchanged; caller passes whichever count was used.
- `_review_common.py:1415` — `_finalize_review_entry`: calls `parse_blocking_count` for both blocking and nit severity; no change needed here beyond the fix to `parse_blocking_count`.
- `millpy-review-discussion.py:64-105` — prepare stage: `hub_dir = resolve_hub_path()` (line 71), `git_root = resolve_git_root()` (line 70). Brief anchor bug at line 98.
- `_implementer_common.py:350` — `_run_verify_gate(project_root, verify_cmd)`: needs new `git_root` param.
- `_implementer_common.py:415` — `_run_verify_gates(project_root, verify_cmd, module_wide_verify_cmd)`: needs `git_root` threaded through to both `_run_verify_gate` calls.
- `_implementer_common.py:539` — `finalize_from_output(agent_output_path, project_root, ...)`: needs `git_root` added.
- `_implementer_common.py:609` — `_forward_output(output, project_root, ...)`: needs `git_root` threaded to `_run_verify_gates`.
- `millpy-implement.py:105-109` — both `project_root` and `git_root` are already in scope. Finalize stage at line 255 only passes `project_root` to `finalize_from_output`.
- `mill-go/SKILL.md:703-716` — Handoff section. Current sequence: scope violations check (703) → done (716). New gate step goes between 712 and 716.
- `mill-config.yaml template:119-124` — `pipeline:` block. `done_gate: null` is added here. Hub overlays and config.local.yaml can override with a real command string.

**YAML findings format (from issue #552):**
The reviewer emits a fenced yaml block with a `findings:` list using keys `id`, `severity`, `title`, `detail`. The `severity` field uses the same labels as headings (`BLOCKING`, `NIT`, `GAP`, `NOTE`). The yaml parse for the fallback scan must handle the block anywhere in `raw_output` (not only the first block — the verdict block is first and has `verdict:` not `findings:`).

**dotnet detection heuristic:** the verify command string is lowercased and checked for substring `dotnet`. This covers `dotnet test`, `dotnet build`, `dotnet run`. If any of those are the verify command, the shutdown fires. This is intentionally broad since any dotnet invocation can leave a build server alive.

**done_gate execution context:** The gate command runs from `git_root` (not hub dir), matching the convention established by #554. The SKILL.md Bash block uses the same `_subprocess_util.run` pattern as other inline verify commands. On failure the orchestrator halts with a BLOCKED message and does not commit the `done` status; the task stays in its current phase so the operator can investigate.

## Constraints

- Print/log output must be ASCII-only (`--` not `—`, `->` not `→`).
- No `python3`; use `$MILL_PYTHON` / `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`.
- `parse_blocking_count` API must not change (same positional + `severity` kw-arg); the fix is purely internal.
- `pipeline.done_gate: null` in the template means disabled; existing configs that do not set the key also see null (deep-merge default). Adding the key must not change any existing behavior.
- `finalize_from_output` and `_forward_output` new `git_root` param must default to None; every existing callsite that omits it gets `project_root` fallback — no behavior change for flat layouts.

## Testing

**test-review-common.py** — extend existing `parse_blocking_count` section:
- YAML findings list only (zero headings, one BLOCKING in yaml) -> count 1
- YAML list with mixed severities (one BLOCKING, two NITs): `severity="BLOCKING"` -> 1, `severity="NIT"` -> 2
- Heading count > 0 and yaml findings also present: heading count wins (yaml not scanned)
- YAML block that has `verdict:` but no `findings:` -> 0 (no false positives from verdict block)
- Malformed yaml in a fenced block (not parseable) -> 0 from yaml path (does not crash)
- Case-insensitive severity in yaml list (e.g. `severity: blocking`) should match `severity="BLOCKING"`

**test-review-discussion-flow.py** — add/extend brief-path test:
- Mock `resolve_hub_path()` to return a subdir of the git root; verify `brief_path` written by `--stage prepare` is under hub_dir, not git_root

**test-implementer-common.py** — add cases:
- `_run_verify_gate` with `git_root` kwarg pointing to a different dir: verify subprocess receives the correct cwd
- `_run_verify_gate` with `git_root=None`: verify subprocess cwd falls back to `project_root`
- Windows path: mock `sys.platform == 'win32'` and a verify_cmd containing `dotnet test`; verify `dotnet build-server shutdown` is invoked after verify exit

**mill-config.yaml template validation** — existing `test-config.py` or a new check: verify `pipeline.done_gate` key is present and null in the template deep-merge output.

No unit tests for the SKILL.md done_gate step itself; that is SKILL.md prose exercised by integration.

## Q&A log

- **Q:** How should `parse_blocking_count` handle reviewers that emit YAML `findings:` lists instead of `### [BLOCKING]` headings? Options: 1) Extend `parse_blocking_count` to scan fenced yaml blocks for a `findings:` list, using heading count when > 0, yaml count otherwise (Recommended). 2) Strengthen reviewer prompt to always mandate headings. 3) Sum heading + yaml counts (double-counting risk). **A:** [auto-pick] Extend `parse_blocking_count` with yaml-list fallback (option 1). **Why:** Heading-first avoids double-counting; the fix is internal with no API change; prompt-only fix is unreliable.
- **Q:** Where should `millpy-review-discussion --stage prepare` write the brief in nested-hub layouts? Options: 1) `hub_dir/_mill/briefs/` via `resolve_hub_path()`, already in scope (Recommended). 2) `git_root/_mill/briefs/` with an added warning when the two differ. **A:** [auto-pick] Use `hub_dir` (option 1). **Why:** All other task-state paths anchor to hub_dir; one-line fix; no new API needed.
- **Q:** What cwd should `--stage finalize` use when running the batch verify command? Options: 1) Add `git_root` kw-arg to finalize_from_output/_forward_output/_run_verify_gate, default None -> project_root (Recommended). 2) Mandate hub-relative paths in plan verify commands. 3) Try git_root then project_root on path error. **A:** [auto-pick] Add `git_root` kw-arg with project_root fallback (option 1). **Why:** In flat layouts fallback is zero-risk; in nested layouts it matches implementer agent behavior; plan conventions unchanged.
- **Q:** How should mill-go clean up orphaned dotnet processes on Windows? Options: 1) Run `dotnet build-server shutdown` after every dotnet verify, Windows-only, best-effort (Recommended). 2) Pass `/p:UseSharedCompilation=false` to dotnet invocations. 3) Detect file-lock errors and clean up only on failure. **A:** [auto-pick] Post-verify build-server shutdown (option 1). **Why:** Idempotent, fast, requires no plan changes; platform guard prevents noise on POSIX; proactive (locks accumulate on successful runs too).
- **Q:** How should mill-go guard against a red full test suite at task done? Options: 1) Add `pipeline.done_gate: null` to mill-config.yaml; mill-go Handoff runs it from git_root when non-null, halts on failure (Recommended). 2) Auto-detect project language and always run full-suite command. 3) Re-run plan overview verify as final gate. **A:** [auto-pick] `pipeline.done_gate` explicit config (option 1). **Why:** Zero-cost when null; language auto-detection is brittle for multi-language repos; option 3 adds no new coverage.
