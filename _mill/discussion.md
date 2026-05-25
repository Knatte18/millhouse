# Discussion: Isolate verify PYTHONPATH so tests validate worktree code

```yaml
task: Isolate verify PYTHONPATH so tests validate worktree code
slug: wiki-v3-verify-isolation
status: discussing
parent: hanf/wiki-v3-adoption
```

## Problem

Every mill skill invokes Python with `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` so that orchestration code runs from the stable plugin cache, not from whatever happens to be in the current worktree. That's correct for live mill operations. But the same `PYTHONPATH` value is inherited by every subprocess that mill spawns — including the `verify:` commands the implementer/fixer and `mill-merge-in` run during a batch.

When `verify:` reads `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`, the test subprocess inherits the parent shell's `PYTHONPATH`. Python's import machinery resolves entries on `PYTHONPATH` before `--project`-resolved site-packages, so any module whose name exists in **both** the cache and the worktree (`_config`, `_paths`, `_review_common`) loads from the **cache** — not from the worktree code under test. Modules deleted in the worktree but still present in the cache (`_tasks_md`, `_wiki`, `_sidebar` after `wiki-v3-adoption` batch 3 card 30) load the stale V2 cache copy.

Result: tests run against a Frankenstein of V2 cache + V3 worktree. They fail in confusing ways unrelated to whatever verify is gating on. In `hanf/wiki-v3-adoption` this manifests as ~15 of 77 unit tests failing — most prominently `test-millpy-claim.py` with all 11 tests reporting "daemon did not start within timeout" because V2-cache `_paths`/`_config` and V3-worktree `wiki/_daemon` disagree about file layout.

