# Discussion: 39 (A) — mill-start question-format UX

```yaml
task: 39 (A) — mill-start question-format UX
slug: mill-start-question-ux
status: discussing
parent: main
```

## Problem

Three independent UX/quality issues observed during mill-start and mill-go runs:

1. **Inconsistent `(Recommended)` placement.** When mill-start (and other skills) present numbered options, the `(Recommended)` tag lands on different option numbers from prompt to prompt. The user has to read every option before picking the obvious one — defeating the purpose of recommending an answer. The `conversation` SKILL.md global rule today says `Recommended option gets (Recommended) suffix` but does not constrain the option number, so call sites diverge.

2. **Question-batch stalls.** mill-start's Phase: Discuss can produce batches of 10–12 questions in one round. The Anthropic prompt-cache TTL is 5 min; long batches push the user past that window, so the next response reads the conversation uncached — slower and more expensive — and the conversation feels stalled. The `mill-start` SKILL.md only says "focused batches" with no explicit cap.

3. **Reviewer subprocess popup-flash on Windows.** During long mill-go runs, every reviewer dispatch produces a brief Windows console-window flash. The fix to add `creationflags=subprocess.CREATE_NO_WINDOW` is already present in `_subprocess_util.run` (added by commit `5714ebb`), but several call sites bypass `_subprocess_util.run` and call `subprocess.run`/`Popen` directly without the flag. The flashes the user observes come from those bypassing sites and from `mill-bg`'s detached worker spawn, which uses `DETACHED_PROCESS` without `CREATE_NO_WINDOW`.

**Why now:** these three are small surface-area papercuts that, accumulated, degrade every interactive mill-start session and every long mill-go session. They are independent enough to bundle in one task because each touches `plugins/mill/skills/` or `plugins/mill/scripts/` only and shares the same review and merge cycle.

## Scope

**In:**

- `plugins/mill/skills/conversation/SKILL.md` — strengthen the global rule: `(Recommended)` MUST be on option 1.
- `plugins/mill/skills/mill-start/SKILL.md` — Phase: Discuss — add explicit `≤5 questions per batch; remainder rolls to the next batch` rule.
- `plugins/mill/scripts/_inplace.py` — reorder `prompt_stale_worktree` so `Abort (Recommended)` is option 1; remap input handler accordingly. Update unit-test mappings in `plugins/mill/unit_tests/test-inplace.py`.
- `plugins/mill/skills/mill-groom/SKILL.md` — Step 4 menu: when the heuristic recommends a non-#1 option, swap the recommended option into position 1 while preserving the relative order of the others. Update wording to describe the swap.
- `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md` — fix the conditional `(Recommended) on option 1 OR option 2` instruction so the recommended option is always #1, with the conditional shifting which content lands in #1.
- `plugins/mill/scripts/_subprocess_util.py` — extend `run(...)` with optional `stdout`/`stderr` overrides (defaults remain `PIPE`); add new `popen_detached(argv, *, stdin, stdout, stderr, cwd=None, env=None)` helper that returns a `Popen` handle and applies `CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` on Windows, `start_new_session=True` on POSIX.
- Refactor every direct `subprocess.run` / `subprocess.Popen` site under `plugins/mill/scripts/` (excluding interactive launchers — see below) to go through `_subprocess_util.run` or `_subprocess_util.popen_detached`. Specifically:
  - `millpy-bg.py:49,94,136` (worker run-to-log; launcher git rev-parse; launcher detached-Popen of worker)
  - `millpy-implement.py` (all `subprocess.run` calls)
  - `millpy-implement-holistic.py` (all `subprocess.run` calls)
  - `millpy-merge-in-subagent.py` (all `subprocess.run` calls)
  - `millpy-skills-index.py:27`
  - `_implementer_common.py:19`
  - `_review_common.py:610`

**Out:**

