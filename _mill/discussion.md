# Discussion: Validate/verify diagnostics gaps

```yaml
task: Validate/verify diagnostics gaps
slug: mill-validate-verify-diagnostics-gaps
status: discussing
parent: main
```

## Problem

Two unrelated diagnosability gaps surfaced during real mill runs, filed as GitHub issues #772 and #770, both closed and folded into this task.

**Gap 1 (#772):** `_plan_validate.py`'s `_check_context_completeness` flags a card's `Requirements:` prose when it backtick-references a file absent from that card's own `Context:`/`Edits:`/`Creates:`/`Deletes:`/`Moves:`. The scan works per-line via `backtick_re.findall(line)`. When a backtick-wrapped phrase is split across two lines (or an adjacent line has an odd backtick count), the per-line regex mis-pairs backticks and can synthesize a bogus token — observed producing a bare `/` flagged as an unresolved reference. The emitted error dict (`{check, batch, card, path, message}`) names the batch and card but not the source line, so tracing a false positive back to the actual malformed line required an ad-hoc one-off script re-running the same regex.

**Gap 2 (#770):** `millpy-implement.py --stage finalize`'s verify-replay runs a batch's own `verify:` command and unconditionally classifies ANY non-zero exit as the batch's own regression (`stuck_type: verify`, then `logic` on retry). Observed case: a batch's two cards were both implemented and committed correctly, but its `verify:` command's test file had 5 pre-existing, unrelated failures (confirmed against a clean `main` checkout) — a sloppy-fixture bug unrelated to the batch's diff. mill-go's one-shot self-resolve-then-block path blocked a fully-correct batch, requiring an out-of-band operator override. The existing `module_verify_baseline` mechanism already solves exactly this class of problem for the overview's single, task-wide module-wide verify command; it has no equivalent for each batch's own (per-batch, differently-scoped) `verify:` command.

Both are diagnosability/false-positive-avoidance fixes to mill's own validation/execution tooling, not user-facing product changes.

## Scope

**In:**
- Add a `line` field (the offending raw `Requirements:` line, `.strip()`ped, verbatim) to every error dict `_check_context_completeness` emits.
- Update `mill-plan/SKILL.md`'s context-completeness fixer-remedy table row to mention the new `line` field.
- Extend the existing baseline mechanism (`_verify_baseline.py`, `_status.py`'s `module_verify_baseline` machinery, `millpy-implement.py --stage baseline`) so that, before batch 1 starts, each batch's own `verify:` command is also snapshotted against the parent branch — not just the overview's module-wide command.
- Store each batch's baseline failure-signature set on its `## Batches` entry in `status.md`.
- At `--stage finalize`, when a batch's `verify:` command fails, diff its failure signatures against that batch's stored baseline; only signatures NOT present in the baseline count toward `stuck_type: verify`/`logic`. A failure set that's a subset of baseline is treated as passing (module-wide gate semantics are unchanged).
- Extract the existing FAIL-marker-prefix line scan (`"--- FAIL:", "FAIL\t", "FAILED ", "--- FAIL ", "FAIL -- "`, currently inline in `_implementer_common.py`'s truncation path) into a shared helper reused by both the truncation logic and the new baseline-diff logic.

**Out:**
- No change to the overview's `module_wide_verify_cmd` baseline semantics or its `"clean"`/`"pre-existing-failures"` binary contract — that mechanism is reused/extended, not replaced.
- No absolute file-line-number computation for gap 1 (raw line text only — see Decisions).
- No changes to `_check_ref_not_backtick_path` or `_check_requirements_quote_indent_drift` — neither scans free-text `Requirements:` prose per-line the way `_check_context_completeness` does, so neither is vulnerable to the split-backtick false-positive class this task fixes.
- No new parsing of language-specific test-runner output formats beyond the existing fixed marker-prefix list (no pytest/go-test/dotnet-specific structured parsers).
- No change to the flakiness-guard retry/corroboration behavior of the module-wide baseline path in `_verify_baseline.compute_baseline` (unchanged for `module_wide_verify_cmd`); the new per-batch baseline computation gets its own, simpler corroboration (see Decisions).

## Decisions

### gap1-line-field-not-line-number

- Decision: Add a `line` field carrying the raw offending `Requirements:` line (stripped of leading/trailing whitespace, otherwise verbatim, no length cap) to `_check_context_completeness`'s error dicts. Do not compute an absolute file line number.
- Rationale: The issue explicitly accepts "a line number OR the offending raw line text." The raw line is available for free inside the existing `for line in requirements_lines:` loop (`_plan_validate.py:1536`). Computing an absolute file line number would require `_parse_cards` (`_plan_validate.py:129`) to also track each card's starting line offset — that function's return shape (`list[tuple[int, list[str]]]`) is consumed by 5 other call sites (`_plan_validate.py:758, 850, 884, 1526, 2585`), so changing it is a much larger, riskier change for no added diagnostic value here (the raw line text already answers "which line").
- Rejected: Absolute line number via `_parse_cards` signature change — too invasive for the value gained.

### gap1-scope-single-check

- Decision: Only `_check_context_completeness` gets the new `line` field.
- Rationale: It is the only check that scans free-form `Requirements:` prose per-line with `backtick_re.findall(line)`, which is the exact mechanism vulnerable to the described split-backtick false positive. `_check_ref_not_backtick_path` (`_plan_validate.py:1166`) scans structured `Context:`/`Edits:`/`Creates:` header values, not prose. `_check_requirements_quote_indent_drift` (`_plan_validate.py:1699`) scans fenced code blocks within `Requirements:`, a different extraction path entirely.
- Rejected: Adding `line` to all checks sharing the `{check, batch, card, path, message}` shape — unnecessary; those checks aren't exposed to this false-positive class.

### gap1-no-existing-test-breakage

- Decision: Adding `line` is purely additive to the error dict; no existing test or consumer needs updating.
- Rationale: Confirmed unit tests in `plugins/mill/unit_tests/test-plan-validate.py` (e.g. `test_check_context_completeness_dirty_missing`) assert on individual keys (`e["check"]`, `e["card"]`, `e["path"]`), never full-dict equality. `mill-plan/SKILL.md`'s fixer-remedy table (line 267) references `message`/token content, not the dict's exact key set.
- Rejected: N/A — no rejected alternative; this is a confirmed-safe observation, not a choice.

### gap2-per-batch-baseline-storage

- Decision: Store each batch's baseline failure-signature set as a new field on that batch's entry in `status.md`'s `## Batches` section (e.g. `verify_baseline_failures: [<signature>, ...]`), added to `_status.py`'s `_BATCH_ALLOWED_KEYS`. An empty list means "clean baseline" (no pre-existing failures for that batch's verify command); a missing/unset field (pre-existing status.md predating this feature, or a batch whose baseline computation failed/was skipped) means "not yet computed" and finalize falls back to today's strict behavior (any failure blocks) — the same fail-safe direction as `module_verify_baseline`'s `None` default.
- Rationale: `## Batches` is already a proper re-serializable yaml list (`_status._write_batches` round-trips via `yaml.safe_dump`), unlike the top yaml block, which `_status.py`'s own module docstring flags as fragile to re-serialize because of `task_description:`'s literal block scalar. Batch name already 1:1-maps to a single `verify:` command per the plan format, so keying by batch name (not by command string) needs no extra indirection.
- Rejected: A new top-level scalar block keyed by verify-command string, mirroring `module_verify_baseline` — avoided due to the top block's re-serialization fragility and the unneeded command-string-keying indirection.

### gap2-compute-eagerly-before-batch-1

- Decision: Compute every batch's verify-command baseline eagerly, once, inside the existing `millpy-implement.py --stage baseline` call (already invoked unconditionally by mill-go before batch 1, idempotent, non-blocking on failure) — not lazily on each batch's own first finalize.
- Rationale: Matches the issue's explicit ask ("snapshot each batch's verify-command failure set before batch 1 starts"). `_status.init_batches` (mill-go's `## Prepare` step) already runs before `--stage baseline` is ever invoked, so every batch's `## Batches` entry exists to write the new field onto. `_plan_dag.iter_batch_verifies(plan_dir, hub_root, git_root)` (used today by `mill-merge-in` and `millpy-fix.py`'s holistic verify-replay) already returns exactly the `(batch_name, verify_cmd, cwd)` triples needed, in DAG order, with null-verify and stale-command batches already filtered out — call it WITHOUT `status_path` at this pre-batch-1 point (no batch has reached `"approved"` yet, so the `status_path`-filtered variant would incorrectly return nothing).
- Rejected: Lazy per-batch computation on first finalize — would run each batch's verify command twice (once as an ad-hoc "is this pre-existing" check, once as the real verify-replay) and doesn't match the issue's stated timing.

### gap2-shared-transient-checkout

- Decision: Extend the baseline computation to run the module-wide command AND every distinct batch verify command inside a single shared transient parent-branch worktree checkout (one `git worktree add`/dependency-junction-setup/teardown for the whole `--stage baseline` invocation), rather than one checkout per command.
- Rationale: `_verify_baseline.compute_baseline`'s checkout + junction setup is the expensive part of the mechanism, and `--stage baseline` fires unconditionally on every mill-go run (even resumed ones, where it no-ops on a cache hit, but a fresh task still pays this cost once). Batching every batch's verify command plus the module-wide command into one checkout materially reduces wall-clock cost without changing the semantics of any individual command's result.
- Rejected: One `compute_baseline`-shaped call per distinct verify command (N+1 separate checkouts) — correct but needlessly slow.

### gap2-failure-signature-extraction

- Decision: Extract `_implementer_common.py`'s existing FAIL-marker-prefix line scan (`"--- FAIL:", "FAIL\t", "FAILED ", "--- FAIL ", "FAIL -- "`, `_implementer_common.py:795`, currently used only to build the truncation marker's earlier-failures excerpt) into a shared helper (e.g. `_extract_failure_signatures(output: str) -> list[str]`), applied to the FULL command output (not just the >2000-char truncation path) both at baseline-computation time and at finalize-diff time. The extracted lines ARE the failure signature set (order-independent set comparison).
- Rationale: This exact marker list already encodes cross-ecosystem failure-line conventions the codebase has already validated (Go's `--- FAIL:`/`FAIL\t`, pytest's `FAILED `, presumably dotnet's `--- FAIL `/`FAIL -- `) — reusing it avoids inventing new per-language parsers and keeps the truncation excerpt and the baseline diff using one consistent notion of "a failure."
- Rejected: Raw full-output byte-diff — too strict; a pre-existing failure whose incidental output (timing, absolute paths) changes between runs would spuriously read as "new." Continuing to use only the binary `"clean"`/`"pre-existing-failures"` verdict for batch-level commands — doesn't give finalize enough information to distinguish "still the same pre-existing failure" from "a new one," which is the whole point of this fix.

### gap2-subset-diff-semantics

- Decision: At finalize, a batch's verify-replay failure is waived (does not raise `stuck_type: verify`/`logic`) only when EVERY extracted failure signature from the replay run is already present in that batch's stored baseline signature set (subset check). Any signature not in the baseline still blocks, even if the baseline set is non-empty.
- Rationale: Issue #770's suggested fix says "a failure that also failed on the pre-task baseline should not, **by itself**, classify the batch as `stuck_type: verify`/`logic`" — the "by itself" wording means other, non-baseline failures in the same run must still block. A binary "skip the whole gate if baseline is non-empty" (mirroring `module_verify_baseline`'s existing behavior) would silently permit a genuine new regression to slip through any batch whose verify command happens to already have one unrelated pre-existing failure.
- Rejected: Binary skip-whole-gate-on-non-empty-baseline — too permissive, defeats the purpose of a regression gate.

### gap2-baseline-corroboration

- Decision: Per-batch baseline computation runs each distinct verify command in the shared transient checkout, and on any failure, runs it once more (same flakiness-guard shape as the module-wide path) — the STORED baseline signature set is the UNION of both runs' extracted failure signatures (not a single run's set, and not a binary "clean"/"dirty" verdict).
- Rationale: A flaky pre-existing failure that only reproduces on one of two runs still needs to be in the baseline (so it doesn't spuriously block a later batch), but unlike the module-wide path's binary verdict, there's no need for a third "control run in the task worktree" step — finalize's own verify-replay run against the real (in-progress) worktree IS the natural downstream corroboration point: if a signature was flagged as baseline via a fluke, a subsequent finalize run simply won't reproduce it and the batch passes cleanly anyway (the diff only excludes signatures that keep recurring in the baseline set, never PENALIZES an extra one).
- Rejected: Reusing the module-wide path's exact three-run (retry + task-worktree control) sequence per batch command — unnecessary extra subprocess cost per distinct command when the union-of-two-runs approach already prevents a single flaky baseline run from being trusted alone, and finalize's own run is a free additional corroboration point the module-wide binary verdict doesn't have.

## Technical context

**Gap 1:**
- `_plan_validate.py:1471` `_check_context_completeness` — the function to change. The per-line loop is at `_plan_validate.py:1536` (`for line in requirements_lines:`); `line` is already in scope when the error dict is built at `_plan_validate.py:1579`.
- `_plan_validate.py:129` `_parse_cards` — NOT to be changed (see Decisions).
- `plugins/mill/unit_tests/test-plan-validate.py` — existing `test_check_context_completeness_*` tests (14 of them) assert on individual dict keys; add a new assertion on `line` to the relevant dirty-case test(s) (e.g. `test_check_context_completeness_dirty_missing`) rather than rewriting them.
- `plugins/mill/skills/mill-plan/SKILL.md:267` — the context-completeness row in the validator-fixer-remedy table; mention the new `line` field so the autonomous fixer can locate the offending Requirements: line without re-deriving it.

**Gap 2:**
- `plugins/mill/scripts/_verify_baseline.py` — today's module-wide-only baseline computation (`compute_baseline`, single command in, `"clean"|"pre-existing-failures"` out). Needs a new function (or an extended signature) that accepts multiple `(name, command, cwd)` triples and returns a `dict[name, list[str]]` of failure signatures per command, sharing one transient checkout. `_DEPENDENCY_DIR_CANDIDATES` junction-reuse logic is already generic enough to reuse as-is.
- `plugins/mill/scripts/millpy-implement.py:78` `_run_baseline_stage` and its call site at `millpy-implement.py:369` (`--stage baseline` branch) — extend to also call `_plan_dag.iter_batch_verifies(plan_base, project_root, git_root)` (no `status_path`) and thread the per-batch results into `_status.set_batch_field`/`set_batch_fields`. `plan_base` is already resolved at `millpy-implement.py:346`, before the `--stage baseline` branch.
- `plugins/mill/scripts/_plan_dag.py:499` `iter_batch_verifies` — existing helper, reused as-is (no changes needed) to enumerate `(batch_name, verify_cmd, cwd)` triples.
- `plugins/mill/scripts/_status.py` — `_BATCH_ALLOWED_KEYS` (line 533) needs the new key added; `get_module_verify_baseline`/`set_module_verify_baseline`/`clear_module_verify_baseline` (lines 335-443) are the pattern to mirror for a new `get_batch_verify_baseline`/equivalent read helper (though writes go through the existing `set_batch_field`/`set_batch_fields`, not a bespoke setter).
- `plugins/mill/scripts/_implementer_common.py:690` `_run_verify_gate` — the function whose stdout+stderr capture (`output = result.stdout + result.stderr`, line 779) is the input to the new shared `_extract_failure_signatures` helper; the existing inline extraction at lines 792-797 (fixed marker-prefix list) becomes that helper's body, called unconditionally (not just in the `>2000` truncation branch). `_run_verify_gates` (line 822) is the caller that would need the batch's stored baseline threaded in (new parameter, parallel to the existing `module_verify_baseline` parameter) to perform the subset-diff before returning a stuck dict.
- `finalize_from_output` (`_implementer_common.py:1324`) and `_forward_output` (`_implementer_common.py:1459`) — both already thread `verify_cmd`/`module_wide_verify_cmd` through to `_run_verify_gates`; the new per-batch baseline value needs to be read from `status.md` (via the new batch-name-keyed lookup) and threaded the same way, at both call sites in `millpy-implement.py` (`finalize` stage and `full` stage).

## Testing

- **`_plan_validate.py` (TDD candidate: extend existing tests, don't rewrite).** Add a targeted test asserting `line` on an existing dirty-case fixture (e.g. `test_check_context_completeness_dirty_missing`) equals the fixture's known offending `Requirements:` line. Add one new test reproducing the issue's exact split-backtick scenario (a backtick-wrapped phrase split across two `Requirements:` lines) to confirm the false-positive's `line` field names the malformed line, not an unrelated one.
- **`_extract_failure_signatures` helper (new, TDD candidate).** Unit-test directly: empty output → empty set; a Go-style `--- FAIL:`/`FAIL\t` sample → expected lines extracted; a pytest `FAILED ` sample → expected lines extracted; output with no recognized markers → empty set (not an error).
- **`_verify_baseline.py`'s extended multi-command computation (TDD candidate).** Mock/fixture-based test (existing convention: in-memory/tempfile, no real git per `plugins/mill/unit_tests/` conventions) verifying: (a) a shared checkout runs N commands and returns N independent signature sets; (b) a command with zero failures yields an empty list, not an absent key; (c) the union-of-two-runs corroboration actually unions rather than overwrites.
- **`_status.py`'s new `## Batches` field (TDD candidate).** Round-trip test: `set_batch_field(status_path, name, "verify_baseline_failures", [...])` then `read_batches` returns the same list; confirm the existing yaml re-serialization (`_write_batches`) doesn't corrupt other batch fields or the top block's `task_description:` literal scalar.
- **`_run_verify_gates`'s subset-diff logic (TDD candidate).** Test matrix: replay failure set ⊆ baseline → gate passes (None); replay failure set has one signature absent from baseline → stuck dict returned, `stuck_type: verify`; baseline absent/None (not yet computed) → falls back to today's strict behavior (any failure blocks), matching the existing fail-safe direction documented for `module_verify_baseline`.
- **Integration-level (per `plugins/mill/integration_tests/` conventions, real git, no real LLM):** a small fixture task whose one batch's `verify:` command has a pre-existing failing test unrelated to the batch's own cards, confirming end-to-end that `--stage baseline` captures it and `--stage finalize` waives it while still catching a genuinely new failure introduced by a mutated fixture in the same test file.

## Q&A log

- **Q:** Should gap 1's new field carry the raw offending line text or a computed absolute file line number? **A:** [auto-pick] Raw line text (`line` field). **Why:** issue accepts either; avoids an invasive `_parse_cards` signature change shared by 5 other checks.
- **Q:** What should the new field be named? **A:** [auto-pick] `line`. **Why:** short, no collision with existing `{check, batch, card, path, message}` keys.
- **Q:** Should the `line` field also be added to sibling checks sharing the same error-dict shape? **A:** [auto-pick] No — only `_check_context_completeness`. **Why:** it's the only check vulnerable to the per-line split-backtick false-positive class; siblings scan structured header values or fenced blocks, not free `Requirements:` prose per-line.
- **Q:** Should `mill-plan/SKILL.md`'s context-completeness fixer-remedy row be updated to mention the new field? **A:** [auto-pick] Yes. **Why:** cheap, directly increases the fix's value for the autonomous fixer.
- **Q:** How should batch-level verify failures be compared against a pre-task baseline — fixed FAIL-marker-prefix line extraction, raw output diff, or keep the existing binary clean/dirty verdict? **A:** [auto-pick] Fixed FAIL-marker-prefix extraction, refactored out of `_implementer_common.py`'s existing truncation logic into a shared helper. **Why:** already-proven cross-ecosystem marker set; raw diff is too strict (cosmetic output changes read as new failures); binary verdict can't satisfy the issue's explicit "diff...failures" ask.
- **Q:** Where should each batch's baseline failure set be stored in `status.md`? **A:** [auto-pick] A new field on each `## Batches` entry (e.g. `verify_baseline_failures`). **Why:** that section round-trips safely via `yaml.safe_dump`; the top block risks corrupting `task_description:`'s literal scalar on re-serialization.
- **Q:** When should each batch's baseline be computed — eagerly before batch 1, or lazily on that batch's own first finalize? **A:** [auto-pick] Eagerly, inside the existing `--stage baseline` call before batch 1, using `_plan_dag.iter_batch_verifies` with no `status_path` filter. **Why:** matches the issue's explicit timing ask; avoids double-running each batch's verify command.
- **Q:** Should each batch's verify command get its own transient parent-branch checkout, or share one checkout with the module-wide baseline? **A:** [auto-pick] Share one checkout for the whole `--stage baseline` invocation. **Why:** checkout/junction setup is the expensive part; one teardown instead of N reduces cost without changing per-command semantics.
- **Q:** At finalize, should a batch be waived only when its ENTIRE new failure set is already in its baseline (subset check), or waived whenever its baseline is non-empty at all (binary skip)? **A:** [auto-pick] Subset check — any signature not already in the baseline still blocks. **Why:** the issue's "by itself" wording implies other new failures must still block; a binary skip would mask genuine regressions once any pre-existing failure exists in that command's history.
