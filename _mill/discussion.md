# Discussion: Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch

```yaml
task: Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch
slug: mill-config-and-brief-gaps
status: discussing
parent: main
```

## Problem

Two unrelated small defects, bundled because both are low-risk hygiene fixes around config loading and the dispatch flow.

**Gap A — spurious config warning (#511, CLOSED issue, observed on loomyard / `weft-repo`).**
On every config load, `_config.warn_unknown_keys` emits `[config] unknown key: git (in merged config)` to stderr. During a single `mill-go` run this fires dozens of times (once per implement/review/fix dispatch's `load_config`). The `git` namespace holds legitimate keys consumed by skills — `git.parent-branch` (git-pr), `git.require_pr_to_base` and `git.base_branch` (mill-merge) — but the namespace is not registered in the config schema. The validator treats the **plugin template** (`plugins/mill/templates/mill-config.yaml`) as the schema-of-record: any top-level key in the merged config that is absent from the template is flagged. The template's `git:` block is entirely commented out, so `git` is "unknown."

**Gap B — dispatch briefs are never committed and are lost.**
Each agent dispatch writes a "brief" (the fully-rendered agent prompt) to `_mill/briefs/<role>-<scope>-r<n>.md`, and mill-go additionally writes the agent's response to `<brief>.out.md` in the same directory. A prior change (`track-task-briefs`) removed the `_mill/briefs/` line from `.gitignore`, so these files are tracked-eligible but **untracked** — nothing `git add`s them. They sit in the worktree and are wiped when `/mill-cleanup` removes the worktree after merge, so they never reach branch history / the archive tag. **why now:** the briefs are the audit trail of what each sub-agent was actually told and what it returned; losing them removes the only record for post-mortems.

Exploration corrected the originally-reported scope of Gap B (see Technical context): most dispatch paths already commit briefs. Only two orchestrators have the gap.

## Scope

**In:**

- **Gap A:** Register the `git` namespace in the plugin template schema (`plugins/mill/templates/mill-config.yaml`) by replacing the commented `git:` block with a real, populated one containing the three known subkeys at behavior-no-op defaults. Add unit-test coverage in `plugins/mill/unit_tests/test-config.py`.
- **Gap B:** Make brief-committing uniform across all orchestrators that dispatch briefs, following the existing "everything in `_mill/` gets committed by the orchestrator" pattern. Concretely:
  - **mill-start** (`SKILL.md`): add `_mill/briefs/` to the commit pathspecs of every commit that runs after a discussion-review round has produced a brief — step 4b (discussion-fix, interactive **and** `--auto`), step 5 (discussion-gap-fix), and Handoff. Also the two `--auto` halt-commits (ERROR-only blocked, gaps-unresolved blocked) for audit completeness, guarded for absence.
  - **mill-merge-in** (`SKILL.md`): add a dedicated brief-commit step near the end of the flow (after step 4 Verify succeeds, before the success report), guarded for absence, that stages and commits `_mill/briefs/`. This captures **both** brief types at the correct time: the `merge/conflicts` brief (written in step 3 during conflict resolution, line ~243) and the `merge/verify-fix` brief (written in step 4, line ~324, *after* the step-3 `git merge --continue`). A single trailing commit avoids the timing trap of staging before `merge --continue` (which cannot capture the later verify-fix brief) and also covers the clean-merge case (no conflicts), where `merge --continue` never runs. On a fully clean merge with passing verify, no brief is written and the guarded step is a no-op. If mill-merge-in rolls back to its checkpoint on stuck, the briefs are discarded with everything else (consistent — nothing special needed).

**Out:**

- **No change to mill-go or mill-plan** — they already stage `_mill/briefs/` in every relevant commit step (verified; see Technical context). Do not touch them.
- **No change to the dispatch CLIs** (`millpy-implement.py`, `millpy-fix.py`, `millpy-review-*.py`, `millpy-merge-in-subagent.py`). The fix lives at the orchestrator (frontend) layer, not the API layer — per the operator's directive "follow the same setup as everything else committed in `_mill/`." (The wiki proposal's suggestion to add a commit step inside each CLI's finalize stage is explicitly **rejected** — see Decisions.)
- **No `.gitignore` change** — `_mill/briefs/` is already un-ignored (only `**/_mill/*.active` is ignored). 
- **No change to the hub `mill-config.yaml`** at the repo root — it is a sparse overlay that sets no `git` keys, so it neither triggers the warning nor needs the block. (See Decisions / sync note.)
- **No unification of `git.parent-branch` and `git.base_branch`** — they are distinct concepts (parent = the branch a task was spawned from; base = the canonical PR target; they legitimately differ, e.g. parent `develop` / base `main`). Both are registered as separate keys.
- **No fix to git-pr's config-file read path.** git-pr reads `git.parent-branch` from `.millhouse/config.yaml` (a file outside the `load_config` merge chain). Whether that read is correct is a separate concern; this task only silences the merged-config validator warning.
- **No broader audit/refactor of the config validator.** Only the `git` namespace is registered.

## Decisions

### Gap A — register git via a populated template block (not a validator allowlist)

- Decision: Replace the commented `git:` block in `plugins/mill/templates/mill-config.yaml` (currently lines ~80-82) with a real block:
  ```yaml
  git:
    parent-branch: null         # consumed by git-pr (reads .millhouse/config.yaml); null/absent -> falls back to arg/main
    require_pr_to_base: false    # consumed by mill-merge; true -> open a PR instead of pushing directly
    base_branch: main            # consumed by mill-merge; PR --base target; falls back to main if absent
  ```
  Keep the surrounding explanatory comments. **Note:** only `require_pr_to_base` and `base_branch` exist in the current commented example (template lines ~81-82); `parent-branch: null` is **net-new** — the planner adds it, it is not an uncomment. The validator (`walk_unknown_keys`) uses the template dict as the schema, so the three subkeys become "known," and any other `git.*` key (a typo, an unknown future key) still correctly warns.
- Rationale: The template is the schema-of-record; a populated block both registers the keys and self-documents them. Defaults are behavior-no-ops: `require_pr_to_base: false` and `base_branch: main` match the existing documented fallbacks in mill-merge, and `parent-branch: null` never reaches git-pr (which reads a different file), so seeding it into the merged config changes nothing. Descending into the `git` dict preserves typo-catching, which an allowlist would lose.
- Rejected: (a) **Validator allowlist** — add `git` to a known-namespaces set in `warn_unknown_keys` (like the existing `deprecated_keys`). Zero merged-config change, but it suppresses ALL `git.*` keys including typos and adds a second special-case to the validator. (b) **Unify parent-branch/base_branch** — out of scope; they are distinct concepts.

### Gap B — commit briefs at the orchestrator layer, uniformly

- Decision: Briefs are a `_mill/` artifact and must be committed the same way every other `_mill/` artifact is — folded into the orchestrator's existing `_mill/` commits via `git add _mill/briefs/`, not by a new commit mechanism inside the CLIs. Extend the pattern to the two orchestrators missing it (mill-start, mill-merge-in).
- Rationale: This is the operator's explicit directive and matches what mill-go and mill-plan already do (they stage `_mill/briefs/` in their approve/done/plan-fix commits). `git add _mill/briefs/` captures both the brief `.md` and any `.out.md` response in one pathspec. Committing at orchestrator milestones (rather than per-CLI) keeps history clean and consistent.
- Rejected: **Per-CLI finalize commit** (the wiki proposal). Although the CLIs already perform git commits (e.g. `millpy-implement.py`'s "start batch" commit), a dedicated brief commit per dispatch adds commit noise and diverges from how the rest of `_mill/` is handled. The operator chose the orchestrator-consistent approach.

### Gap B — guard the brief `git add` against an absent/empty briefs dir

- Decision: Where a commit step may run **without** any brief having been written (mill-start Handoff reached via the review-skip path when `rounds: 0` or `reviewer: null`; the `--auto` halt-commits; and **mill-merge-in's trailing brief-commit on a clean merge** with no conflict and passing verify), guard the add so a missing `_mill/briefs/` does not fail the commit: e.g. `if [ -d <worktree>/_mill/briefs ]; then git -C <worktree> add _mill/briefs/; fi`, or otherwise only include the pathspec when the directory exists.
- Rationale: `git add _mill/briefs/` errors with "did not match any files" if the directory does not exist. In mill-start's post-review commits (4b, 5) a brief always exists by construction, so an unguarded add is fine there; the skip/halt paths and mill-merge-in's trailing step need the guard (a clean merge writes no brief).
- Rejected: Unconditionally creating an empty `_mill/briefs/` dir just to satisfy `git add` — git does not track empty dirs, so it would not help.

## Technical context

Key files and current behavior (verified during exploration):

- **`plugins/mill/scripts/_config.py`** — `walk_unknown_keys(actual, template)` (line ~89) flags any key in the merged config absent from the template; `warn_unknown_keys` (line ~113) prints `[config] unknown key: <path> (in <label>)` and already carries a `deprecated_keys` suppression set. `load_config` (line ~193) loads the plugin template via `resolve_plugin_template_path("mill-config.yaml")` and deep-copies it as `template_cfg` — that copy is the schema passed to the validator.
- **`plugins/mill/templates/mill-config.yaml`** — the schema-of-record. The `git:` example block is currently commented out (only `require_pr_to_base` and `base_branch`, lines ~81-82; `parent-branch` is **not** present) — the source of the warning. Keys consumed elsewhere: `git.require_pr_to_base` + `git.base_branch` are read via `cfg.get("git", ...)` in **`mill-finalize/SKILL.md`** (lines 32-33 — `require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))` and `base_branch = cfg.get("git", {}).get("base_branch", "main")`, deciding PR-vs-direct and the PR `--base`); `mill-merge/SKILL.md` (steps ~30-31) only *documents* them in prose for its branch-protection fallback message. `git.parent-branch` is read by `git-pr/SKILL.md` (step ~88) from `.millhouse/config.yaml` (a file outside the `load_config` merge chain).
- **Brief writers** (call `_agent_dispatch.write_brief` / `_implementer_common.emit_prepare`):
  - `millpy-implement.py` (role `implement`) → orchestrated by **mill-go** ✓ commits briefs (SKILL lines 270, 343, 678).
  - `millpy-fix.py` (role `fix`) → **mill-go** ✓.
  - `millpy-review-code.py` → **mill-go** ✓ (line 343, 638).
  - `millpy-review-plan.py` → **mill-plan** ✓ (SKILL lines 166, 168, 190, 199).
  - `millpy-review-discussion.py` → **mill-start** ✗ **(the gap)**. mill-start's commits (Phase: Discussion File line ~120; step 4b; step 5 line ~183; Handoff line ~189; `--auto` halt-commits) stage `<discussion_path>`/`<reviews_dir>`/`<status_path>` but never `_mill/briefs/`.
  - `millpy-merge-in-subagent.py` (roles `merge/conflicts` line ~243, `merge/verify-fix` line ~324) → **mill-merge-in** ✗ **(the gap)**. The merge is finalized with `git -c core.editor=true merge --continue` (SKILL line ~48, conflict path only), which commits the index but not the untracked brief. The `merge/verify-fix` brief is written in step 4 (Verify), **after** `merge --continue`, and step 4 has no orchestrator-level commit (the verify-fix sub-agent commits only its own fixes, not `_mill/briefs/`). Therefore a single pre-`merge --continue` staging cannot capture both briefs, and clean merges (no conflicts) skip `merge --continue` entirely — hence the trailing guarded brief-commit step (see Scope).
- **`_agent_dispatch.write_brief`** (`_agent_dispatch.py` ~96) writes `briefs_dir/<role>-<sanitized_scope>-r<n>.md`; `mkdir(parents=True, exist_ok=True)`. **`_implementer_common.emit_prepare`** (~184) wraps it and emits the prepare JSON envelope. Response `.out.md` files are written by the mill-go SKILL (Agent-mode dispatch, step ~127) into the same `_mill/briefs/` dir, so a single `git add _mill/briefs/` covers brief + response.
- **mill-go's `millpy-implement.py` prepare stage already does git add/commit/push** (the "mill-go: start batch" commit, lines ~231-255), confirming CLIs performing git ops is established — but we are intentionally *not* adding brief commits there (orchestrator-layer decision above).
- **`.gitignore`** (root) ignores only `**/_mill/*.active`; `_mill/briefs/` is not ignored.
- **Hub `mill-config.yaml`** at repo root is a sparse overlay (omits many template keys, sets no `git` keys) — no change needed; the CLAUDE.md "template and hub must stay in sync" note refers to structural compatibility, not byte-equality (the two already differ).

## Constraints

- **ASCII-only stdout/stderr** in any Python output (Windows cp1252). Not directly relevant — no new prints — but keep test messages ASCII.
- **`${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths**; this task edits source files under `plugins/mill/` (templates, SKILLs, unit tests) — those are repo edits, run via the cache only when invoking, tested via `uv run --project plugins/mill`.
- **No CONSTRAINTS.md** at the hub root (none found).
- **Frontend/API separation** (CLAUDE.md review terminology): git-commit logic for briefs stays in the orchestrator SKILLs (frontend), not the dispatch CLIs (API).
- **Default no-op:** the template change must not alter behavior for any existing hub. Verify the three seeded defaults match current fallbacks.

## Testing

- **Gap A (config, unit-testable):** Add a test to `plugins/mill/unit_tests/test-config.py` modeled on `test_via_psmux_does_not_trigger_unknown_key_warning` (line ~1076): write a hub `mill-config.yaml` containing a `git:` block with `parent-branch`, `require_pr_to_base`, and `base_branch`, load config with stderr captured, and assert `"unknown key: git"` does **not** appear in stderr. Recommended companion negative test: a `git:` block with an unknown subkey (e.g. `git.bogus-key`) **does** still emit `unknown key: git.bogus-key`, proving the namespace is registered without disabling typo detection. The existing `_setup_plugin_template` fixture copies the real template, so these tests exercise the actual schema change. TDD candidate: write the no-warning test first (red against current template), then add the template block (green).
- **Gap B (orchestrator SKILL prose, not unit-testable):** mill-start and mill-merge-in changes are edits to SKILL.md instructions, with no Python code path to unit-test. Verify by inspection that each edited commit pathspec now includes `_mill/briefs/` and matches the existing mill-go/mill-plan pattern, and that skip/halt paths use the existence guard. No integration test is added (mill's integration tests invoke real git/claude and are heavyweight); the change is a one-line pathspec addition consistent with already-shipped, already-working steps in sibling skills.
- **Full suite:** run `plugins/mill/unit_tests/run-all.py` (via `uv run --project plugins/mill`) to confirm no regression in the config tests. Per-batch `verify:` commands must start with `PYTHONPATH= ` (Python project).

## Q&A log

- **Q:** Where should the brief + `.out` commit live? **A:** Follow the same setup as everything else committed in `_mill/` — i.e. fold `_mill/briefs/` into the orchestrators' existing `_mill/` commits (as mill-go/mill-plan already do), not a new per-CLI finalize commit. This also auto-scopes the fix to the orchestrators that miss it (mill-start, mill-merge-in).
- **Q:** How to register the `git` namespace so the validator stops warning? **A:** Populate a real `git:` block in the template (parent-branch, require_pr_to_base: false, base_branch: main) — registers the keys, self-documents, keeps typo detection.
- **Q:** Unify `git.parent-branch` and `git.base_branch`? **A:** No — they are NOT the same thing (parent = spawned-from branch; base = canonical PR target; they can legitimately differ). Register both as distinct keys.
- **Q:** mill-merge-in's conflict sub-agent also writes uncommitted briefs (outside the originally-reported CLI list) — include it? **A:** Yes — fix mill-merge-in too, for full consistency with "everything in `_mill/` gets committed." Mechanism: a dedicated trailing guarded brief-commit step after step 4 Verify (NOT staging before `merge --continue` — that cannot capture the `merge/verify-fix` brief written later in step 4, and misses clean merges with no conflicts).
- **Q:** Among the originally-listed CLIs (implement/review-{plan,code,discussion}/fix), which are actually broken? **A:** Only review-discussion (mill-start). mill-go already commits implement/review-code/fix briefs; mill-plan commits review-plan briefs. Scope is therefore smaller than the proposal implied.