- Interactive launchers — `plugins/mill/scripts/millpy-terminal.py:112,114` (`cmd /c claude --name <slug>` / `claude --name <slug>`) and `plugins/mill/scripts/millpy-vscode.py:169` (`code <path>`) — left untouched. These spawn user-facing programs whose console window is expected/desired; suppressing it would break the operator experience.
- `mill-claim` — already complies (option 1 is `(Recommended)`).
- Any reorder of mill-start's question-presentation Phase itself — questions presented inline by mill-start are dynamic and already place the recommended answer first when the skill author follows the rule. The fix is the rule, not the dynamic-rendering code.
- New SKILLS or new helpers beyond the two `_subprocess_util` entry points listed above.
- Plugins outside `plugins/mill/` (codeguide, csharp, python, weblens) — out of scope; if those grow direct `subprocess.run` sites later, they can adopt the same helper.
- Unit/integration tests for the popup-flash fix beyond updating existing tests broken by the `_inplace` reorder. GUI-level popup behaviour is verified manually.

## Decisions

### rec-rule-global

- Decision: Update `conversation/SKILL.md:34` to require that the `(Recommended)` option is always option `1`. New rule text: `Always use numbered text lists. Print each option as 1) Label — description. The recommended option, if any, MUST be option 1; remaining options follow in any order.`
- Rationale: a single global rule is easier to enforce than per-skill rules; mill-start, mill-groom, mill-ghissues-to-tasks, mill-claim, and `_inplace.prompt_stale_worktree` all inherit. The user's stated motivation — letting them pick "1" without reading every option — only holds if it is universal.
- Rejected: scoping the rule to mill-start only (would leave the same UX bug everywhere else); adding a per-prompt opt-out (rule loses its force).

### rec-rule-inplace-reorder

- Decision: Reorder `_inplace.prompt_stale_worktree` so the menu reads: `1) Abort (Recommended) / 2) Treat as in-place — skip worktree remove / 3) Treat as worktree — run git worktree remove`. Update the input mapping so `1 → "abort"`, `2 → "inplace"`, `3 → "worktree"`. Invalid input continues to default to `"abort"` — now also the option-1 default. Update `plugins/mill/unit_tests/test-inplace.py` test names and assertions to match.
- Rationale: prompt_stale_worktree is one of the loudest violators today. Reordering preserves the safe-default behaviour (abort on invalid/EOF) and aligns with rec-rule-global. The function only returns string codes (`"abort"`, `"inplace"`, `"worktree"`); call sites in `millpy-cleanup.py:269` and the `mill-merge` skill consume those strings, not numbers, so the reorder is API-safe.
- Rejected: exempt the prompt because abort-as-last is "ergonomically traditional" — option 1 is the new ergonomic default, and the safe choice should be there.

### rec-rule-groom-swap

- Decision: In `mill-groom` Step 4, when a heuristic recommends a non-default option, the menu reorders by **swapping** the recommended option into position 1; the remaining options retain their relative order. Examples:
  - Heuristic recommends "Drop" → menu: `1) Drop (Recommended) / 2) Keep as-is / 3) Shorten / 4) Fold into <slug> / 5) Extract to proposal`.
  - Heuristic recommends "Extract" → menu: `1) Extract to proposal (Recommended) / 2) Keep as-is / 3) Shorten / 4) Fold into <slug> / 5) Drop`.
  - No heuristic recommendation → menu unchanged: `1) Keep as-is / 2) Shorten / 3) Fold / 4) Drop / 5) Extract`.
- Rationale: keeps groom compliant with rec-rule-global without forcing operators to remember a fully reshuffled option order across every task. The recommended option is at #1; the remaining order is stable relative to the canonical list.
- Rejected: full priority-based reorder (more invasive UX change for marginal benefit); leave-in-place + accept rule violation (defeats the purpose of the global rule).

### rec-rule-ghissues-conditional

- Decision: Update `mill-ghissues-to-tasks/SKILL.md:58` so the recommended option is always rendered at position 1; the conditional decides which option (new task vs. fold-in) gets that position. New wording must be unambiguous: "If the issue does not overlap with any current Home.md task, present `1) New task (Recommended) / 2) Fold into <slug>`. If it overlaps, present `1) Fold into <slug> (Recommended) / 2) New task`."
- Rationale: same global-rule alignment.
- Rejected: keep the conditional `(Recommended)` floating between option 1 and option 2 — direct violation of rec-rule-global.

### batch-cap

