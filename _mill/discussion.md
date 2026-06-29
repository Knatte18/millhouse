# Discussion: Fix stale checkpoint safety, Go binary ephemeral allowlist, and bare agent-tier name trap

```yaml
task: Fix stale checkpoint safety, Go binary ephemeral allowlist, and bare agent-tier name trap
slug: mill-scope-and-infra-gaps
status: discussing
parent: main
```

## Problem

Three independent mill infrastructure/safety bugs, each surfaced by `/mill-self-report --auto` from real runs on the `loomyard` repo. They share no code and can be implemented in parallel:

1. **#567 — stale checkpoint rollback target (safety).** `mill-merge-in` step 2 creates a rollback checkpoint with `git branch "$CHK"`. If a checkpoint branch from a prior run already exists, `git branch` fails (`fatal: a branch named '…' already exists`), the skill has no guard, and the run sails on. The rollback contract is `git reset --hard "$CHK"`, so `$CHK` now points at a *stale* pre-merge commit from an earlier run. A rollback during steps 3–5 would reset to the wrong commit — silent data loss / incorrect recovery. The bug is latent today (the failed merge happened to not need rollback) but it is a correctness landmine.

2. **#571 — Go build binary blocks the Handoff cleanliness gate.** During `/mill-go` on a Go project, building a `package main` (e.g. `tools/sandbox`) leaves an untracked `sandbox.exe` (~3.3 MB) at the repo root. `_cleanliness.clean_ephemeral_scope_violations` does not recognize Go build artifacts, so it returns `removed=[]`, `blocking=["sandbox.exe"]`. The mill-go Handoff "scope violations cleanup gate" then forces a halt for manual operator removal — breaking autonomous flow for what is a textbook ephemeral output, exactly like the coverage profiles the allowlist already auto-cleans.

3. **#565 — bare `sonnet`/`opus` tier-name trap (ergonomics → hard failure).** The agent registry (`mill-agents.yaml`) defines bare `haiku` but only effort-suffixed `sonnethigh/medium/max` and `opushigh/medium/max` — there is **no bare `sonnet` or `opus`**. A user who writes `model: sonnet` (mirroring the working `model: haiku`) gets `Unknown reviewer: 'sonnet'` raised deep in the pipeline at the prepare/dispatch stage, which blocks *every* agent dispatch until corrected. The inconsistency is the trap: bare haiku works, so bare sonnet/opus look like they should too.

**Why now:** all three were filed against live autonomous runs; #567 is a silent-corruption risk and #571/#565 break autonomous flow with hard halts.

## Scope

**In:**

