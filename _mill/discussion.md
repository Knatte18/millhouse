# Discussion: Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts

```yaml
task: Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts
slug: mill-implementer-and-dispatch-quality
status: discussing
parent: main
```

## Problem

Five defects in the mill agent-dispatch implementer pipeline (six source GitHub
issues) all share one theme: the implementer/stage-CLI layer either **crashes
unclearly** or **reports success it did not earn**, and the harness then either
blocks downstream (cleanliness gate) or merges work that violated the plan.

- **#514 / #520 — cwd-dependent hub resolution.** In `mill-go` agent-dispatch mode,
  the Builder invokes the per-stage CLIs (`millpy-implement.py`,
  `millpy-review-code.py`, `millpy-fix.py`) **directly**, bypassing `millpy-bg`'s
  cwd guard. On nested-hub repos (hub is a git **subdirectory**, e.g.
  `src/csharp/NORCE.Models`), the CLIs resolve `_mill/status.md` relative to
  `Path.cwd()`. When cwd is the git-root rather than the nested hub, they crash
  with a raw `ValueError: status file not found` traceback instead of resolving the
  hub or emitting an actionable error.
- **#521 — implementer self-terminates between cards.** In agent dispatch the
  `mill:mill-implementer` subagent ends its turn after a single per-card commit
  (e.g. "Now on to Card N+1") without finishing the batch or emitting the mandated
  JSON report. The brief has **no** directive forbidding mid-batch turn-yielding.
  Forces repeated Builder re-dispatches and breaks the finalize contract.
- **#516 — success reported with a dirty in-scope tree.** The implementer reports
  `{"status":"success"}` while leaving a tracked, in-scope file modified-but-
  uncommitted. The self-reported-success path does not check working-tree
  cleanliness; only mill-go's downstream 2b cleanliness gate catches it, blocking
  the batch and forcing a manual operator commit.
- **#519 — haiku implementer violates plan directives, verify stays green.** The
  default `haiku`-tier implementer changed `rewriteOriginURL` to use
  `git remote set-url` (contradicting a plan Shared Decision) and silently dropped
  two tests during a table-drive migration. Both passed `verify`, so the model saw
  no failure and self-reported success. Per-batch review was disabled (rounds: 0),
  so nothing caught it until holistic/manual review.
- **#522 — harness file-memory is useless in ephemeral worktrees.** A doc/skill
  gap: agents save project facts to the per-worktree harness `memory/` store, which
  is destroyed when the task worktree is torn down on merge/cleanup. `mill:workflow`
  (loaded on every startup) should tell agents to put durable notes in versioned
  files instead.

**Why now:** all five were filed from real downstream task runs (NORCE Models,
loomyard) in June 2026 and bundled because they cluster in the same
implementer/dispatch quality surface.

## Scope

**In:**

- Make the three agent-dispatch stage CLIs resolve the hub **cwd-independently**
  via `_paths.resolve_hub_path()`, and emit an **actionable error** (not a raw
  `ValueError`) if `_mill/status.md` is still missing.
- Add an explicit **"do NOT end your turn between cards"** directive to
  `implementer-brief.md`, plus a mechanical **batch-completeness gate**
  (content-commit count vs `### Card N` count) in the finalize path so an incomplete
  batch can never be reported (or inferred) as success.
- Add a mechanical **in-scope dirty-tree rejection** to the finalize success path
  (reusing `_cleanliness.compute_terminal_dirt`), plus a mandatory
  `git status --porcelain` self-check at the end of the implementer brief.
- Raise the **default implementer model** from `haiku` to `sonnethigh`, and
  strengthen the brief's **Test Integrity Guardrail** wording to explicitly forbid
  dropping/skipping tests and shared-decision-violating shortcuts (e.g.
  `git remote set-url`).
- Add a **one-line note to `mill:workflow`** that harness file-memory is ephemeral
  in task worktrees; durable notes belong in `CLAUDE.md`, `_codeguide/`, or code
  comments.

**Out:**

- No language-specific mechanical equivalence/test-superset enforcement (e.g.
  `go test -list` baseline diff). mill is language-agnostic; that is a separate,
  larger feature. We address #519 via model-tier + guardrail wording only.
