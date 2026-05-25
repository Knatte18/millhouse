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

- **Decision:** New `_plan_validate.py` check `verify-not-isolated`. **Source checked:** per-batch file frontmatter `verify:` only — the same field `_plan_dag.iter_batch_verifies` (`_plan_dag.py:318-319`) reads at runtime. Trigger: `verify` is a non-null, non-empty string AND `verify.strip().startswith("PYTHONPATH=") is False`. Error payload conforms to the existing 5-key envelope every other check uses: `{"check": "verify-not-isolated", "batch": "<batch_file_stem>", "card": None, "path": "<full verify string>", "message": "verify command missing PYTHONPATH= prefix"}`. `batch:` is the per-batch file's stem (matches `non-existent-path` and friends — see `_plan_validate.py:246-255`). `card:` is `None` because the verify field is per-batch, not per-card. `path:` carries the offending verify string so the mechanical-fix dispatcher can read and rewrite it.
- **Rationale:** The runtime-relevant source is per-batch frontmatter; checking only there is sufficient. The 5-key envelope is mandatory because `_plan_validate.run()` (`_plan_validate.py:855`) sorts errors via `(e["batch"] or "", e["card"] or 0, e["check"])` — any check that omits `card` would `KeyError` at sort time. Conforming also means the existing mill-plan mechanical-fix dispatcher needs no schema changes.
- **Rejected:** Also check the overview's `batches:` Batch Index mirror entries' `verify:` field and the overview's top-level `verify:` field. Neither is read at runtime (`iter_batch_verifies` resolves through the batch index to per-batch files; nothing reads the top-level or the mirror `verify:`). Drift in those fields has no runtime effect, so YAGNI.
- **Rejected:** A 3-key payload (`{check, batch, verify}`). Would `KeyError` at sort time in `_plan_validate.run()`; would also require touching the mill-plan dispatcher to handle the new shape.
- **Rejected:** Permitting alternative leading tokens (`env -i`, `unset PYTHONPATH &&`) — added complexity for no concrete benefit; the planner is generating these strings, we want one canonical shape.
- **Rejected:** Validator runs but only warns. Existing validator gates are hard fails per the SKILL.md fix table; no precedent for warnings, and a warning that doesn't block lets drift back in.

### mechanical-fix-row

- **Decision:** Add a new row to the mill-plan SKILL.md "Phase: Plan Review → Step 1.5 fix table":
  - `check`: `verify-not-isolated`
  - `mechanical fix`: "Prepend `PYTHONPATH= ` (literal — empty value, single space, then the existing command) to the `verify:` field in the per-batch file named by the error payload's `batch:` field (`_mill/plan/<batch>.md`). Read the offending command from the payload's `path:` field; replace the file's frontmatter `verify:` line with `verify: PYTHONPATH= <original>`."
- **Rationale:** Symmetric with how other mechanical-fix rows are described; identifies the file + the literal change. Only one file kind to edit (per-batch frontmatter) since that's the only source the validator checks.
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
- `plugins/mill/templates/plan-overview.md:33,48` — `verify: null` in the top frontmatter and `verify: <command or null>` in the Batch Index example. Change the Batch Index example to `verify: PYTHONPATH= <command> or null`. Top-level `verify:` stays `null`. **Note:** the validator does NOT check the overview's mirror `verify:` or top-level `verify:` — these are documentation-only fields the planner uses for human readers. Showing the prefixed form in the template is purely for example consistency.
- `plugins/mill/templates/plan-batch.md:25` — `verify: null` placeholder. This file's frontmatter `verify:` IS what the validator checks (and what `iter_batch_verifies` executes at runtime). Add a comment line above explaining the prefix requirement, since the planner reads template comments.

**Validator changes:**

- `plugins/mill/scripts/_plan_validate.py` — add `_check_verify_not_isolated(batch_files)` function alongside the existing `_check_*` functions (see `_check_non_existent_path` at line 246 for the canonical shape). Register the call via `errors.extend(_check_verify_not_isolated(batch_files))` inserted into `run()` (around `_plan_validate.py:842-853`), grouped with the other batch-scoped checks. For frontmatter extraction, use the in-module inline-YAML pattern already in `_plan_validate.py` — see `_check_depends_on_batch_mismatch` at lines 534-549: read text, find the fenced ` ```yaml ` block, `yaml.safe_load` the inner lines. The function then reads each batch's `verify:` field and emits the 5-key error dict per the validator-check-shape decision above when the field is a non-null, non-empty string that does not satisfy `verify.strip().startswith("PYTHONPATH=")`.
- `plugins/mill/unit_tests/test-plan-validate.py` — add unit tests: (a) per-batch frontmatter `verify:` without prefix → error fired with correct 5-key payload; (b) per-batch frontmatter `verify:` WITH prefix → no error; (c) per-batch frontmatter `verify: null` → no error; (d) per-batch frontmatter `verify:` with leading whitespace before `PYTHONPATH=` → no error (we trim first); (e) per-batch frontmatter `verify: PYTHONPATH=/some/path uv run ...` (non-empty value after `PYTHONPATH=`) → no error (we only require the prefix token, not a specific value). Use the existing fixture pattern in that test file for setting up batch files with frontmatter.

**Doc changes:**

- `plugins/mill/templates/mill-config.yaml` — comment-only addition near line 200 (existing verify block).
- `CLAUDE.md` (project root) — one paragraph under `## Script invocation`.

**Gotchas:**

