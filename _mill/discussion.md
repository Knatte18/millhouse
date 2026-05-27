# Discussion: mill-merge / fixer teardown recovery

```yaml
task: mill-merge / fixer teardown recovery
slug: mill-merge-teardown-recovery
status: discussing
parent: main
```

## Problem

`/mill-merge` is the most fragile point in the pipeline: a single halt mid-teardown leaves the task in a state where the next `/mill-go` crashes (`status.md` already deleted by Step 4's cleanup commit), and the fixer subprocess has historically been able to corrupt the task branch's git config and history when its session `cd`s into a fixture or mutates worktree-local `git config`. The skill is currently not safely re-runnable, and the fixer's blast radius extends to commit authorship and branch contents.

Five concrete failure modes are tracked as #356, #357, #358, #367, #368 (all in `proposal-mill-merge-teardown-recovery.md`). They were each surfaced by real incidents during recent task runs (notably the wiki-tinydb holistic-fix and a prior aborted mill-merge). Fixing them is a precondition for autonomous `mill-autofix` runs to be trustworthy — every one of these bugs requires human intervention today.

**Why now:** `mill-autofix` and `pipeline.autonomous_mode` ramp up the rate of mill-merge invocations and fixer dispatches. The pipeline can't tolerate fragility at these two points if it's going to run unattended.

## Scope

**In:**
- `mill-merge/SKILL.md` Step 6 (archive tag) — conflict-resolution policy (#356).
- `mill-merge-in/SKILL.md` Step 3 (merge --continue) — non-interactive editor (#357).
- `mill-go/SKILL.md` Entry Step 5 (phase gate) — fallback when `status.md` is absent (#358).
- `_llm_claude.py` + `_subprocess_util.py` — strip git env vars from implementer/fixer child env (#367).
- `millpy-fix.py` + `millpy-implement.py` — use explicit `-c user.name/email` flags on CLI state commits (#368).
- Fixer/implementer brief templates — document cwd discipline (no `cd` outside worktree).
- Unit tests for each fix.

**Out:**
- Integration tests covering full mill-merge re-runs — YAGNI for this task; the unit tests cover the failure modes that #356–#368 actually describe.
- `git-commit` skill behaviour (per-card commits from inside an LLM session). Those commits run inside the session's git environment and don't share the CLI state-commit surface. Fixing them is a separate scope.
- Save+restore of worktree-local `user.name/email` around fixer dispatch. The `-c` flag approach on CLI commits makes save+restore unnecessary; pollution to the worktree config is annoying but not load-bearing for correctness.
- Builder-issued Bash commits inside `mill-go` (Prepare, Approve, Blocked). The original incident (#368) was a CLI state commit; broadening the `-c` flag pattern to Builder Bash calls is a separate hardening pass.
- `mill-merge` rollback semantics beyond the archive-tag step. The existing rollback path (Steps 1–5 reset to checkpoint) is unchanged.
- The `git-commit` skill's lint / `codeguide-update` chain is untouched.

## Decisions

### archive-tag-conflict

- **Decision:** `mill-merge` Step 6 implements a three-way conflict resolution when `archive/<slug>` already exists. (1) Tag points to the same SHA as `CHILD_BRANCH` → no-op (print `[mill-merge] archive tag already at HEAD; skipping`). (2) Tag points to a SHA that is an ancestor of `CHILD_BRANCH` (verified via `git merge-base --is-ancestor <existing-sha> $CHILD_BRANCH` returning 0) → force-update with `git tag -f archive/<slug> $CHILD_BRANCH && git push --force-with-lease origin archive/<slug>`. (3) Otherwise → move the existing tag aside as `archive/<slug>-<NN>` where `<NN>` is the lowest unused two-digit suffix starting at `01`, then create `archive/<slug>` afresh. Warn the user via stdout (`[mill-merge] existing archive tag preserved as archive/<slug>-01; new tag created`).
- **Rationale:** Idempotent re-runs (case 1) are the common path after a partial teardown — repeating the tag operation should be silent. Stacked cleanup commits on the same branch (case 2) are still safe to force because the ancestor chain is preserved in the new tag. Divergent history (case 3) is rare but must not lose the prior tag — naming it aside preserves the operator's ability to inspect the earlier teardown attempt.
- **Rejected:**
  - Always force-update (`git tag -f`) — loses the prior tag in case 3, which is the only case where preserving it matters.
  - Always move-aside — noisy for the common idempotent-re-run case; pollutes the tag namespace with `archive/<slug>-01`/`-02` accumulation across mundane re-runs.

### merge-continue-editor

- **Decision:** Update `mill-merge-in/SKILL.md` Step 3 to document the merge-continue command as `git -c core.editor=true merge --continue`. No Python helper, no env-var wrapper — the SKILL.md line is the only operator-facing surface and the documented command needs to be non-interactive by default.
- **Rationale:** `git -c core.editor=true` is portable across PowerShell and Bash (no inline-env-var syntax that breaks PowerShell), scoped to the single command (no env-var leak into subsequent operations), and adds zero new code surface to maintain.
- **Rejected:**
  - `GIT_EDITOR=true git merge --continue` — POSIX-inline env syntax; PowerShell can't parse it without a wrapper.
  - `millpy-merge-continue.py` helper — a new script for one git command is YAGNI; the SKILL.md edit is the actual fix because the command is invoked by the Builder thread, not by Python.

### mill-go-status-absent-fallback

- **Decision:** Mill-go's Entry Step 5 phase gate, before reading `status_path`, branches on `status_path.exists()`. If absent: call `task = _client.get_task(wiki_path, slug)` (the same helper `mill-merge`'s Step 5 already uses for its analogous fallback). Branch on `task["status"]`:
  - `"ready-to-merge"` or `"pr-pending"` → halt with: *"`_mill/status.md` is absent and wiki shows `<status>` for `<slug>` — mill-merge has likely run cleanup but not completed. Run `/mill-merge` to resume teardown."*
  - `"done"` → halt with: *"Task `<slug>` is already merged. Nothing to do."*
  - `None` (task not in Home.md) → halt with: *"`_mill/status.md` is absent and `<slug>` is not in Home.md — cannot determine state. Inspect manually."*
  - any other value → halt with: *"`_mill/status.md` is absent and wiki state is `<status>` — unexpected; inspect manually."*
  If `status_path.exists()` → proceed with the existing phase-gate table (no behaviour change for the happy path).
- **Rationale:** Symmetric with `mill-merge`'s existing fallback (uses the same `_client.get_task` helper) — operators get the same recovery story across both entry points. Telling the operator to run `/mill-merge` rather than auto-invoking it preserves the audit trail and keeps mill-go's surface lean (no auto-dispatch from a phase gate).
- **Rejected:**
  - Auto-invoke `/mill-merge` on the absent-status branch — risky (the operator may have deleted status.md intentionally; auto-recovery hides that signal). Also adds a cross-skill invocation surface that we don't currently have.
  - Generic "merge-incomplete" halt without checking the wiki — leaves the operator to debug the actual state; with the wiki probe we can tell them exactly which command to run.

### fixer-implementer-git-env-isolation

- **Decision:** In `_llm_claude._invoke` (the shared dispatch path for both implementer and fixer subprocess spawns), build an explicit child env that **strips** `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` before passing the env to `_subprocess_util.run`. The Python implementation: `env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k in {"GIT_PYTHON_REFRESH"}}` — a strict-allowlist would be safer but breaks if Claude CLI later adds a benign `GIT_*` it needs; the blocklist covers the known-dangerous surface. Apply to both implementer (`millpy-implement.py`) and fixer (`millpy-fix.py`) dispatches via the shared `_invoke` change. Document in the implementer and fixer brief templates: *"Do not `cd` outside the task worktree. Use `git -C <path>` for cross-repo reads or the Read tool for fixture inspection. The Bash tool's cwd persists between calls — `cd <fixture>` corrupts every subsequent git operation."*
- **Rationale:** The reported incident (#367) was caused by env-level GIT_DIR pollution from a test fixture. Stripping these vars from the child env at dispatch removes the entire mechanism. Symmetric application to implementer + fixer is mandatory because the same subprocess path serves both; protecting one without the other leaves a known-reproducible hole. Brief-level documentation of the cwd-drift concern complements the env strip — env isolation prevents inherited pollution, but the session can still `cd` into a fixture mid-run, and the brief is the only surface that can warn against that.
- **Rejected:**
  - Set `GIT_DIR=<worktree>/.git` + `GIT_WORK_TREE=<worktree>` explicitly — breaks `git -C <parent>` cross-worktree reads documented as allowed in CLAUDE.md `## Worktree isolation`. With `GIT_DIR` set, git ignores cwd and `-C`'s pre-cd and always operates on the env-pinned repo.
  - Strip env only for fixer (not implementer) — same subprocess surface; same risk. The implementer's longer running time arguably makes its env exposure *worse* than the fixer's.
  - Lock cwd via a Bash wrapper that auto-cd's back to worktree — fragile; doesn't survive subshells; adds a new surface to maintain.
  - Allowlist instead of blocklist for `GIT_*` env vars — too brittle as Claude CLI evolves; blocklist of the known-dangerous set is the right cost/safety trade.

### cli-commit-author-pinning

- **Decision:** Add a helper `_subprocess_util.git_commit(cwd, message, *, name, email)` that wraps `git -c user.name="$NAME" -c user.email="$EMAIL" commit -m "$MESSAGE"` (and returns the same `CompletedProcess` shape as `_subprocess_util.run`). `millpy-fix.py` and `millpy-implement.py` resolve `name` and `email` once at script start by calling `git config --global --get user.name` / `--get user.email` (failing fast with a clear stderr message if either is unset, since we cannot author a commit without identity). Every CLI state commit in both scripts goes through `_subprocess_util.git_commit(...)` instead of bare `["git", "commit", "-m", ...]`.
- **Rationale:** Worktree-local config drift (incident #368: fixer ran `git config user.email test@test.com`) becomes irrelevant for CLI state commits because the explicit `-c` flags override local config. Reading the intended identity from `--global` is robust to the very pollution we're guarding against. Centralising in a helper keeps the call sites readable and ensures the pattern is uniformly applied across both CLIs. Failing fast on missing global identity surfaces the misconfiguration immediately rather than producing commits with `(no author)` or similar garbage.
- **Rejected:**
  - Save+restore worktree-local user.name/email around fixer dispatch — restore correctness is its own footgun (what if dispatch crashes mid-flight?). The `-c` flag approach is stateless and immune to dispatch failure modes.
  - Both save+restore *and* `-c` flags — defense in depth doesn't justify the additional code surface when the `-c` flags fully fix the reported incident.
  - Read `name`/`email` from a `mill-config.yaml` key — adds a config field for something git already knows; new config keys must justify their existence.
  - Apply the pattern to Builder Bash commits in `mill-go` and `mill-merge` (e.g. Prepare, Approve, archive-tag teardown) — these run from the Builder thread's Bash tool, not from a Python CLI, and are out of scope for this task. Extending coverage there is a follow-up.

### scope-boundaries

- **Decision:** Touch only the surfaces enumerated under **Scope: In** above. Specifically: per-card commits from inside the implementer/fixer LLM session (issued via `git-commit` skill) are NOT modified — they run inside the session's git environment and the `-c` flag pattern doesn't transfer cleanly. Builder Bash commits in `mill-go`/`mill-merge` are NOT modified. The wiki daemon write path is NOT modified.
- **Rationale:** Each #-issue maps to a specific dispatch surface (CLI subprocess, SKILL.md doc, helper module). Broadening to per-card commits or Builder Bash would expand the change set without addressing any of the incidents on the docket.
- **Rejected:** Whole-pipeline author/env hardening pass — would conflate this task with a much larger refactor and dilute the unit-test surface.

## Technical context

Key files touched (relative to repo root `plugins/mill/`):

- `skills/mill-merge/SKILL.md` — Step 6 (archive tag) gets the conflict-resolution block. The Step 6 location is documented at line ~180–187 in the skill body; the operator-facing Bash text needs to be replaced with the smart-resolution form. The SKILL is interpreted by the Builder thread (mill-merge runs from the child worktree), so the documented commands are what the Builder Bash-tool calls execute.
- `skills/mill-merge-in/SKILL.md` — Step 3, conflict-resolution table. The "Real code conflicts" row already says `git merge --continue`; replace with `git -c core.editor=true merge --continue` (one-line edit). The "non-conflict" merge path uses `git merge <parent-branch>` which is non-interactive on no-conflict merges — that path is unchanged.
- `skills/mill-go/SKILL.md` — Entry Step 5 phase gate. The current text is:
  ```python
  status = _status.read_full(status_path)
  phase = status["yaml"]["phase"]
  ```
  This crashes on `FileNotFoundError` when `status_path` is gone. The new block wraps with `if not status_path.exists(): <wiki fallback>`. Use the existing `from wiki import _client` import pattern already documented in mill-merge SKILL Step 5.
- `scripts/_llm_claude.py` — `_invoke()` (around line 274) is the only dispatch path; both `run_implementer` and `run_bulk`/`run_tool_use` route through it. Add an env-strip step before passing env to `_subprocess_util.run`. The strip set is fixed: `{"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"}`. The env-strip applies on both the `_get_via_psmux_flag()` branch (line ~297) and the direct-spawn branch (line ~334). Same logic, two call sites.
- `scripts/_subprocess_util.py` — Add `git_commit(cwd, message, *, name, email) -> CompletedProcess`. Implementation: `return run(["git", "-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-m", message], cwd=cwd)`. Reuse the existing `run()` for env, encoding, watchdog semantics.
- `scripts/millpy-fix.py` — Two `["git", "commit", "-m", ...]` call sites (one per scope, lines ~170 and ~218) become `_subprocess_util.git_commit(project_root, "...", name=git_name, email=git_email)`. Resolve `git_name` and `git_email` once at script start (after `cfg` load, before any commit). Use:
  ```python
  git_name = _subprocess_util.run(["git", "config", "--global", "--get", "user.name"], cwd=project_root).stdout.strip()
  git_email = _subprocess_util.run(["git", "config", "--global", "--get", "user.email"], cwd=project_root).stdout.strip()
  if not git_name or not git_email:
      print("git global user.name and user.email must be set", file=sys.stderr)
      return 1
  ```
- `scripts/millpy-implement.py` — Same pattern as millpy-fix.py. The script's existing CLI state commits (batch-start in particular) get the same `_subprocess_util.git_commit` treatment.
- `templates/fixer-batch-brief.md`, `templates/fixer-holistic-brief.md`, `templates/implementer-brief.md` — append a `## Cwd discipline` section (or extend the existing constraints block) with the documented warning. Brief templates already exist; we add a short paragraph, not a new file.
- `unit_tests/test-archive-tag-conflict.py` (new) — Tests are pure-Python: build a tmp git repo via `subprocess.run(["git", "init"], cwd=tmp)`, create tag, run the resolution helper (extract the logic into `_archive_tag.py` if it makes the test cleaner; otherwise call a Python wrapper that runs the same Bash). Mill-plan owns the exact split.
- `unit_tests/test-fixer-env-isolation.py` (new) — Monkey-patch `_subprocess_util.run` to capture the `env=` kwarg passed by `_invoke`; assert the strip set is absent.
- `unit_tests/test-cli-commit-author.py` (new) — Tmp git repo + tmp worktree config with `user.email=test@test.com`; call `_subprocess_util.git_commit(...)` with explicit name/email; `git log --format=%ae` returns the explicit email, not the local config.
- `unit_tests/test-mill-go-status-absent.py` (new) — Monkey-patch `_client.get_task` to return each branch in the table; assert the correct halt message is emitted. The SKILL itself is not Python so the test exercises the helper(s) the SKILL invokes — likely a small `_phase_gate.py` extract is the cleanest way to make this testable (mill-plan decides).

Shared helpers that **must** be reused (not reimplemented):

- `_paths.resolve_git_root`, `_paths.resolve_wiki_path`, `_paths.resolve_task_path` for all path resolution.
- `_status.read_full`, `_status.append_phase`, `_status.set_batch_fields` for status mutations.
- `_client.get_task` for the mill-go absent-status fallback (matches mill-merge's existing pattern).
- `_subprocess_util.run` for all subprocess spawning. The new `git_commit` helper wraps it.
- `_marker.slug_from_branch` for slug resolution (already used in both scripts).

Gotchas:

- The `_invoke` function in `_llm_claude.py` has two subprocess-spawn branches (psmux and direct); both must get the env strip.
- The strip set must not include `GIT_PAGER`, `GIT_TERMINAL_PROMPT`, etc. — those are user-experience env vars, not state-affecting ones. Only the seven listed above are correctness-affecting.
- `git config --global --get user.email` exits with code 1 and empty stdout when the key is unset; the script's resolution code must handle that without crashing the script.
- The `archive/<slug>-<NN>` move-aside collision check must be deterministic across re-runs — list existing matching tags via `git tag -l "archive/<slug>-*"`, parse the suffixes, pick the lowest unused.
- The SKILL.md edits for #356, #357, #358 are interpreted by an LLM (Builder thread); the prose must be precise. Avoid ambiguous phrasing like "handle the conflict" — spell out the exact Bash commands per branch.
- `git push --force-with-lease` (not `--force`) is mandatory for the archive-tag force-update branch to avoid clobbering a concurrent operator push. Same convention used elsewhere in the codebase (verify in mill-merge-in if any precedent exists; if not, document the choice).

## Constraints

- **CLAUDE.md `## Path invariants`** — all path resolution through `_paths.py`. The new code must not construct hub or worktree paths manually.
- **CLAUDE.md `## Hard constraints`** — `${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths in SKILL.md text. The mill-go SKILL.md edit for #358 stays within this rule.
- **CLAUDE.md `## Worktree isolation`** — child worktrees may read parent state via `git -C <parent-path>`. This is why option 3 in the env-isolation decision (explicit `GIT_DIR` set) was rejected: it would block this documented pattern.
- **CLAUDE.md `## Script invocation`** — verify commands in plan files must use `PYTHONPATH=` literal-empty prefix. The new unit tests run via `uv run --project plugins/mill`, not the cache form; this is the documented exception for tests.
- **`print()` / `_log()` output: ASCII only** — every new stderr/stdout line in `_llm_claude`, `_subprocess_util`, `millpy-fix`, `millpy-implement` must be ASCII (`->` not `→`, `--` not `—`).
- **Wiki access** — mill-go's `_client.get_task` call respects the daemon-serialised wiki invariant. No `cd .wiki/` ever.
- **`mill-config.yaml` template parity** — none of these changes add config keys, so no template update is needed.

## Testing

- **TDD candidates:**
  - `_subprocess_util.git_commit` — write the test first; the helper is a thin wrapper with deterministic behaviour. Easy to assert via `subprocess.run(["git", "log", "--format=%an <%ae>"], ...)` on a tmp repo.
  - `_llm_claude._invoke` env-strip — write `test-fixer-env-isolation.py` first by monkey-patching `_subprocess_util.run` to capture the env kwarg, then make `_invoke` pass the assertion.
  - Archive-tag conflict resolution helper — if the resolution logic is extracted into `_archive_tag.py` (mill-plan call), write the test against the three branches before writing the helper.
- **Scenarios that MUST be covered:**
  - Archive tag: same-SHA (no-op), ancestor-SHA (force-update succeeds), divergent-SHA (move-aside to `-01` succeeds; second divergence in same task moves to `-02`).
  - Fixer env: confirm the seven listed env vars are stripped; confirm benign env vars (`PATH`, `HOME`, `CLAUDE_PLUGIN_ROOT`, `PYTHONPATH`) survive.
  - CLI commit author: fixture worktree with `user.email=test@test.com` in `.git/config`; CLI commit lands with the explicit `-c` author; fixture's local config remains polluted (i.e., we do *not* save+restore — and that's intentional).
  - mill-go absent-status fallback: each branch (`ready-to-merge`, `pr-pending`, `done`, `None`, unknown) emits the correct halt message. Monkey-patch `_client.get_task` to fixture each branch.
- **Out of test scope:**
  - The `git -c core.editor=true merge --continue` change is a SKILL.md doc edit only — no test surface. Operator behaviour following the documented command is verified by usage.
  - End-to-end mill-merge re-run after partial failure (integration). YAGNI for this task — the unit tests cover the failure-mode-level guarantees that the incidents named.
- **Test framework conventions:**
  - Use `plugins/mill/unit_tests/test-<name>.py` naming.
  - In-memory and tmpfile fixtures only; no real LLM calls; real git is acceptable (`subprocess.run(["git", "init"], cwd=tmp)`) per existing patterns in `plugins/mill/unit_tests/`.
  - Verify via `run-all.py` discovery.

## Q&A log

- **Q:** Archive-tag conflict policy when `archive/<slug>` already exists? **A:** [auto-pick] Smart resolution: same-SHA → no-op; ancestor-SHA → force-update; divergent → move-aside to `archive/<slug>-<NN>`. **Why:** covers idempotent re-runs (common), supports stacked cleanup, preserves prior tags on divergence.
- **Q:** How to suppress the editor prompt on `git merge --continue`? **A:** [auto-pick] Update `mill-merge-in/SKILL.md` Step 3 to use `git -c core.editor=true merge --continue`. **Why:** portable across PowerShell + Bash, scoped to single command, no env-var leak, no new helper code.
- **Q:** How should mill-go's entry-phase gate handle missing `_mill/status.md`? **A:** [auto-pick] Mirror mill-merge's existing `_client.get_task` fallback; route the operator to `/mill-merge` when wiki shows `ready-to-merge`/`pr-pending`, halt with explanation in other branches. **Why:** symmetric recovery story with mill-merge; preserves operator audit trail by not auto-dispatching.
- **Q:** How to prevent inherited `GIT_DIR`/etc env pollution corrupting the fixer/implementer? **A:** [auto-pick] Strip `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_AUTHOR_*`, `GIT_COMMITTER_*` from child env in `_llm_claude._invoke`; apply uniformly to implementer + fixer; document cwd discipline in briefs. **Why:** root-cause fix for the env-pollution mechanism; doesn't break `git -C <parent>` cross-worktree reads documented in CLAUDE.md.
- **Q:** How to make CLI state commits robust to worktree-local `git config user.email` pollution? **A:** [auto-pick] Add `_subprocess_util.git_commit(cwd, message, *, name, email)` helper; resolve name/email from `git config --global` once at script start; route every CLI state commit in `millpy-fix.py` and `millpy-implement.py` through it. **Why:** stateless fix; CLI commits become immune to local config drift; fail-fast if global identity unset.
- **Q:** What test surface? **A:** [auto-pick] Unit tests in `plugins/mill/unit_tests/` for each fix; no integration test. **Why:** YAGNI; the unit tests cover the specific failure modes called out in #356–#368.
- **Q:** Batching strategy? **A:** [auto-pick] Four independent batches: `archive-tag` (#356), `merge-continue` (#357, doc-only), `status-gate` (#358), `fixer-isolation` (#367+#368, shared dispatch surface). **Why:** clean isolation per issue; parallelisable; #367+#368 co-located because they touch the same files.
- **Q:** Should worktree-local user.name/email be saved+restored around fixer dispatch? **A:** [auto-pick] No — the `-c` flag approach on CLI commits fully fixes the reported incident; save/restore adds correctness-on-failure complexity without addressing a real bug. **Why:** YAGNI; pollution to the worktree config is annoying but not load-bearing.
- **Q:** Should the `-c` author pattern also apply to Builder Bash commits in mill-go/mill-merge? **A:** [auto-pick] No — out of scope for this task. **Why:** the incidents documented are CLI state commits; broadening to Builder Bash would expand the change set without addressing any docketed issue. Follow-up task if needed.
- **Q:** Should we use an allowlist or blocklist for `GIT_*` env vars in the strip? **A:** [auto-pick] Blocklist of the seven known-dangerous vars (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`). **Why:** allowlist breaks if Claude CLI later needs a benign `GIT_*` var; blocklist covers the documented attack surface.
- **Q:** For the archive-tag force-update branch, `--force` or `--force-with-lease`? **A:** [auto-pick] `--force-with-lease`. **Why:** safer against concurrent operator pushes; standard convention elsewhere in the codebase.