- Decision: Add to `mill-start/SKILL.md` Phase: Discuss section the rule: `Cap each batch at ≤5 questions; ask the rest in subsequent batches after the user answers.`
- Rationale: the user observed that 10–12-question batches stall the conversation past the 5-min prompt-cache TTL, making each follow-up slower and more expensive. The short rule is enforceable; 5 was chosen as a practical ceiling that keeps a batch readable on one screen and answerable inside the cache window.
- Rejected: longer rule with TTL rationale embedded in SKILL.md (per Q5 the user picked the short version — rationale belongs in this discussion.md and the commit message, not the always-loaded skill text); cap at 3 (too small, causes excessive round-trips); cap at 7 (too easy to drift past cache window).

### batch-cap-location

- Decision: Cap rule lives in `mill-start/SKILL.md` only (not `conversation/SKILL.md`).
- Rationale: mill-start is the only skill that asks free-form question batches large enough to stall. Other multi-prompt skills (`mill-groom`, `mill-ghissues-to-tasks`, `_inplace`) ask one question at a time. Hoisting to global would be premature generalization.
- Rejected: hoist to `conversation/SKILL.md` (no other skill needs it today; YAGNI); duplicate in both files (drift risk).

### popup-helper-shape

- Decision: Extend `_subprocess_util.py` as follows:
  1. `run(argv, *, cwd=None, input=None, check=False, timeout=None, env=None, stdout=None, stderr=None)` — when `stdout` / `stderr` are `None`, behaviour is unchanged (`PIPE`). When supplied, the caller's value flows directly to `subprocess.Popen`. Caveat: when `stdout`/`stderr` are non-`PIPE`, the returned `CompletedProcess.stdout`/`.stderr` will be empty strings (since nothing was captured). Document this in the docstring.
  2. New `popen_detached(argv, *, stdin=None, stdout=None, stderr=None, cwd=None, env=None) -> subprocess.Popen` — fire-and-forget helper. On Windows: `creationflags = CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`. On POSIX: `start_new_session=True`. Returns the `Popen` handle so the caller can read `.pid`. Also injects `PYTHONIOENCODING=utf-8` into the child env, mirroring `run`.
- Rationale: keeps the existing `run` API backward-compatible while allowing call sites that need redirected I/O (mill-bg's worker→log) to keep their behaviour. The new `popen_detached` covers the remaining Windows-flash gap (mill-bg's launcher Popen of the worker) and centralises the detached-process flag combo so future fire-and-forget helpers don't drift.
- Rejected: separate `run_to_file(argv, *, log_path)` helper (too narrow, still needs new helpers for any future case); inline `creationflags=CREATE_NO_WINDOW` per call site (each maintainer would have to remember the flag every time, exact failure mode that motivated `_subprocess_util` in the first place).

### popup-call-site-routing

- Decision: For each direct `subprocess.run` / `subprocess.Popen` site listed in **Scope: In**, replace the call as follows.
  - `subprocess.run(cmd, ...)` capturing output → `_subprocess_util.run(cmd, ...)` (drop redundant `text=True`, `encoding=...`, `errors=...`, `capture_output=...` kwargs since `_subprocess_util.run` provides them).
  - `subprocess.run(cmd, stdout=log_f, stderr=subprocess.STDOUT)` redirecting to a file → `_subprocess_util.run(cmd, stdout=log_f, stderr=subprocess.STDOUT)`.
  - `subprocess.Popen(worker_argv, creationflags=DETACHED_PROCESS|...)` fire-and-forget → `_subprocess_util.popen_detached(worker_argv, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)`.
  - `subprocess.run(["git", ...], capture_output=True, text=True)` quick git query → `_subprocess_util.run(["git", ...])`.
- Rationale: every routing rule above is a mechanical substitution; behaviour is preserved (return type, error semantics) but the Windows console-flash flag is now applied uniformly. The breadcrumb-on-stderr (`[subprocess] spawn …`) becomes consistent across all sites — useful for debugging and grepping in tests.
- Rejected: routing only the cmd/c claude site through `_subprocess_util` (popup comes from many sites; partial fix); inline patches (drift risk identified above).

### popup-interactive-exemption