- The validator runs in the cache via `${CLAUDE_PLUGIN_ROOT}/scripts/millpy-validate-plan.py` per the SKILL invocation pattern. Don't expect to test it interactively from this worktree alone — tests under `unit_tests/` import from worktree code with `uv run --project plugins/mill`, which is itself subject to the very PYTHONPATH bug this task fixes. Self-referential: the test for the verify-isolation validator must itself use the isolated verify form. Tests in `test-plan-validate.py` invoke pure-Python check functions in-process — no subprocess, no `verify:` execution — so they're unaffected by the leak. The verify-string-of-the-test-runner is what's affected, and the test-runner's verify string (any future plan covering this task) is the only one we're enforcing.
- `_plan_validate.py` already has a multi-row mechanical-fix table referenced by SKILL.md row-by-row. Use the same JSON envelope shape (`{"check": "...", "batch": "...", ...}`) so the existing fix-dispatcher in mill-plan picks it up without changes.
- The overview's top-level `verify:` and the overview's Batch Index `batches:` mirror entries' `verify:` are documentation-only fields — nothing reads them at runtime. `iter_batch_verifies` (`_plan_dag.py:285-322`) resolves through the batch-index DAG to per-batch files and reads each per-batch file's frontmatter `verify:`. The validator therefore only checks per-batch file frontmatter. Drift in the overview's mirrored or top-level `verify:` has no runtime effect.

## Testing

**TDD candidates (write tests first):**

- `_plan_validate._check_verify_not_isolated` — table-driven test in `test-plan-validate.py`. All cases vary the per-batch file's frontmatter `verify:` only (overview top-level and batch-index mirror `verify:` are not validated):
  - input: per-batch file `verify: null` → no errors.
  - input: per-batch file `verify: <unset / missing key>` → no errors.
  - input: per-batch file `verify: uv run ...` (no prefix) → one error with the 5-key envelope `{check: "verify-not-isolated", batch: <batch_file_stem>, card: None, path: "uv run ...", message: "verify command missing PYTHONPATH= prefix"}`.
  - input: two batches both unprefixed → two errors, one per batch, each with its own `batch:` stem.
  - input: per-batch file `verify: PYTHONPATH= uv run ...` → no errors.
  - input: leading whitespace before `PYTHONPATH=` (e.g. `  PYTHONPATH= uv run ...`) → no error (trim before checking).
  - input: `verify: PYTHONPATH=/some/path uv run ...` (non-empty value after the prefix) → no error (we only require the `PYTHONPATH=` token, not a specific reset value — the planner might intentionally set it).
  - integration via `_plan_validate.run()`: a batch file with unprefixed `verify:` produces an error that survives the final `errors.sort(key=lambda e: (e["batch"] or "", e["card"] or 0, e["check"]))` call (`_plan_validate.py:855`) without `KeyError`. Verifies the 5-key envelope is correctly populated.

**Coverage scenarios — full pass through the planning loop (out of scope for this task's automated tests, but must work end-to-end):**

- Fresh mill-plan run writes a verify with the prefix → validator passes on first try.
- Planner writes a verify without the prefix → validator fires → mechanical fix prepends `PYTHONPATH= ` → validator passes on second try.
- Two batch files both with unprefixed `verify:` in one plan → both fixed in one mechanical-fix pass → validator passes.

**Not tested in unit tests (but verified during integration):**

- The actual `subprocess.run` in `millpy-merge-in-subagent.py` with the isolated string. That code path is unchanged.
- The implementer/fixer Sonnet running the verify command. The brief tells the agent to run the literal string from frontmatter — if the string is correctly prefixed, the agent runs it correctly. No code change there to test.

## Q&A log

- **Q:** Doc-only, runtime, validator, or all three layers? **A:** Doc + validator. Belt + suspenders, no runtime magic.
- **Q:** Retroactive patch of `hanf/wiki-v3-adoption`'s `_mill/plan/*.md`? **A:** Out of scope. Parent is stale, waiting for `wiki-v3-batch3-finish` to produce a fresh smaller-batch plan off the corrected templates. Editing the parent from this child worktree violates worktree-isolation rules and would carry foreign plan files on this branch.
- **Q:** Should mill-config.yaml schema comment + CLAUDE.md note both be added? **A:** Yes. Same place future readers look when wondering why the prefix is required.
- **Q:** Exact validator-check trigger shape? **A:** Regex-free: trim leading whitespace, require `startswith("PYTHONPATH=")`. Anything else is rejected with mechanical fix = prepend `PYTHONPATH= `.
- **Q:** Error-payload schema? **A:** 5-key envelope matching every other check in `_plan_validate.py`: `{check, batch, card, path, message}`. A 3-key payload would `KeyError` at `_plan_validate.run()`'s sort step (line 855 sorts on `(batch, card, check)`).
- **Q:** Which `verify:` field does the validator inspect — overview top-level, overview Batch Index mirror entries, or per-batch file frontmatter? **A:** Per-batch file frontmatter only. That is the field `_plan_dag.iter_batch_verifies` reads (`_plan_dag.py:319`) and the only one executed at runtime. The other two are documentation-only and not validated.
- **Q:** Why reject `uv run --isolated`? **A:** That flag means "ignore project pyproject", which breaks `--project plugins/mill` resolution. Wrong semantic for this fix.
- **Q:** Do we touch the executed-string path (implementer brief, fixer brief, mill-merge-in subagent)? **A:** No. Single source of truth at authoring time (planner + validator). Runtime stays a verbatim string runner.