**Why now:** the diagnosis lives in `_mill/handoff.md` on the `hanf/wiki-v3-adoption` branch (insight #2). The sibling task `wiki-v3-batch3-finish` is blocked on this fix — without verify isolation, its test-sweep cards keep tripping over cache leakage and the implementer can't tell real failures from environmental ones.

## Scope

**In:**

- Update `plugins/mill/skills/mill-plan/SKILL.md` so the planner writes every non-null `verify:` command with a `PYTHONPATH=` prefix that resets the env var for that one command.
- Update `plugins/mill/templates/plan-overview.md` and `plugins/mill/templates/plan-batch.md` so their `verify:` placeholders / examples show the prefixed form.
- Add a `_plan_validate.py` check (`verify-not-isolated`) that rejects any non-null `verify:` command that does not start with `PYTHONPATH=`. Wire the mechanical-fix row into the mill-plan SKILL fix table: prepend `PYTHONPATH= ` to the command.
- Add unit-test coverage for the new validator check in `plugins/mill/unit_tests/test-plan-validate.py`.
- Add a comment in `plugins/mill/templates/mill-config.yaml` that documents the canonical isolated-verify form (no schema change — comment only).
- Add a one-paragraph note in `CLAUDE.md` (project-root) under "Script invocation" explaining why verify commands must reset `PYTHONPATH`. Cross-reference the mill-plan validator check.

**Out:**

- Editing existing plan files on the `hanf/wiki-v3-adoption` branch. Parent is stale and waiting for `wiki-v3-batch3-finish`, which will write a fresh plan off the corrected templates. No retroactive patching from this branch.
- Runtime injection of `PYTHONPATH=` in implementer briefs, fixer briefs, `mill-merge-in` subagent, or `millpy-merge-in-subagent.py`. Doc + validator is the single source of truth; the executed string is exactly what the plan says, no silent magic.
- Cleanup of the worktree's `__pycache__/` directories or the plugin cache itself. The cache is the correct runtime for mill skills; the fix is in the verify command, not in cache layout.
- Root-causing the residual `test-millpy-claim.py` "daemon did not start within timeout" failures if they survive after isolation lands. That investigation belongs to `wiki-v3-batch3-finish` (per the proposal's "if it persists, root-cause it in this task" note — "this task" there meant the larger batch3 task, not verify-isolation).
- Any change to the implementer-brief / fixer-batch-brief / merge-in-verify-brief templates. They pass `verify:` through verbatim; nothing about the brief needs to change.

## Decisions

### verify-isolation-mechanism

- **Decision:** `PYTHONPATH=` prefix on the same line as the verify command, written into the plan file by the planner. Example: `verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`. Empty value on the same line scopes the env-var reset to that one command only.
- **Rationale:** The verify string is the single source of truth read by every consumer (`mill-merge-in` via `iter_batch_verifies`, the implementer/fixer Sonnet agents reading batch frontmatter). One change at the authoring layer fixes every downstream consumer with no special-casing.
- **Rejected:** `uv run --isolated` — that flag means "ignore project pyproject", which breaks `--project plugins/mill` resolution. Wrong semantic.
- **Rejected:** `env -i ...` — strips everything, including `PATH` / `HOME`. Overkill and surface for subtle breakage on Windows.
- **Rejected:** Runtime injection in `millpy-merge-in-subagent.py` and per-brief. Two execution paths to keep in sync, plus the implementer brief instructs an LLM agent to "run the verify command from the batch frontmatter" — modifying that to "prepend `PYTHONPATH= ` first" hides the actual executed string from the user reading the plan.

### enforcement-layer

- **Decision:** Doc + validator. mill-plan SKILL.md gets a paragraph requiring the prefix; templates show the prefix in placeholders; `_plan_validate.py` rejects any plan whose non-null `verify:` lacks `PYTHONPATH=` at the start (after trimming whitespace).
- **Rationale:** Doc alone lets the planner LLM drift. A validator check costs nothing to implement and gives a hard guarantee that ships in every future plan. Mechanical-fix path is trivial (prepend the prefix).
- **Rejected:** Doc-only. Drift risk over the long run; LLM planners forget non-obvious rules.
- **Rejected:** Runtime-only. Hides the executed string from the plan reviewer; two-path maintenance burden.
- **Rejected:** All three layers (doc + validator + runtime guard). Runtime guard is redundant once the validator gates every plan.

### validator-check-shape

- **Decision:** New `_plan_validate.py` check `verify-not-isolated`. Fires per batch entry in the overview's Batch Index DAG (the `verify:` field per `_plan_dag.iter_batch_verifies` shape). Trigger: `verify` is a non-null, non-empty string AND `verify.strip().startswith("PYTHONPATH=") is False`. Error payload: `{"check": "verify-not-isolated", "batch": "<batch_name>", "verify": "<full string>"}`. Also checked at the plan-overview top-level `verify:` field (same trigger logic).
- **Rationale:** Simple to implement; mirrors the proposal's "one-line fix"; covers both the per-batch `verify:` and the top-level overview `verify:` (which exists in the template but isn't routinely populated — guard it anyway so adoption of that field doesn't reintroduce the leak).
- **Rejected:** Permitting alternative leading tokens (`env -i`, `unset PYTHONPATH &&`) — added complexity for no concrete benefit; the planner is generating these strings, we want one canonical shape.
- **Rejected:** Validator runs but only warns. Existing validator gates are hard fails per the SKILL.md fix table; no precedent for warnings, and a warning that doesn't block lets drift back in.

### mechanical-fix-row

- **Decision:** Add a new row to the mill-plan SKILL.md "Phase: Plan Review → Step 1.5 fix table":
  - `check`: `verify-not-isolated`
  - `mechanical fix`: "Prepend `PYTHONPATH= ` (literal — empty value, single space, then the existing command) to the offending `verify:` field in the overview's Batch Index entry and/or the per-batch file's frontmatter. The error payload's `batch:` field names which file to edit; the top-level overview `verify:` is identified by `batch: <overview>` (sentinel)."
- **Rationale:** Symmetric with how other mechanical-fix rows are described; identifies the file + the literal change. The `<overview>` sentinel for the top-level field is a small new convention but the fix table already uses one-off sentinels in similar rows.
- **Rejected:** Halt instead of mechanical-fix. Halting on a one-character fix wastes a planning round when the planner can be told to prepend.

### docs-touchpoints

- **Decision:** Comment in `plugins/mill/templates/mill-config.yaml` near the existing `verify:` allowlist block (around line 200) showing the canonical isolated-verify shape. One-paragraph addition to `CLAUDE.md`'s `## Script invocation` section: "Verify commands MUST start with `PYTHONPATH=` to reset the inherited cache path — see mill-plan validator check `verify-not-isolated`." Both are doc-only; no schema change.
- **Rationale:** Future readers wonder why the prefix is there. Documenting in the two places people read (mill-config schema and CLAUDE.md root) is cheap and pre-empts the question.
- **Rejected:** Skip docs, rely on validator alone. The validator message tells you *what* to do but not *why*; the next maintainer wonders if they can simplify it away.

## Technical context

**Verify-string execution sites (read-only — none of these change):**

- `plugins/mill/templates/implementer-brief.md:53-60` — Sonnet implementer reads `verify:` from batch frontmatter and runs it.
- `plugins/mill/templates/fixer-batch-brief.md:52-57` — same shape, for the fixer after a code-review request-changes.
- `plugins/mill/scripts/millpy-merge-in-subagent.py:213` — `subprocess.run(args.cmd, shell=True, ...)` runs the verify command in verify-fix mode.
- `plugins/mill/skills/mill-merge-in/SKILL.md:55-65` — calls `_plan_dag.iter_batch_verifies(plan_dir)`, executes each verify command from the worktree root, dispatches to the subagent above on failure.
- `plugins/mill/scripts/_plan_dag.py:286-291` — `iter_batch_verifies` returns `(batch_name, verify_cmd)` tuples in DAG order. Strings, no transformation.

**Verify-string authoring sites (these change):**

- `plugins/mill/skills/mill-plan/SKILL.md` — the planner LLM is guided here. Add a "verify command shape" paragraph in Phase: Plan that mandates the `PYTHONPATH=` prefix; add the `verify-not-isolated` row to the Step 1.5 fix table.
- `plugins/mill/templates/plan-overview.md:33,48` — `verify: null` in the top frontmatter and `verify: <command or null>` in the Batch Index example. Change the Batch Index example to `verify: PYTHONPATH= <command> or null` (top-level stays `null` since the proposal-driven plans rarely set it).
- `plugins/mill/templates/plan-batch.md:25` — `verify: null` placeholder. Add a comment line above explaining the prefix requirement, since the planner reads template comments.

**Validator changes:**

- `plugins/mill/scripts/_plan_validate.py` — add `verify-not-isolated` check function. Look at the existing check functions in that file for the registration shape (likely a list of check functions or a check-dispatcher).
- `plugins/mill/unit_tests/test-plan-validate.py` — add unit tests: (a) non-null verify without prefix → error fired with correct payload; (b) non-null verify WITH prefix → no error; (c) `verify: null` → no error; (d) overview-level verify field and batch-level verify field both checked.

**Doc changes:**

- `plugins/mill/templates/mill-config.yaml` — comment-only addition near line 200 (existing verify block).
- `CLAUDE.md` (project root) — one paragraph under `## Script invocation`.

**Gotchas:**

- The validator runs in the cache via `${CLAUDE_PLUGIN_ROOT}/scripts/millpy-validate-plan.py` per the SKILL invocation pattern. Don't expect to test it interactively from this worktree alone — tests under `unit_tests/` import from worktree code with `uv run --project plugins/mill`, which is itself subject to the very PYTHONPATH bug this task fixes. Self-referential: the test for the verify-isolation validator must itself use the isolated verify form. Tests in `test-plan-validate.py` invoke pure-Python check functions in-process — no subprocess, no `verify:` execution — so they're unaffected by the leak. The verify-string-of-the-test-runner is what's affected, and the test-runner's verify string (any future plan covering this task) is the only one we're enforcing.
- `_plan_validate.py` already has a multi-row mechanical-fix table referenced by SKILL.md row-by-row. Use the same JSON envelope shape (`{"check": "...", "batch": "...", ...}`) so the existing fix-dispatcher in mill-plan picks it up without changes.
- The overview `verify:` top-level field (vs. batch-level) — the existing plan written for `hanf/wiki-v3-adoption` populates the top-level too (line 10: `verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`). The validator must check both: top-level `verify:` from the overview YAML block, AND per-batch `verify:` from the Batch Index DAG. Use `batch: <overview>` sentinel in the error payload to disambiguate.

## Testing

**TDD candidates (write tests first):**

- `_plan_validate.py::check_verify_isolated` — table-driven test in `test-plan-validate.py`:
  - input: overview YAML with `verify: null` + batch entries with `verify: null` → no errors.
  - input: overview YAML with `verify: uv run ...` (no prefix) → one error, `batch: "<overview>"`.
  - input: overview YAML `verify: null` + batch with `verify: uv run ...` → one error, `batch: <batch_name>`.
  - input: overview + batch BOTH unprefixed → two errors.
  - input: overview + batch BOTH `verify: PYTHONPATH= uv run ...` → no errors.
  - input: leading whitespace before `PYTHONPATH=` (e.g. `  PYTHONPATH= uv run ...`) → no error (trim before checking).
  - input: `verify: PYTHONPATH=/some/path uv run ...` (non-empty value) → no error (we only require the prefix, not a specific reset value — the planner might intentionally set it).

**Coverage scenarios — full pass through the planning loop (out of scope for this task's automated tests, but must work end-to-end):**

- Fresh mill-plan run writes a verify with the prefix → validator passes on first try.
- Planner writes a verify without the prefix → validator fires → mechanical fix prepends `PYTHONPATH= ` → validator passes on second try.
- Two unprefixed verify strings (top-level + batch) in one plan → both fixed in one mechanical-fix pass → validator passes.

**Not tested in unit tests (but verified during integration):**

- The actual `subprocess.run` in `millpy-merge-in-subagent.py` with the isolated string. That code path is unchanged.
- The implementer/fixer Sonnet running the verify command. The brief tells the agent to run the literal string from frontmatter — if the string is correctly prefixed, the agent runs it correctly. No code change there to test.

## Q&A log

- **Q:** Doc-only, runtime, validator, or all three layers? **A:** Doc + validator. Belt + suspenders, no runtime magic.
- **Q:** Retroactive patch of `hanf/wiki-v3-adoption`'s `_mill/plan/*.md`? **A:** Out of scope. Parent is stale, waiting for `wiki-v3-batch3-finish` to produce a fresh smaller-batch plan off the corrected templates. Editing the parent from this child worktree violates worktree-isolation rules and would carry foreign plan files on this branch.
- **Q:** Should mill-config.yaml schema comment + CLAUDE.md note both be added? **A:** Yes. Same place future readers look when wondering why the prefix is required.
- **Q:** Exact validator-check trigger shape? **A:** Regex-free: trim leading whitespace, require `startswith("PYTHONPATH=")`. Anything else is rejected with mechanical fix = prepend `PYTHONPATH= `.
- **Q:** Why reject `uv run --isolated`? **A:** That flag means "ignore project pyproject", which breaks `--project plugins/mill` resolution. Wrong semantic for this fix.
- **Q:** Do we touch the executed-string path (implementer brief, fixer brief, mill-merge-in subagent)? **A:** No. Single source of truth at authoring time (planner + validator). Runtime stays a verbatim string runner.