- Decision: `millpy-terminal.py:112` (`cmd /c claude --name <slug>`), `millpy-terminal.py:114` (POSIX `claude --name <slug>`), and `millpy-vscode.py:169` (`code <path>`) remain bare `subprocess.run` calls. Add a one-line code comment at each site: `# Interactive launcher — must keep its console; do NOT route through _subprocess_util.run.`
- Rationale: these launches exist precisely to hand off a foreground process to the user. Suppressing the console / routing through `_subprocess_util.run` (which captures stdout/stderr as PIPEs) would either hide the launched program or break it.
- Rejected: route through `_subprocess_util.run_interactive(...)` variant (overengineered for two call sites); convert to fire-and-forget detached (kills the foreground hand-off entirely).

### popup-verification

- Decision: Verification is manual. Operator runs a reviewer end-to-end on Windows (e.g. `mill-go` on a small task or a standalone reviewer dispatch) and confirms no console window appears for the duration of the run. No automated test asserts the GUI behaviour; existing unit tests for `_subprocess_util.run` remain unchanged.
- Rationale: GUI popup behaviour is environment-dependent (Windows version, shell, focus) and not reliably mockable. A scan-test that asserts no direct `subprocess.run` exists outside the helpers is brittle (catches false positives in tests that mock subprocess) and adds maintenance load.
- Rejected: scan-test for direct `subprocess.run` usage (high false-positive rate; circular for tests that mock subprocess); mock-based unit test asserting `creationflags` (ties tests to internal kwargs and offers no GUI assurance).

## Technical context

Modules and contracts mill-plan must know:

- **`plugins/mill/scripts/_subprocess_util.py`** — single subprocess wrapper. Already injects `PYTHONIOENCODING=utf-8` into the child env, hardcodes `stdout=PIPE, stderr=PIPE, encoding="utf-8", errors="replace", text=True`, sets `creationflags=CREATE_NO_WINDOW` on Windows, emits `[subprocess] spawn argv=... timeout=...` and `[subprocess] exit code=... duration=...s` breadcrumbs to stderr, and converts `TimeoutExpired` into a wrapped exception with stdout/stderr preserved. The `popen_detached` helper added by this task must mirror the env injection and breadcrumbs but skip the timeout / capture machinery.

- **`plugins/mill/scripts/_llm_claude.py`** — already routes through `_subprocess_util.run` via `_invoke()` at line 246. No code change needed here, but cite as evidence that the cmd-/c-claude path is already protected.

- **`plugins/mill/scripts/millpy-bg.py`** — split between launcher path and worker path. Launcher (line 94) does `git rev-parse` then (line 121–136) spawns the worker with detached flags. Worker (line 49) runs the user's command with stdout redirected to a log file and writes the `[mill-bg] EXIT` sentinel. After this task: launcher uses `_subprocess_util.run` for the git query and `_subprocess_util.popen_detached` for the worker spawn; worker uses `_subprocess_util.run(cmd, stdout=log_f, stderr=subprocess.STDOUT)` for the user's command.

- **`plugins/mill/scripts/_inplace.py`** — `prompt_stale_worktree(slug, worktree_path) -> Literal["inplace","worktree","abort"]`. Defined at line 75. Internal numbered prompt currently maps `1→inplace, 2→worktree, 3→abort`. Reorder updates strings and the integer-mapping branches. Callers in `plugins/mill/scripts/millpy-cleanup.py:269` and `plugins/mill/skills/mill-merge/SKILL.md` consume only the string return value — safe to reorder. Tests in `plugins/mill/unit_tests/test-inplace.py:119–193` simulate `input()` returning specific strings; test names and stdin fixtures must change to reflect the new mapping.