- No mill-go agent-mode **auto-continue / SendMessage loop**. `SendMessage`/resume
  is not available in agent dispatch; re-dispatch stays a fresh, idempotent
  dispatch. The completeness gate's job is to **prevent false success**, not to
  build a re-dispatch loop.
- No change to `roles.fixer.model` or `merge.model` (both stay `haiku`); #519 is
  about the implementer specifically.
- No change to the cwd guard in `millpy-bg.py` itself (it already works for
  subprocess/psmux dispatch); we are closing the gap that agent-dispatch opened by
  bypassing it.
- No removal of mill-go's existing 2b cleanliness gate — it remains the
  authoritative revert+block layer; the new finalize check is an additional,
  earlier, dispatch-mode-independent rejection.

## Decisions

### hub-resolution-cwd-independent (#514 / #520)

- **Decision:** In `millpy-implement.py`, `millpy-fix.py`, and `millpy-review-code.py`,
  replace the cwd-derived hub/status anchoring with `_paths.resolve_hub_path()`
  (already cwd-independent — it walks up to the `.millhouse/config.local.yaml`
  marker and honors `hub_relative_path`). Specifically the `project_root = Path.cwd()`
  anchor used to build `status_path` becomes the resolved hub. After resolution, if
  `status.md` still does not exist, raise/return a **clear, actionable error**
  ("run from the task hub dir `<path>`", mirroring `millpy-bg`'s non-task-worktree
  message) with a clean exit code — never a raw `ValueError` traceback.
- **Rationale:** `_paths.resolve_hub_path()` is already the cwd-independent contract
  used by mill-go's inline-Python steps and by `millpy-review-code.py`'s
  `load_config` call; the implement/fix CLIs are simply inconsistent. Fixing the
  resolution (not just the error message) makes agent-dispatch from any cwd work,
  which is the actual breakage. The actionable error is a defensive backstop for the
  genuinely-misconfigured case.
- **Rejected:** Error-message-only (issue's option b) — leaves agent-dispatch broken;
  the operator would still have to re-run from the hub. Adding a `--root`/`--hub`
  CLI flag — unnecessary; the marker-based resolution already knows the hub.

### implementer-no-yield-and-completeness (#521)

- **Decision:** Two layers. (1) Add an explicit directive near the top of
  `implementer-brief.md`: do **not** end your turn between cards — only stop when all
  `### Card N` entries are committed, `## Verify` has run, and the JSON report is
  emitted. Combine with the existing Long-session reminder (emit JSON as the first
  line of the final turn). (2) Add a mechanical **batch-completeness gate** in the
  finalize path (`_implementer_common._forward_output`): count `### Card N` headings
  in the batch file and count content commits since `start_sha`; if commits <
  cards, the batch is incomplete — demote any self-reported (or inferred) success to
  `stuck` rather than reporting success. Apply to both the self-reported-success and
  inferred-success branches.
- **Rationale:** The brief directive is the primary prevention (make the agent finish
  in one turn). The completeness gate is a cheap, language-agnostic safety net:
  "one commit per card" is already brief policy, so `commits_since_start >= card_count`
  is a sound lower-bound completeness signal (extra commits — formatter drift,
  plan-extend — only inflate the count, so `commits < cards` reliably means
  incomplete). This guarantees an incomplete batch can never slip through as success,
  which is the core of #521. Recommended stuck_type: `transient` (mill-go's existing
  one-shot retry gives a free continuation; a fresh re-dispatch resumes because
  committed cards and `start_sha` persist in status.md), surfacing to the operator if
  still incomplete after the retry.
- **Rejected:** mill-go agent-mode auto-continue loop via `SendMessage` — not
  available in agent dispatch; would be fresh re-dispatch anyway and is larger scope.
  Brief-directive-only — issue explicitly notes brief-strengthening mitigates but
  does not fully prevent; the mechanical gate is needed to close the false-success
  hole.

### finalize-rejects-dirty-in-scope-tree (#516)