- `plugins/mill/templates/mill-agents.yaml` — add bare `sonnet`, `sonnet_bulk`, `opus`, `opus_bulk` convenience aliases (#565).
- `plugins/mill/scripts/_reviewers.py` — improve the `resolve()` "Unknown reviewer" error message to list valid registry names (#565).
- `plugins/mill/skills/mill-merge-in/SKILL.md` — make checkpoint creation idempotent and always-correct (#567).
- `plugins/mill/scripts/_cleanliness.py` — extend the ephemeral allowlist in `clean_ephemeral_scope_violations` for Go build artifacts (#571).
- Unit tests in `plugins/mill/unit_tests/` for each code change (`test-reviewers.py`, `test-cleanliness.py`; registry shape covered by `test-agents-defs.py` / `test-reviewers.py` load path).

**Out:**

- No change to `validate_role_refs` *logic* (#565) — once the registry has bare `sonnet`/`opus`, the existing walk resolves them; we do not move validation to config-load time (it already runs at prepare and that timing is acceptable once the names resolve).
- No change to `mill-merge` step 274's rollback reference (#567) — it consumes the checkpoint; making the checkpoint correct is sufficient.
- No magic-byte / executable-bit sniffing for binaries (#571) — see Decisions.
- No new `hai) bulk` effort tiers and no removal of bare `haiku` — we add parity, we don't restrict.
- `.millhouse/agents.local.yaml` is not touched (no local overlay exists in this hub; the template is the only registry source).
- No changes to non-millhouse repos; `mill-agents.yaml` exists only inside the plugin tree.

## Decisions

### bare-tier-aliases (#565)

- **Decision:** Add four convenience entries to `mill-agents.yaml`: `sonnet`, `sonnet_bulk`, `opus`, `opus_bulk`, each `provider: claude`, `type: single`, `effort: medium`, with `tooluse: true` for the bare name and `tooluse: false` for the `_bulk` variant — mirroring the existing `haiku`/`haiku_bulk` shape. Model ids match the family (`claude-sonnet-4-6`, `claude-opus-4-7`). Add a short comment documenting that the bare name resolves to the **medium** effort tier and that explicit `…high`/`…max` remain available.
- **Rationale:** Removes the trap by *consistency-via-addition*: every model family now has a bare name that works, matching the `haiku` precedent the user reasonably generalized from. `medium` is the neutral default effort; users wanting more pick `sonnethigh`/`opusmax` explicitly. This is the minimal, regular extension of the existing naming scheme.
- **Rejected:** (a) Up-front config-load rejection with a "valid tiers" message (issue option b) — does not let the intuitive `model: sonnet` work; it only relocates the failure earlier. We instead make the intuitive name valid. (b) Removing bare `haiku` to force full symmetry — gratuitously breaks working configs. (c) Resolving bare to `high` — `high` is not the neutral default and would surprise; `medium` is the principled middle.

### unknown-reviewer-error-message (#565)

- **Decision:** In `_reviewers.resolve()`, when a name is not in the registry, raise `ReviewerError(f"Unknown reviewer: {name!r}. Available: {sorted_names}")` listing the sorted registry keys (and noting `test_stub` is a synthetic special case only if cheap). This helps genuine typos even after the bare aliases land.
- **Rationale:** Cheap, strictly additive robustness; turns a dead-end error into an actionable one. The existing call sites (`validate_role_refs`, `resolve_role`, cluster flattening) all propagate the richer message unchanged.
- **Rejected:** Leaving the bare `Unknown reviewer: 'x'` message — provides no guidance toward valid names.

### idempotent-checkpoint (#567)

- **Decision:** Replace `git branch "$CHK"` in `mill-merge-in` step 2 with a detect-then-force sequence: capture the existing checkpoint sha if the branch exists (`git rev-parse --verify --quiet "$CHK"`), then `git branch -f "$CHK"` so the checkpoint **always** points at the current (true pre-merge) HEAD. If the branch pre-existed, emit an informational, non-blocking note recording `old-sha -> new-sha` so the move is auditable. Update the surrounding prose (step 2 + Rollback section) to state the checkpoint is force-refreshed each run.
- **Rationale:** The checkpoint is *deliberately left in place on success* (step 6: "delete manually once confident"), so encountering an existing checkpoint on any re-run is the **normal** state, not an exceptional one. At step 2 we are at the true pre-merge HEAD (step 1's no-op check has already confirmed there is something to merge and we have not merged yet), so force-moving the checkpoint to current HEAD is exactly the correct rollback target. The audit note preserves the prior sha for investigation without blocking.
- **Rejected:** (a) Refuse / halt on existing checkpoint (issue option a/c) — would make *every* second run fail, since the prior run intentionally left its checkpoint behind. (b) Plain `git branch -f` with no note — correct rollback target but loses the auditable trail of what the prior checkpoint pointed at. (c) Delete-then-create — same result as force-move but with a transient window where no checkpoint exists; force-move is atomic from the rollback contract's view.

### go-artifact-allowlist (#571)

- **Decision:** Extend `clean_ephemeral_scope_violations`'s allowlist:
  - Add suffix **`.exe`** to the existing suffix set (`.test`, `.test.exe`, `.prof`, `.cover` + basename `coverage.out`). This auto-cleans `sandbox.exe` — the reported case and the Windows-primary platform mill runs on. **`.exe` is a blanket rule, NOT gated by the `package main` heuristic** — this is the intended, explicit choice (do not silently narrow it). Rationale for the asymmetry vs. the rejected magic-byte option: an extension-bearing `.exe` is itself an unambiguous "compiled artifact" signal in a source repo, so suffix-matching alone is a strong-enough basis to auto-clean; the magic-byte/`X_OK` option was rejected specifically for the **extensionless** case, where there is no extension signal and a precise corroborating heuristic is required. Accepted residual risk: a deliberately-placed/downloaded untracked, non-gitignored, out-of-scope `.exe` would be auto-removed — judged acceptable because (a) the gate fires only on untracked+out-of-scope files at batch/Handoff end, (b) the user can `.gitignore` or commit any intentional binary, and (c) gating `.exe` behind the dir-name heuristic would fail to clean legitimate `go build -o foo.exe` output whose name does not match a package dir.
  - Add a precise **bare-name Go-binary** heuristic: an untracked out-of-scope file whose basename contains **no `.`** is allowlisted **iff** the repo has a tracked `*.go` file (a) located in a directory whose basename equals the binary's basename and (b) declaring `package main`. Discover candidate sources via `git ls-files "*.go"` (only tracked source counts), and run the scan **only when** at least one extensionless violation exists, so the common case pays nothing. This mirrors `go build`'s default output naming (`go build ./tools/sandbox` → `sandbox`).
  - Update the docstring to describe the Go artifact coverage.
- **Rationale:** `.exe` is unambiguous in a code repo and covers the actual bug. The bare-name heuristic is intention-revealing (matches the issue author's own suggested fix: "bare-name executables that match a `package main` dir name"), platform-independent for Linux/macOS Go users, and conservative enough to never delete an unrelated stray file (it requires both no-extension *and* a matching `package main` source dir).
- **Rejected:** (a) Blanket-allowlist all extensionless untracked files — would auto-delete arbitrary stray files (a `notes` scratch file, etc.). (b) Magic-byte / `os.access(X_OK)` sniffing — too clever, could delete a deliberately-downloaded binary, and platform-fragile. (c) `.exe`-only (skip bare-name) — leaves Linux/macOS Go runs still blocked; the issue explicitly lists bare-name binaries as in-scope.

## Technical context

- **`_reviewers.py`** — `resolve(registry, name)` (line ~360) is the single chokepoint; `validate_role_refs` (line ~424) and `resolve_role` (line ~400) both call it, so improving its error message and having the registry carry bare names fixes #565 end-to-end with no call-site changes. `load()` merges plugin template + optional `.millhouse/agents.local.yaml`; here only the template exists. `_NAME_REGEX = ^[a-z0-9_-]+$` already permits `sonnet`/`opus`/`sonnet_bulk`.
- **`mill-agents.yaml`** — flat `name: {type, provider, model, effort?, tooluse, timeout?}` mapping. Existing tier entries (lines 70–152) are the exact shape to copy. Keep entries alphabetically grouped as the file already is (insert `opus`/`opus_bulk` near the `opus*` block, `sonnet`/`sonnet_bulk` near the `sonnet*` block).
- **`mill-merge-in/SKILL.md`** — step 2 is lines 27–33; Rollback section lines 99–107. `$CHK` is `mill-checkpoint-<branch-with-slashes-as-dashes>`. The checkpoint branch name is never the current branch, so `git branch -f` is always legal. `mill-merge/SKILL.md:274` resets to the same checkpoint name on its own rollback path — it benefits from the corrected target with no edit.
- **`_cleanliness.py`** — `clean_ephemeral_scope_violations` (lines 156–207) calls `compute_scope_violations` (lines 59–77), which returns sorted bare paths of untracked, non-gitignored, out-of-`_mill/`, non-junction files. The allowlist partition loop (lines 181–205) is where the suffix/basename checks live and where the new Go logic slots in. A new small helper (e.g. `_is_go_main_artifact(worktree, path)`) keeps the loop readable; it should use `_subprocess_util.run(["git", "ls-files", "*.go"], cwd=worktree)` and read each candidate's leading lines for `package main`. Removal already swallows `FileNotFoundError` and reports `OSError` as blocking — preserve that for the new paths too.
- **Tests** — `test-cleanliness.py` has CESV-1..5 covering coverage.out / `.test.exe` / non-allowlisted / in-scope `_mill/` / already-gone, using real `git init` tmp fixtures (see lines 538–669) — extend with `.exe`, bare-name-with-matching-main-pkg (allowlisted), and bare-name-without-matching-pkg (blocking). `test-reviewers.py` covers load/resolve/validate; add cases that bare `sonnet`/`opus` resolve and that `resolve` on a true unknown name yields the new richer message. `test-agents-defs.py` validates agent `.md` frontmatter, not the registry size, so new entries don't perturb it.

## Constraints

- No `CONSTRAINTS.md` at the hub root (none found during exploration).
- **ASCII-only stdout** (`print`/`_log`): the audit note for #567 and any new messages must use ` -- ` / ` -> ` not Unicode dashes/arrows (Windows cp1252).
- **Verify command shape:** this is a Python project, so plan `verify:` commands must start with `PYTHONPATH=` (literal empty value + single space) per CLAUDE.md; unit tests run via `uv run --project plugins/mill`.
- **Windows-primary:** `.exe` is the dominant Go-binary form here; the bare-name heuristic is for cross-platform completeness, not the primary path.
- **Idempotency (#567):** the new step 2 must be safe to run repeatedly — force-move, never fail-on-exists.

## Testing

- **#565 (`test-reviewers.py`, unit):**
  - `resolve(registry, "sonnet")` and `resolve(registry, "opus")` return specs with `effort == "medium"`, `provider == "claude"`, correct model ids, `tooluse is True`; `sonnet_bulk`/`opus_bulk` resolve with `tooluse is False`. (Load the real template via `load()` or a fixture mirroring it.)
  - `validate_role_refs` passes with `roles.implementer.model: sonnet` / `roles.fixer.model: opus` (the exact #565 repro config) — no raise.
  - `resolve(registry, "definitely-not-a-name")` raises `ReviewerError` whose message contains "Available:" and at least one real registry name.
- **#571 (`test-cleanliness.py`, unit, real-git tmp fixtures):**
  - `.exe` artifact at repo root → removed, not blocking.
  - Extensionless binary `sandbox` at repo root + tracked `tools/sandbox/main.go` containing `package main` → removed (bare-name heuristic hit).
  - Extensionless file `notes` with **no** matching `package main` dir → blocking (heuristic must not over-match).
  - Regression: existing CESV-1..5 still pass; in-scope `_mill/` and gitignored files remain untouched.
- **#567 — VERIFICATION IS PROSE-ONLY (committed decision, not "decide later").** No Python module owns `mill-merge-in` step 2; it is a SKILL.md behavioral change, and the existing `integration_tests/` harness does not cleanly drive skill-prose execution. The plan therefore must NOT spend a batch building a bespoke automated repro for it. Verification = (a) inspection of the edited step 2 + Rollback prose confirming `git branch -f` is used and the audit note is emitted, and (b) the manual repro recorded verbatim in the plan from issue #567 (create checkpoint, re-run, confirm `$CHK` points at the current pre-merge HEAD and the run does not error). Plan writers: set this batch's `verify:` to `null`. TDD candidate: only #565 and #571 are pure-code; #567 is doc/behavioral and prose-verified only.
- **Full suite:** `uv run --project plugins/mill plugins/mill/unit_tests/run-all.py` must stay green.

## Q&A log

- **Q:** #565 — make bare `sonnet`/`opus` work (parity with `haiku`), or reject them up front with a "valid tiers" message? **A:** [auto-pick] Add bare `sonnet`/`sonnet_bulk`/`opus`/`opus_bulk` aliases at `effort: medium` (parity-via-addition). **Why:** removes the trap by making the intuitive name valid, matching the `haiku` precedent the user generalized from; rejection only relocates the error without letting `model: sonnet` work.
- **Q:** #565 — what effort tier should the bare alias resolve to? **A:** [auto-pick] `medium`. **Why:** neutral default; `high`/`max` would surprise and remain explicitly available as `…high`/`…max`.
- **Q:** #565 — also improve the "Unknown reviewer" error to list valid names? **A:** [auto-pick] Yes, append `Available: <sorted names>` in `resolve()`. **Why:** cheap, strictly additive, helps genuine typos even after aliases land.
- **Q:** #567 — refuse on existing checkpoint, force-move it to current HEAD, or halt? **A:** [auto-pick] Force-move (`git branch -f`) with an informational `old -> new` sha note. **Why:** the checkpoint is intentionally left on success, so a pre-existing checkpoint is the normal re-run state; at step 2 HEAD is the true pre-merge commit, so force-moving yields the correct rollback target; halting would break every second run.
- **Q:** #571 — how broadly to allowlist Go artifacts? **A:** [auto-pick] Add `.exe` suffix + a precise bare-name heuristic (extensionless file whose basename matches a tracked `package main` dir). **Why:** `.exe` covers the reported Windows case unambiguously; the bare-name heuristic mirrors the issue's own suggestion and stays conservative (requires a matching main-package source dir), avoiding deletion of unrelated stray files.
- **Q:** #571 — use magic-byte/executable-bit detection instead of the dir-name heuristic? **A:** [auto-pick] No. **Why:** too clever and platform-fragile; could delete a deliberately-downloaded binary. The `package main` dir match is intention-revealing and safe.
- **Q:** Implement all three in one task/branch? **A:** [auto-pick] Yes, parallel batches. **Why:** they share no code (registry YAML, one skill doc, two unrelated scripts); a batch-per-issue DAG lets mill-go parallelize cleanly.