- **`plugins/mill/skills/conversation/SKILL.md`** — global rules read at every session start (declared in mill's `workflow` SKILL.md). Line 34 holds the `(Recommended)` rule today. Adjacent rules (avoid `AskUserQuestion`, never write `/tmp/`) are stable and out of scope.

- **`plugins/mill/skills/mill-start/SKILL.md`** — Phase: Discuss is at line 43–56. The new cap rule is appended as a bullet inside the existing Phase block. The Phase: Discussion Review present-each-gap-one-at-a-time rule is already cap=1 by design — no change.

- **`plugins/mill/skills/mill-groom/SKILL.md`** — Step 4 action menu at lines 114–125. Today the menu is fixed-order with `(Recommended)` appended on whichever option the heuristic picks; the new wording instructs the skill to **swap** the recommended option into position 1, retaining relative order of the rest, and to enumerate the heuristic→swap mapping with examples.

- **`plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`** — line 58 holds the conditional `(Recommended)` instruction. New wording places the recommended content always at position 1.

- **`plugins/mill/unit_tests/test-inplace.py`** — `_test_prompt_stale_worktree_returns_inplace_on_choice_1` and siblings at line 119–193. After the reorder, the choice→string mapping changes: rename the test functions and update the stdin fixture to match. Run via `python plugins/mill/unit_tests/run-all.py`.

- **No tests for SKILL.md content** — text changes to `conversation`, `mill-start`, `mill-groom`, `mill-ghissues-to-tasks` SKILL.md files have no unit tests today and none should be added.

Gotchas:

- `_subprocess_util.run`'s caveat when `stdout`/`stderr` overrides are passed: the returned `CompletedProcess.stdout` / `.stderr` are `""`. Callers that previously redirected and then inspected `.stdout` (none currently do) would break — verify with grep before assuming the override is safe to use everywhere.
- `popen_detached` must not pass `text=True` / `encoding=...`. Detached fire-and-forget callers don't `.communicate()`; encoding pipes that aren't read invites deadlock or interpretation surprises. Document the helper as raw-bytes / DEVNULL only.
- The `[subprocess] spawn` breadcrumb assumes a stderr the parent can see. mill-bg's launcher writes its own `pid=<N> log=<abs-path>` line to stdout for callers to parse; the launcher's stderr is forwarded by Bash and is fine. The worker's stderr is redirected to the log file by `subprocess.STDOUT`; the breadcrumb lands in the log, which is the desired outcome (debuggable from the log).
- Reordering the `_inplace.prompt_stale_worktree` menu while keeping invalid-input → `"abort"` means a user who hits Enter on an empty prompt now lands on the same outcome as a user who explicitly types `1`. Document this in the docstring as the "fail-safe default."

## Constraints

- **Junctions and hardlinks are NEVER used by scripts or skills.** Already enforced by `_paths`. None of the changes in scope touch path resolution, but new subprocess routes must continue to use `_paths`-resolved real paths, not junctions.
- **`${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths.** The popup fix touches scripts referenced by `${CLAUDE_PLUGIN_ROOT}/scripts/...` — no source-tree paths in code or SKILL.md.
- **Working state never written to the wiki.** No change here; `task/discussion.md` is on the task branch, not in the wiki.
- **Plugin scripts invoked via `uv run`.** Not affected.
- **Generated markdown uses fenced ```yaml for metadata, not `---` frontmatter** — except SKILL.md and plugin manifests. SKILL.md edits in scope keep their existing `---` frontmatter intact.
- **No CONSTRAINTS.md** at the hub root or worktree root — checked, none present.

## Testing

Per-module test approach:

- **`_subprocess_util` extensions** (`run` stdout/stderr overrides + `popen_detached`):
  - TDD candidate. Add `plugins/mill/unit_tests/test-subprocess-util.py` (or extend an existing file if one exists — confirm during plan).
  - Scenarios:
    - `run(argv, stdout=<file-like>, stderr=subprocess.STDOUT)` writes child stdout to the supplied file-like object, returns `CompletedProcess` with empty `.stdout`/`.stderr` strings, returncode propagates.
    - `run` defaults unchanged when `stdout`/`stderr` not supplied (regression check against existing behaviour).
    - `popen_detached(argv, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)` returns a `Popen` handle with non-`None` `.pid`, on Windows includes `CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB` in `creationflags` (assert by spawning a tiny no-op python `-c "pass"` and checking the kwarg passed to `Popen` via mock or by reading the spawned process's exit).
    - `popen_detached` injects `PYTHONIOENCODING=utf-8` into the child env (run a `python -c "import os; print(os.environ['PYTHONIOENCODING'])"` and read from a redirected file).

- **`_inplace.prompt_stale_worktree` reorder**:
  - Existing tests at `plugins/mill/unit_tests/test-inplace.py:119–193` need their names and fixtures updated:
    - `_test_prompt_stale_worktree_returns_abort_on_choice_1` (was `_returns_inplace_on_choice_1`)
    - `_test_prompt_stale_worktree_returns_inplace_on_choice_2` (was `_returns_worktree_on_choice_2`)
    - `_test_prompt_stale_worktree_returns_worktree_on_choice_3` (was `_returns_abort_on_choice_3`)
    - `_test_prompt_stale_worktree_returns_abort_on_invalid_choice` — keep, verify still passes (invalid → abort independent of menu order).
    - `_test_prompt_stale_worktree_returns_abort_on_eof` — keep, ditto.
  - Run via `python plugins/mill/unit_tests/run-all.py`. No new test logic; fixture-string updates only.

- **Refactored call sites (`millpy-bg.py`, `millpy-implement.py`, `millpy-implement-holistic.py`, `millpy-merge-in-subagent.py`, `millpy-skills-index.py`, `_implementer_common.py`, `_review_common.py`)**:
  - Existing tests for these scripts (`test-millpy-bg.py`, `test-millpy-implement.py`, `test-millpy-implement-holistic.py`, `test-millpy-merge-in-subagent.py`, `test-millpy-skills-index.py`) must continue to pass without modification — refactoring is a behaviour-preserving substitution (`subprocess.run` → `_subprocess_util.run`).
  - If a test directly mocks `subprocess.run`, the mock target must change to `_subprocess_util.run` (or `_subprocess_util.popen_detached`). Confirm by grepping the test file before refactoring; update the patch path as needed.
  - No new tests for the routing itself.

- **SKILL.md text changes** (`conversation`, `mill-start`, `mill-groom`, `mill-ghissues-to-tasks`):
  - No unit tests. Rendering and behaviour are inspected by reading the file in a follow-up `mill-start` / `mill-groom` / `mill-ghissues-to-tasks` session. Document the rule changes in the commit body.

- **Manual end-to-end verification (popup-flash)**:
  - On Windows: trigger a reviewer dispatch via `mill-go` (or run `millpy-bg.py --slug verify -- uv run --project ... millpy-review-discussion.py` against a small task). Watch the screen for any console-window flash. Expected: none.
  - Document the verification in the commit body of the popup fix commit.

- **Run order**: unit tests first via `python plugins/mill/unit_tests/run-all.py`; then operator verifies the popup fix manually before opening the PR.

## Q&A log

- **Q:** Where does the "recommended = always #1" rule live? **A:** Both `conversation/SKILL.md` (global rule) and reorder existing hardcoded menus.
- **Q:** Reorder `_inplace.prompt_stale_worktree` so Abort is option 1? **A:** Yes; update unit tests accordingly; safe-default behaviour preserved.
- **Q:** mill-groom heuristic-recommended option — fix? **A:** Yes; swap the recommended option into position 1, keep the others in their relative order.
- **Q:** Where does the "cap each batch at 5" rule live? **A:** `mill-start/SKILL.md` Phase: Discuss only.
- **Q:** How prescriptive should the rollover wording be? **A:** Short: "Cap each batch at ≤5 questions; ask the rest in subsequent batches after the user answers."
- **Q:** Where is the popup actually coming from? **A:** Bypassing `subprocess.run` / `Popen` call sites that don't go through `_subprocess_util.run`. Patch all of them.
- **Q:** Central helper vs. per-site patch? **A:** Central helper. Refactor every direct `subprocess.run` / `Popen` in `plugins/mill/scripts/` (excluding interactive launchers) through `_subprocess_util.run` or a new sibling for fire-and-forget.
- **Q:** Interactive launchers — exempt? **A:** Yes. `millpy-terminal.py` and `millpy-vscode.py` keep their bare `subprocess.run` (with a one-line comment marking the exemption).
- **Q:** Verification approach? **A:** Manual end-to-end on Windows; no automated GUI test.
- **Q:** Helper signature for the bypassing call sites? **A:** Extend `_subprocess_util.run` with optional `stdout`/`stderr` overrides; add `_subprocess_util.popen_detached(argv, *, stdin, stdout, stderr)` returning a `Popen` handle, with the full Windows detached-flag combo plus `CREATE_NO_WINDOW`.
- **Q:** mill-groom reorder shape? **A:** Swap-only — recommended option moves to position 1, the rest keep their relative order.