- **Decision:** In the finalize success path of `_implementer_common._forward_output`,
  after the verify gate and the existing no-content-commit check, compute in-scope
  dirt via `_cleanliness.compute_terminal_dirt(worktree, task_dir, parent_branch)`
  (read-only — it does **not** revert) and, if the result is non-empty, demote the
  success to `stuck` (e.g. `stuck_type: logic`, reason "success reported but in-scope
  tree dirty"). Thread `task_dir` and `parent_branch` (resolved from `status_path` /
  status.md, as mill-go's 2b gate does) into `_forward_output`. Also add a mandatory
  `git status --porcelain` self-check to the end of `implementer-brief.md`:
  commit-or-report-stuck before emitting the JSON line.
- **Rationale:** Moves the dirty-tree check **to the source** (the CLI) so it fires in
  both subprocess and agent dispatch, and rejects the implementer's report rather than
  letting a false success propagate to the downstream gate. Using the read-only
  `compute_terminal_dirt` (vs `revert_out_of_scope_drift`) keeps reverting as mill-go
  2b's sole responsibility — the finalize check only rejects, avoiding surprising
  double-reverts. The brief self-check addresses the model-level cause.
- **Rejected:** Brief-self-check-only — no mechanical backstop; the model already
  failed to self-police. Status-quo (rely on mill-go 2b gate only) — the implementer
  still emits false success and the failure surfaces late as a hard block requiring a
  manual commit.

### raise-implementer-tier-and-guardrail (#519)

- **Decision:** Change the shipped template default `roles.implementer.model` from
  `haiku` to `sonnethigh` (`plugins/mill/templates/mill-config.yaml`; the code default
  in `millpy-implement.py` is already `sonnethigh`, so this aligns template with code).
  Strengthen the brief's `## Test Integrity Guardrail` to explicitly forbid: dropping,
  skipping, or omitting any pre-existing test during a migration/refactor (the post
  set must include every pre test), and taking shared-decision-violating shortcuts
  (call out `git remote set-url` as the concrete example) to make verify pass.
- **Rationale:** haiku self-policing is the demonstrated failure mode for non-trivial
  migration work; verify being green gives the weak model no corrective signal. A
  capable default tier plus sharper guardrail wording is the proportionate fix.
  Keep the hub `mill-config.yaml` overlay and the plugin template in sync (project
  convention).
- **Rejected:** Mechanical test-list baseline (`go test -list` superset diff) — strong
  but language-specific and a large separate feature, against mill's language-agnostic
  design. Keep-haiku-plus-guidance (enable per-batch review for migrations) — relies on
  per-task config the operator may forget; doesn't fix the default failure mode.

### workflow-ephemeral-memory-note (#522)

- **Decision:** Add a single sentence to `plugins/mill/skills/workflow/SKILL.md`,
  immediately after the `## Wiki mutations` paragraph (the existing "what state is
  durable vs not" bucket): harness file-memory (the `memory/` dir) is ephemeral in
  task worktrees and is discarded when the worktree is removed; durable notes belong
  in `CLAUDE.md`, `_codeguide/`, or code comments.
- **Rationale:** `mill:workflow` is loaded on every startup and is the global home for
  rules that apply to every mill-managed repo; mill is what creates the ephemeral
  worktrees, so the rule belongs in mill rather than each repo's CLAUDE.md.
- **Rejected:** A dedicated new section/heading — heavier than warranted for one line;
  the `## Wiki mutations` adjacency is the most topically coherent placement.

## Technical context

Key files and the cwd-independent contract:

- `plugins/mill/scripts/_paths.py` — `resolve_hub_path()` (≈153-219) walks up from cwd
  to the `.millhouse/config.local.yaml` marker, honoring `hub_relative_path`; this is
  the cwd-independent hub resolver already used elsewhere. `status_path(project_root, cfg)`
  joins the hub with `paths.status_md`.
- `plugins/mill/scripts/millpy-implement.py` — `project_root = Path.cwd()` (~102),
  `status_path = _paths.status_path(project_root, cfg)` (~129), unconditional
  `_status.read_full(status_path)` (~130) in `main()` before the stage branch (so
  `prepare`/`finalize`/`full` all hit it). `load_config(git_root, mill_dir)` passes
  cwd-derived `git_root` as hub_root (~109). Renders `implementer-brief.md` (~257-270);
  reads `roles.implementer.model` (~146, default `sonnethigh`); reads
  `verify_cmd`/overview path from the batch (~159, ~305-308).
- `plugins/mill/scripts/millpy-fix.py` — same cwd-anchored pattern:
  `project_root = Path.cwd()` (~120), `status_path` (~146), `read_full` (~147).
- `plugins/mill/scripts/millpy-review-code.py` — already calls `resolve_hub_path()` for
  `load_config` (~96) but `project_root`/`mill_dir` remain cwd-based (~92-94); align it.
- `plugins/mill/scripts/_status.py` — `read_full` raises the raw
  `ValueError: status file not found` at ~630-631 (also ~169, ~556). The CLIs do not
  try/except it.
- `plugins/mill/scripts/millpy-bg.py` — the model for the actionable error: the
  non-task-worktree guard at ~159-170 (catches `_marker.MarkerError`, prints a clear
  "switch to the task-worktree terminal" message, returns 1).
- `plugins/mill/templates/implementer-brief.md` — sections: `## Inputs` (~30),
  `## Implementation discipline` (~42; card handling + per-card `git-commit` skill at
  ~44-49; "one commit per card" at ~48), `## Test Integrity Guardrail` (~58-60),
  `## Verify` (~62-69), `## Report` (~71-100; single-final-turn JSON contract +
  Long-session reminder at ~100), `## On review resume` (~102). No anti-yield directive
  today.
- `plugins/mill/scripts/_implementer_common.py` — `_forward_output(output, project_root, *, start_sha, snapshot_path, session_id, verify_cmd)`
  (311). Self-reported-success path: verify gate (~333), no-content-commit check
  (~345-359), then enrich `commit_sha` + `scope_violations` (~361-369). Inferred-success
  fallback (~374-451) runs `compute_new_dirt` and the formatter-drift auto-commit.
  `_extract_status_json` (280) takes the **last** balanced-brace `{...}` with a `status`
  key. `finalize_from_output` (255) reads the agent-output file and delegates here. Both
  new checks (completeness, dirty-tree) go here; thread `batch_file`/`card_count`,
  `task_dir`, `parent_branch` from `millpy-implement.py`.
- `plugins/mill/scripts/_cleanliness.py` — `compute_terminal_dirt(worktree, task_dir, parent_branch)`
  (119-148) is the **read-only** in-scope dirt computation to reuse for #516.
  `revert_out_of_scope_drift` (151) is what mill-go 2b uses (revert + block) — do not
  call it from finalize. `compute_scope_violations` (54) flags untracked out-of-scope
  files (already attached to reports).
- `plugins/mill/skills/mill-go/SKILL.md` — "Agent-mode dispatch" (~105-139): synchronous
  one-shot Agent tool, output captured to `<brief>.out.md`, no SendMessage/resume;
  re-dispatch is fresh. The 2b cleanliness gate (~241-266) resolves `parent_branch` via
  `_parent_branch.resolve(status_path)` and `task_dir` from `status_path.parent` — reuse
  the same resolution to feed the finalize dirty-tree check.
- `plugins/mill/templates/mill-config.yaml` — `roles.implementer.model: haiku` (~169) →
  `sonnethigh`; keep the hub `mill-config.yaml` overlay in sync (project convention).
- `plugins/mill/templates/plan-batch.md` — cards are `### Card N: <title>` under
  `## Cards` (~40-58); the completeness gate counts these headings.
- `plugins/mill/skills/workflow/SKILL.md` — `## Wiki mutations` paragraph is the
  insertion point for the #522 note.

Card-completeness count is mechanical and language-agnostic: number of `### Card`
headings in the batch file vs `git rev-list --count <start_sha>..HEAD` content commits
(excluding the prepare pre-commit / any empty commits as appropriate).

## Constraints

(No `CONSTRAINTS.md` at the hub root.) Repo conventions that bound this work:

- **ASCII-only stdout** in Python helpers (`print`/`_log`): `—`→` -- `, `->`→` -> `.
  Windows cp1252 crashes on non-ASCII stdout.
- **`${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths**; never hard-code `plugins/mill/…`
  in shipped commands.
- **Plan `verify:` for this Python project must start with `PYTHONPATH=`** (literal,
  empty value, single space) so the test subprocess loads worktree code, not the
  V2-cache modules. Enforced by `_plan_validate.py`'s `verify-not-isolated` check.
- **Unit tests** live in `plugins/mill/unit_tests/` as `test-<name>.py`, run via
  `run-all.py`, use in-memory/tempfile fixtures (no real git/LLM). Integration tests
  (`integration_tests/`) may invoke real git in `.scratch/`.
- **Hub `mill-config.yaml` and the plugin template must stay in sync** (template seeds
  new hubs) — applies to the implementer-model default change.
- **Stage CLIs must not break subprocess/psmux dispatch** while fixing agent dispatch;
  cwd-independent resolution must remain correct when cwd **is** the hub.

## Testing

Unit tests (tempfile/in-memory git fixtures; no real LLM), per fix:

- **hub-resolution (#514/#520):** Build a nested-hub fixture (hub in a git subdir).
  Assert `millpy-implement.py`/`millpy-fix.py`/`millpy-review-code.py` resolve
  `status.md` correctly when cwd = git-root (not the hub). Assert that when `status.md`
  is genuinely absent, the CLI returns a clean non-zero exit with the actionable
  "run from the task hub dir" message — not a raw `ValueError` traceback. Regression:
  resolution still correct when cwd = hub.
- **completeness gate (#521):** TDD `_forward_output` (or a helper it calls). Given a
  batch with N `### Card` headings and a git log with < N content commits since
  `start_sha`, assert a self-reported success is demoted to `stuck` (transient).
  Assert commits == N (and > N with extra drift/plan-extend commits) yields success.
  Assert the inferred-success branch is likewise gated.
- **dirty-tree rejection (#516):** Fixture worktree with an uncommitted in-scope
  tracked file. Assert a self-reported success is demoted to `stuck` ("in-scope tree
  dirty"). Assert out-of-scope dirt does **not** trigger the rejection (parity with
  `compute_terminal_dirt` scope semantics). Assert a clean in-scope tree still reports
  success.
- **implementer-model default (#519):** Assert the shipped template
  `roles.implementer.model` resolves to `sonnethigh` (template-vs-code-default
  alignment); the guardrail wording change is template prose (covered by review, no
  unit test).
- **workflow note (#522):** No automated test — skill markdown; verified by review.

Brief/template changes (anti-yield directive, self-check, guardrail wording, workflow
note) are prose and are validated by the discussion/plan/code review loop rather than
unit tests; ensure rendered-brief token substitution still passes any existing
`_render` tests.

## Q&A log

- **Q:** How should the stage CLIs locate the hub when cwd is git-root, not the nested
  hub? **A:** Cwd-independent resolution via `_paths.resolve_hub_path()` **plus** an
  actionable error if status.md is still missing — fixes the real agent-dispatch
  breakage, not just the message.
- **Q:** Beyond a brief directive, add a mechanical backstop for the implementer
  self-terminating between cards? **A:** Yes — brief anti-yield directive **and** a
  finalize completeness gate (content-commit count vs `### Card N` count) so an
  incomplete batch can never be reported/inferred as success. No SendMessage
  auto-continue loop (not available; out of scope).
- **Q:** Where to enforce "no success with a dirty in-scope tree"? **A:** Mechanical
  rejection in `millpy-implement` finalize (reuse read-only `compute_terminal_dirt`,
  demote to stuck) **plus** a `git status --porcelain` self-check in the brief. Keep
  mill-go's 2b gate as the authoritative revert+block layer.
- **Q:** How to address the haiku implementer violating plan directives while verify is
  green? **A:** Raise the default `roles.implementer.model` `haiku`→`sonnethigh` and
  strengthen the Test Integrity Guardrail wording (forbid dropping tests / shared-
  decision-violating shortcuts like `git remote set-url`). Defer language-specific
  mechanical test-superset enforcement.
- **Q:** Scope of #519 — also raise fixer/merge model tiers? **A:** No. Keep
  `roles.fixer.model` and `merge.model` at `haiku`; #519 is implementer-specific.
- **Q:** Should the finalize dirty-tree check revert out-of-scope drift like mill-go's
  2b gate? **A:** No — finalize is read-only (reject only); reverting stays mill-go 2b's
  responsibility to avoid surprising double-reverts.
```
