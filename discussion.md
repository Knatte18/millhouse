# Discussion: review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure

```yaml
task: 'review-subsystem-fixes — Review subsystem: deleted-refs + execution infrastructure'
slug: review-subsystem-fixes
status: discussing
parent: main
```

## Problem

The review subsystem has nine known defects spanning two domains. Both block mill-go from running reliably end-to-end. **Domain A — content** covers how `_review_common.resolve_ref_paths` handles paths that have been deleted or renamed: a card that lists a file under `Reads:` and then `git rm`s it in the same commit hard-fails post-implementation review (#103); deleted/renamed files referenced in `Reads:`/`Modifies:` give the reviewer no signal that the absence is intentional, so the reviewer can flag stale plan refs that aren't actually stale (#77, #78). **Domain B — execution infrastructure** covers seven subprocess and error-reporting bugs in `_llm_claude` and the review CLIs: holistic reviews need a longer timeout than per-batch (#80); the per-batch default is too tight for `effort max` on a 485-line batch with cold cache (#83); on Windows `subprocess.run(timeout=N)` overshoots by ~200s because the spawned `node`/`claude` process tree survives the parent kill (#86); a holistic that hangs mid-round forces the orchestrator to re-fire every per-batch in the next round even though those files are already on disk (#87); rate-limit rejections from claude exit 1 with empty stderr so callers cannot distinguish rate-limit, auth missing, and crash (#93); when every per-batch and holistic returns `verdict: ERROR` the aggregate is `REQUEST_CHANGES` with no review files, and the orchestrator's fix-pass step crashes trying to read non-existent files (#84); `ReviewError` surfaces only the bracketed prefix line on stderr with no `ERROR:` marker and no traceback (#104). The fixes are tightly clustered — six files, all under `plugins/mill/`. **Why now:** task 6 (mill-go SKILL.md + lock-API) is in flight and depends on the review backend behaving deterministically. Without these fixes a single rate-limit or a single deleted file inside a batch derails the whole pipeline.

## Scope

**In:**
- New `Deletes:` field on plan-batch cards, parsed and validated alongside `Reads`/`Modifies`/`Creates`.
- `compute_deletes_union()` helper in `_review_common.py`, mirroring `compute_creates_union()`.
- `resolve_ref_paths()` accepts a `deletes_union` keyword (silent-suppress just like `creates_union`).
- New `## Intentionally deleted` section appended to reviewer prompts (per-batch and holistic, plan and code) when `deletes_union` is non-empty.
- New `llm.holistic_timeout` config key in `wiki/config.yaml` (default 1800s); `_review_plan` and `_review_code` pass it on the holistic call.
- Bump `llm.bulk_timeout` default to 900s.
- Replace `subprocess.run(timeout=)` in `_subprocess_util.run` with a `Popen` + manual-timeout loop that, on timeout, terminates the parent then kills the entire process tree (`taskkill /T /F /PID` on Windows, `os.killpg(SIGKILL)` on POSIX) after a 5s grace period.
- Mid-round-aware resume in `_review_plan.run`: if no holistic file exists for round N but per-batch round N files exist, treat round N as in-progress; reuse the per-batch round-N files (regardless of verdict, parsing the verdict from disk for the aggregate) and only fire the holistic.
- Stream-json scanner in `_llm_claude` detects `rate_limit_event` and `result.is_error == true`; new `LLMRateLimitError(LLMError)` subclass raised by `_invoke` on non-zero exit when a rate-limit signal is observed.
- ERROR-only-aggregate retry policy added to `mill-plan` SKILL.md (Phase: Plan Review, new step 4.5): skip fix-pass when every entry has `verdict: ERROR`, re-run the CLI; halt with `BLOCKED: review ERROR-only round {N}` after two consecutive ERROR-only rounds.
- Remove the total-fail `raise ReviewError` block in `_review_plan.run` (lines 529–534) so an all-ERROR plan review still emits a parseable `ReviewResult` JSON envelope (`verdict: REQUEST_CHANGES`, `reviews[]` populated with the ERROR entries). The orchestrator's ERROR-only retry then has something to evaluate.
- Patch `_review_code.run` ERROR handling for consistency: replace the `raise ReviewError(f"Code reviewer failed: {exc}") from exc` block (lines 240–242 and the equivalent `LLMError` handler in the NEED_CONTEXT resume retry on lines 267–268) with a structured `verdict: ERROR` `ReviewResult` return — same shape as the `_review_plan` per-batch ERROR entry already produces. mill-go's existing review-loop logic gets the same JSON-first contract as plan review.
- All three review CLI scripts (`millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`) catch `ReviewError` at top level and print `ERROR: <message>` (uppercase prefix) to stderr; when the message starts with `[resolve_ref_paths]`, append a one-line hint pointing at the originating plan card.
- Unit-test coverage for every helper change.

**Out:**
- `mill-go` SKILL.md — owned by task 6 (mill-go-fixes); ERROR-only retry inside mill-go's review loop is a separate fix and not part of this task.
- Reviewer-module additions (cluster, sonnetmax_max, etc.) — task 13.
- Validator additions for `Deletes:` (`non-existent-path`, `card-missing-field`, etc. for the new field) — covered here as a small extension to `_plan_validate`, but no broader validator overhaul.
- `mill-plan` skill validator-fix mapping table for `Deletes:` — covered, but no other rows touched.
- Code review mid-round resume — `_review_code.run` is single-scope per call; mill-go invokes it batch-by-batch and there is no in-call resume gap.
- Process-tree kill on POSIX is implemented but not the priority; CI is Windows-first for this repo.
- Replacing `subprocess` with `psutil` or Win32 Job Objects — explicit decision: stay with stdlib `Popen` + `taskkill` / `killpg`.
- Backend-internal retry on rate-limit (the orchestrator decides; backend records `verdict: ERROR` with `error: rate_limit: ...`).
- Discussion-review backend changes — discussion review never bulks plan refs, so deletes_union does not apply there.

## Decisions

### deletes-field-on-cards

- **Decision:** Add a fourth ref field on every plan-batch card: `Deletes:`. Same shape as `Reads`/`Modifies`/`Creates` — backtick-wrapped paths, "none" sentinel, single-line or multi-line bullet form. Update `plan-batch.md` template, `_REQUIRED_CARD_FIELDS` in `_plan_validate.py`, and add a `compute_deletes_union()` helper symmetric with `compute_creates_union()`.
- **Rationale:** Explicit intent; validatable; matches the v1 convention. Lets the reviewer be told exactly which files are *intentionally* gone vs which are stale plan refs.
- **Rejected:** Sentinel-marker reuse of `Modifies:` (parse becomes case-y, fragile against typos); auto-derive from `git diff parent..HEAD` (only works post-implementation, bypasses planner declaring intent, doesn't help plan-review at all).

### deletes-union-flow

- **Decision:** `resolve_ref_paths()` accepts a `deletes_union` keyword (set of raw token strings). When a candidate path is missing on disk, it's silent-suppressed if it's in *either* `creates_union` or `deletes_union`. Reviewer prompts get a new `## Intentionally deleted` section listing the deletes (when non-empty), built by a new `build_deletes_section(deletes_paths)` helper in `_review_common.py`.
- **Rationale:** Mirrors the existing `creates_union` semantics, so the helper signature stays clean and predictable. The explicit prompt section is the actual fix for #77/#78 — without it the reviewer doesn't know the absence is deliberate.
- **Rejected:** Silent-suppress only (loses the explicit signal #77/#78 are about); a generic "## Notes about referenced files" section that mixes deletes and creates (muddier signal).

### no-pending-creations-section

- **Decision:** Files that resolve into `creates_union` but not yet on disk stay silently skipped. No "## Pending creations" section in the prompt.
- **Rationale:** They're expected to appear as the batch runs; plan review evaluates them via the card text directly, code review sees them on disk after the batch. The signal is already implicit.
- **Rejected:** Surfacing them adds noise without changing reviewer behaviour in the cases we hit.

### holistic-timeout-config-key

- **Decision:** Add `llm.holistic_timeout` to `wiki/config.yaml` (default 1800s). `_review_plan.run` and `_review_code.run` read it from `cfg["llm"]["holistic_timeout"]` and pass it to the reviewer module's `run()` call for the holistic invocation. The per-batch path keeps using `bulk_timeout`.
- **Rationale:** Holistic prompts bulk every batch + every referenced file — typically 5–10× the per-batch size. Matching budget to prompt size is cleaner than bumping `bulk_timeout` to cover the worst case.
- **Rejected:** Single bumped `bulk_timeout: 1200` covering both (per-batch waste, masks slow reviewers).

### bump-bulk-timeout-default

- **Decision:** Raise `llm.bulk_timeout` default from 600 to 900. Keep `tool_use_timeout: 900` and `implementer_timeout: 3600` unchanged.
- **Rationale:** 600s repeatedly times out on `effort max` per-batch reviews against 400+ line batches with cold cache (#83). 900s leaves enough headroom without making a slow reviewer invisible.
- **Rejected:** 1200s (masks slow reviewers); leave at 600s and force per-worktree overrides (every operator hits this; not an override case).

### subprocess-tree-kill-stdlib

- **Decision:** Rewrite `_subprocess_util.run` to use `subprocess.Popen` with manual timeout polling. On timeout, send `terminate()`, wait `_GRACE_SECONDS = 5`, then if the process is still alive call `taskkill /T /F /PID <pid>` on Windows or `os.killpg(os.getpgid(pid), signal.SIGKILL)` on POSIX (with `start_new_session=True` on the Popen). Keep the existing `[subprocess] spawn / exit` breadcrumbs and `subprocess.TimeoutExpired` semantics so callers don't change.
- **Rationale:** Stdlib-only; no new dependency. `taskkill /T` walks the process tree (covers `cmd.exe → npm shim → node → claude`), which is what `subprocess.run(timeout=)` fails to do today (#86). 5s grace lets stream-json flush a final result line.
- **Rejected:** `psutil` (one-feature dep); Windows Job Objects via `pywin32` (cleanest on Windows but adds platform-specific dep + diverging code paths); 0s grace (loses last stream-json line).

### mid-round-resume-discover-round

- **Decision:** Extend `discover_round` (or add a sibling helper used only by `_review_plan.run`) to recognise mid-round state. Concretely: if the highest round number `N` for which any plan-batch file exists has *no* corresponding plan-holistic file at round `N`, treat round `N` as the active round. `_review_plan.run` detects this case before kicking off per-batch work; in that case it skips the per-batch ThreadPoolExecutor entirely, reads each round-N per-batch file from disk, parses the verdict, and assembles the `reviews[]` array from disk. The holistic then fires at round N (not N+1).
- **Rationale:** Closes #87 cleanly. Never re-fires a per-batch that already has a verdict file. `_scan_approved_batches` already handles the cross-round APPROVE carryforward; this adds the orthogonal mid-round resume.
- **Rejected:** A `--resume` CLI flag (extra knob; user has to know to pass it); manual file deletion before re-run (error-prone; reviewer LLM tokens already spent).

### code-review-no-resume

- **Decision:** Don't add mid-round resume to `_review_code.run`. Single-scope per call; mill-go calls it once per batch and once for holistic. No in-call resume window exists.
- **Rationale:** No observed bug; adding parity here is dead code.
- **Rejected:** Parity-for-its-own-sake.

### error-only-aggregate-retry-in-skill

- **Decision:** ERROR-only-aggregate retry lives in **mill-plan SKILL.md** (Phase: Plan Review, new step 4.5: pre-fix-pass). Step 4.5 fires after step 4c parses the JSON envelope: if every entry's `verdict` is `ERROR`, skip the fix-pass entirely and re-run the CLI immediately (no round counter consumed — the round produced no reviewable output). Halt with `BLOCKED: review ERROR-only round {N}` after two consecutive ERROR-only rounds. Backend (`_review_plan.run`) stays stateless across runs. **Backend prerequisite:** the existing total-fail block in `_review_plan.run` (lines 529–534, `if reviews and all(r["verdict"] == "ERROR" for r in reviews): raise ReviewError(...)`) is removed entirely. After removal the function falls through to `aggregate_verdict([...])` which already maps ERROR to `REQUEST_CHANGES`, so the CLI prints a valid JSON envelope on stdout with `verdict: REQUEST_CHANGES` and an all-ERROR `reviews[]` array. That JSON is what step 4.5 evaluates.
- **Rationale:** Matches the proposal's location. Backend remains pure (no retry policy embedded). The two-pass cap mirrors the validator-fix two-pass cap already in step 1.5 — same shape, easy to reason about. Removing the total-fail check is the load-bearing change: without it the orchestrator has no JSON to inspect.
- **Rejected:** Retry-inside-backend (couples retry policy to backend; harder to test; same retry would have to be re-implemented for code review). Keeping the total-fail check (silently breaks step 4.5).

### code-review-error-handling-parity

- **Decision:** Patch `_review_code.run` to record `verdict: ERROR` instead of raising. The two `raise ReviewError(f"Code reviewer failed: {exc}") from exc` sites — at line 242 (initial `reviewer.run` call) and at line 268 (NEED_CONTEXT resume retry) — both replaced with constructing a single-entry `ReviewResult(type="code", round=round_n, verdict="REQUEST_CHANGES", blocking_count=0, reviews=[{"scope": scope_label, "verdict": "ERROR", "file": None, "error": str(exc), "session_id": None}])` and returning it. Same shape as the per-batch ERROR entry `_review_plan._review_one_batch` already produces.
- **Rationale:** Code review currently explodes with no JSON when the LLM errors, mirroring the same JSON-contract violation #84 calls out for plan review. mill-go's review-loop benefits from the same JSON-first contract as mill-plan; ERROR-only retry semantics can be applied uniformly later (out of scope for this task — mill-go SKILL.md is task 6).
- **Rejected:** Leave `_review_code.run` as-is (perpetuates the JSON-contract gap; same bug, different surface).

### llm-rate-limit-error-class

- **Decision:** Add a new `_scan_rate_limit(stdout: str) -> bool` helper in `_llm_claude.py` that scans every line of the captured stdout for a `rate_limit_event` event-type or a `result` event with `is_error: true` AND a rate-limit subtype/message marker (matched by substring against the known claude CLI markers). Restructure `_invoke` so it calls `_parse_stream_json(stdout)` defensively (wrapped to swallow `LLMError` on the no-content path) and `_scan_rate_limit(stdout)` *before* the existing exit-code branch. On non-zero exit AND `_scan_rate_limit` true, raise `LLMRateLimitError(msg)` — taking precedence over `LLMSessionError` and the generic `LLMError`. On non-zero exit with no rate-limit signal, raise the existing `LLMError`/`LLMSessionError` exactly as today. Zero-exit path is unchanged. `_parse_stream_json` keeps its `(text, session_id)` signature; rate-limit detection is a sibling concern.
- **Rationale:** Typed exceptions let callers distinguish rate-limit from generic crash without string-matching. Keeping `_parse_stream_json` clean separates the "what did the assistant say" parser from the "did the platform throttle us" scanner. The retry policy still lives in the orchestrator; the backend records `verdict: ERROR, error: "rate_limit: <msg>"` and the SKILL.md step 4.5 ERROR-only retry handles it naturally.
- **Rejected:** Returning a 3-tuple from `_parse_stream_json` (every caller updates for one feature); raising from inside `_parse_stream_json` itself (parser deciding error semantics is surprising); only improving the error string (loses typed-handling option).

### review-error-cli-prefix

- **Decision:** All three CLI scripts catch `ReviewError` at top level and print `ERROR: <message>` to stderr (uppercase prefix). When `<message>` starts with `[resolve_ref_paths]`, append a one-line hint to stderr: `Hint: check the plan card referencing this file; if the file is intentionally deleted, list it under Deletes: in that card.` Exit 1 unchanged.
- **Rationale:** Tooling-friendly (consistent prefix); hints point the operator at the new `Deletes:` mechanism for the most common cause; no traceback noise. Matches #104.
- **Rejected:** Always-print-traceback (noisy; the message is the actionable bit); env-var-gated traceback (extra knob nobody will set the first time it bites them).

### testing-scope

- **Decision:** Unit tests added for: `compute_deletes_union` (parser edge cases — single-line, multi-line, "none", missing field); `resolve_ref_paths` with `deletes_union` (silent-suppress; both unions populated; conflict between the two — favours suppression); `discover_round` mid-round resume case (per-batch round N present, holistic round N absent → returns N); ERROR-only aggregate detection (helper if extracted, else covered by SKILL.md prose); `_parse_stream_json` rate-limit detection (fixture stream-json blob with a `rate_limit_event` line); CLI ERROR-prefix output (subprocess invocation against a fixture wiki + plan triggering each path). All in-memory / `tempfile`. No real claude CLI, no real git.
- **Rationale:** Every helper has a tight, isolatable surface. Fixture-based stream-json testing covers the rate-limit parser without real API calls. CLI-output tests catch regressions in the formatter.
- **Rejected:** Skipping unit coverage for the kill path is correct (hard to TDD across platforms); a separate integration test for SIGKILL grace can be added later if a regression hits — covered as a stretch in the testing section below.

### tdd-candidates

- **Decision:** TDD-first for: (1) `compute_deletes_union` parser, (2) `resolve_ref_paths` with `deletes_union`, (3) mid-round resume detection, (4) `_parse_stream_json` rate-limit detection. Process-tree kill is *not* TDD (integration-shaped; fixture would need cross-platform sleep-loop spawning).
- **Rationale:** These four have pure inputs and outputs. Writing tests first locks the contract before the implementation drifts.
- **Rejected:** TDD for process-tree kill (covered above).

## Technical context

**Files mill-plan needs to know about and the role each plays in this task.**

- **`plugins/mill/scripts/_review_common.py`** — shared helpers, regex constants, exceptions, `ReviewResult` dataclass. Houses `parse_batch_refs`, `compute_creates_union`, `resolve_ref_paths`, `resolve_existing_paths`, `bulk_files`, `build_manifest_section`, `build_reattached_section`, `discover_round`, `aggregate_verdict`, `load_config`. Most of the Domain-A work lands here: new `compute_deletes_union`, new `build_deletes_section`, extension of `resolve_ref_paths` to accept `deletes_union`, possible refactor of `parse_batch_refs` so `Reads`/`Modifies`/`Creates`/`Deletes` share one parser.
- **`plugins/mill/scripts/_llm_claude.py`** — wraps `claude -p` via `_subprocess_util.run`. Houses `LLMError`, `LLMSessionError`, `_parse_stream_json`, `run_bulk`, `run_tool_use`, `run_implementer`. Add `LLMRateLimitError`, extend `_parse_stream_json` to detect rate-limit events. The default `timeout=600` in `run_bulk` is replaced by callers passing the config value; the literal default stays for safety.
- **`plugins/mill/scripts/_subprocess_util.py`** — single subprocess wrapper used by every mill script. Domain-B work: switch `subprocess.run` to `Popen` + manual timeout poll + tree kill. Preserve the spawn/exit breadcrumbs and the existing `subprocess.TimeoutExpired` exception so every other caller keeps working.
- **`plugins/mill/scripts/_review_plan.py`** — plan-review backend. Per-batch parallel via `ThreadPoolExecutor`, optional holistic, `_scan_approved_batches` for cross-round APPROVE carryforward. Mid-round-resume logic lands here (between the path/round resolution and the per-batch dispatch). Holistic-timeout pass-through lands here.
- **`plugins/mill/scripts/_review_code.py`** — code-review backend. Single-scope per call. Holistic-timeout pass-through (when `batch_name is None`). No mid-round resume.
- **`plugins/mill/scripts/_review_discussion.py`** — discussion-review backend. Out of scope; discussion review doesn't bulk plan refs.
- **`plugins/mill/scripts/millpy-review-discussion.py` / `millpy-review-plan.py` / `millpy-review-code.py`** — three CLI scripts. Each ends with `except ReviewError as exc: print(str(exc), file=sys.stderr); return 1`. Replace with `ERROR:` prefix + the resolve_ref_paths hint when applicable. Same change in all three; consider extracting a `_review_cli.print_error(exc)` helper to avoid duplication.
- **`plugins/mill/scripts/_plan_validate.py`** — plan validator. Holds `_REQUIRED_CARD_FIELDS = ["Reads", "Modifies", "Creates", "Requirements", "Commit"]`. Add `"Deletes"` to that list. Extend `_check_non_existent_path` (or whatever the current function name is — there's a `non-existent-path` rule today via `parse_batch_refs`) to accept a new `deletes_union: set[str]` parameter computed from `compute_deletes_union(plan_dir)`. Gating: a token from `Reads:`/`Modifies:` that is missing on disk is skipped if it's in `deletes_union` (mirrors the existing `creates_union` gate). For `Deletes:` tokens specifically, the validator REQUIRES the path to resolve to an on-disk file at validation time OR to be in `creates_union` (covers the cross-batch case where batch 01 creates X and batch 02 deletes X). A `Deletes:` token that's missing on disk AND not in `creates_union` is a `non-existent-path` error — keeps the validator-as-source-of-truth contract for the new field. Cross-card consistency check ("a path can't be in `Deletes:` of card N AND `Reads:`/`Modifies:` of card M>N") is flagged as out-of-scope here.
- **`plugins/mill/templates/plan-batch.md`** — card template. Add `- **Deletes:**` field documentation (same shape as `Creates:`).
- **`wiki/config.yaml`** — add `llm.holistic_timeout: 1800`; bump `llm.bulk_timeout` to 900. Comment block above explains both.
- **`plugins/mill/skills/mill-plan/SKILL.md`** — Phase: Plan Review, add step 4.5 (ERROR-only-aggregate retry, two-pass cap). Update the validator-fix mapping table to include rows for `Deletes:` if any new validator codes appear (likely none for the minimal extension).
- **`plugins/mill/unit_tests/`** — flat layout; one `test-<name>.py` per helper. Add tests next to existing `test-_review_common.py` (or whatever exists) covering deletes_union, mid-round resume, rate-limit parser. Tests are run via `python plugins/mill/unit_tests/run-all.py` per CLAUDE.md.

**Helpers to reuse:**

- `_RE_REFS_HEADER` and `_RE_REFS_SUB` regex constants in `_review_common.py` already cover `Reads|Modifies|Creates`. Extend the alternation to include `Deletes`. Same parser handles all four fields.
- `compute_creates_union` is the shape `compute_deletes_union` should copy (filter `Creates` → filter `Deletes`).
- `build_manifest_section`, `build_reattached_section` are the templates for `build_deletes_section` (header + bullet list).
- `_subprocess_util.run`'s `[subprocess] spawn` / `[subprocess] exit` breadcrumb format must be preserved verbatim — smoke tests grep for it.

**Gotchas discovered during exploration:**

- `_review_plan.py` already calls `_scan_approved_batches` for cross-round APPROVE carryforward (line 49). The mid-round resume is orthogonal: same code path that builds the `approved_carry` dict can be extended (or a sibling helper added) to also detect "round-N batch files exist regardless of verdict, holistic-N missing → reuse them." Don't conflate the two.
- The `_load_root_from_overview` parser reads the first ```yaml fenced block in `plan/00-overview.md`. Discussion frontmatter uses the same convention. Don't break it.
- `parse_verdict` accepts `APPROVE | REQUEST_CHANGES | GAPS_FOUND | NEED_CONTEXT`. The mid-round resume path needs to handle every value (APPROVE → approve_carry, REQUEST_CHANGES → mid-round-reuse, GAPS_FOUND → discussion-only so won't appear in plan-review files, NEED_CONTEXT → ambiguous; treat the file as in-progress and re-fire only if mid-round resume detects no holistic). Actually NEED_CONTEXT should propagate as-is — the operator already saw the prior NEED_CONTEXT outcome and re-running is the intended response; do not re-fire automatically.
- `_subprocess_util.run` is called by `_llm_claude` and by every mill script that touches git. Rewriting it must keep the existing return shape (`subprocess.CompletedProcess[str]`) and the `subprocess.TimeoutExpired` exception type — every caller depends on both.
- On Windows the `_claude_argv_prefix` returns `["cmd", "/c", "claude"]` — three layers (cmd.exe → npm shim → node). `taskkill /T /F /PID <cmd-pid>` walks the tree; verify by checking it kills the node process too in the unit/integration check.
- `start_new_session=True` on POSIX `Popen` puts the child in its own process group so `os.killpg` works. On Windows the equivalent is `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`, but `taskkill /T` doesn't need it — it walks parent-child via the Win32 process snapshot.
- Existing tests import `_review_common` directly; they don't go through the CLI. Test files for the new helpers should follow the same pattern.
- The proposal calls out fix locations including `mill-plan/SKILL.md`. mill-go SKILL.md is a separate task (task 6); don't touch it from this plan.
- Card numbering is GLOBAL across batches (per mill-plan SKILL.md). Cards in batch 02 keep counting from where batch 01 left off.

## Constraints

- **No `${CLAUDE_PLUGIN_ROOT}` violations.** All intra-plugin paths in any new SKILL.md prose, helper, or template reference `${CLAUDE_PLUGIN_ROOT}`, never `plugins/mill/...`. (CLAUDE.md.)
- **`uv run --project "${CLAUDE_PLUGIN_ROOT}"` for all script invocations.** No bare `python`. (CLAUDE.md.)
- **Junctions are IDE convenience only.** Code resolves real paths via `_paths.py`. Never hand a junction path to a Python helper. (CLAUDE.md / wiki/config.yaml header.)
- **No working-state writes to wiki.** `status.md`, `discussion.md`, `plan/`, `reviews/` live on the task branch. Wiki holds only `Home.md` and `config.yaml`. (CLAUDE.md.)
- **Fenced ```yaml metadata in generated markdown.** `---` is reserved for `SKILL.md` and plugin manifests. (CLAUDE.md / mill:markdown.)
- **Tight v1 review style.** Reviews target a few hundred tokens; per-finding = severity-label + 3–4 short bullets. The new `## Intentionally deleted` section is a bullet list, not prose.
- **Stdlib-only subprocess kill.** No `psutil`, no `pywin32`. (Decision `subprocess-tree-kill-stdlib`.)
- **Preserve `_subprocess_util.run` contract.** Same return type (`CompletedProcess[str]`), same `subprocess.TimeoutExpired` propagation, same `[subprocess]` breadcrumbs on stderr.
- **Card globally-numbered.** Cards across batches in this plan must keep a single ascending counter; reviewer/implementer cite cards by number.
- **`Reads:`/`Modifies:`/`Creates:`/`Deletes:` content rule.** Backtick-wrapped paths only, one per indented bullet. No inline parenthetical notes, no line-range suffixes — this is a validator-enforced rule that already covers the existing fields and must apply uniformly to `Deletes:`.
- **No `if __name__ == "__main__":` smoke-test blocks in helpers.** (CLAUDE.md `plugins/mill/scripts/`.)
- **Tests live in `plugins/mill/unit_tests/` as `test-<name>.py`, in-memory / `tempfile` fixtures.** Run via `python plugins/mill/unit_tests/run-all.py`. (CLAUDE.md.)

## Testing

**Per-module test approach.** TDD-first for the four candidates listed under `tdd-candidates`; tests-after for the rest.

**`_plan_validate` Deletes-aware path checks (`_plan_validate.py`):**
- `_REQUIRED_CARD_FIELDS` includes `"Deletes"` (every card must have the field; "none" is the empty sentinel).
- `Deletes:` token resolves to an on-disk file → no error.
- `Deletes:` token missing on disk AND in `creates_union` (cross-batch case) → no error.
- `Deletes:` token missing on disk AND not in `creates_union` → `non-existent-path` error.
- `Reads:`/`Modifies:` token missing on disk AND in `deletes_union` → no error (suppressed by deletes_union).
- `Reads:`/`Modifies:` token missing on disk AND in `creates_union` (existing behaviour) → no error.
- `Reads:`/`Modifies:` token missing on disk AND in NEITHER union → `non-existent-path` error (existing behaviour).

**`compute_deletes_union` (`_review_common.py`) — TDD:**
- Empty plan_dir → empty set.
- Single batch, single-line `- **Deletes:** \`a\`, \`b\`` → `{"a", "b"}`.
- Single batch, multi-line bullet form (`- **Deletes:**\n  - \`a\`\n  - \`b\``) → `{"a", "b"}`.
- `none` filter (case-insensitive: `None`, `NONE`, `none`).
- Two batches with overlapping deletes → de-duplicated set.
- `Deletes:` field absent on a card → that card contributes nothing; other cards in same batch still contribute.
- `00-overview.md` is skipped (mirrors `compute_creates_union`).

**`resolve_ref_paths` extension (`_review_common.py`) — TDD:**
- Path missing on disk + in `deletes_union` → silent suppress (no resolve, no error).
- Path missing on disk + in `creates_union` → silent suppress (existing behaviour preserved).
- Path missing on disk + in BOTH unions → silent suppress (favour suppression).
- Path missing on disk + in NEITHER → `ReviewError` (existing behaviour preserved).
- Path on disk + in `deletes_union` → resolve and return (path was deleted by a later card but still present at review time; treat as on-disk).
- Caller-label propagation: when raised, error message contains the supplied `caller_label` prefix.

**`build_deletes_section` (`_review_common.py`):**
- Empty list → empty string.
- Non-empty list → `## Intentionally deleted (N=<count>)\n\n- <path-1>\n- <path-2>\n...`.
- No trailing newline (matches `build_manifest_section` shape).

**`discover_round` mid-round behaviour (`_review_common.py`) — TDD:**
- The mid-round resume detection is *not* in `discover_round` itself (which keeps the strict max+1 contract); it's a new helper, e.g. `detect_resume_round(reviews_dir, review_type)`, returning `int | None`. Tests:
  - No files at all → `None`.
  - Per-batch round 1 files exist + holistic round 1 file exists → `None` (not in mid-round; round 1 complete).
  - Per-batch round 1 files exist + no holistic round 1 file → `1`.
  - Per-batch rounds 1 and 2 files exist + holistic round 1 file + no holistic round 2 file → `2`.
  - Per-batch round 2 partial (some batches at round 2, some only at round 1) + no holistic round 2 → `2` (highest seen).
- This helper is consumed only by `_review_plan.run`; tests cover the helper, not the integration.

**`_review_plan.run` mid-round resume integration (`_review_plan.py`):**
- Fixture: a `reviews_dir` populated with a complete round-1 per-batch set (verdicts mixed APPROVE/REQUEST_CHANGES) and no holistic. Run `_review_plan.run` with a fake reviewer that records calls. Assert the per-batch reviewer is *not* called; the holistic reviewer is called once at round 1; the assembled `reviews[]` contains the disk-loaded per-batch entries (with their parsed verdicts) plus the new holistic entry. Aggregate is the worst-case across the disk-loaded verdicts and the holistic.

**`_scan_rate_limit` + `_invoke` integration (`_llm_claude.py`) — TDD:**
- `_scan_rate_limit` unit cases: stdout containing a `rate_limit_event` line → True; stdout with `result` event having `is_error: true` and a rate-limit subtype/message marker → True; stdout with `result.is_error: true` but no rate-limit marker → False (generic error, falls through to `LLMError`); empty stdout → False; malformed stream-json (one bad line, others good) → scan continues, returns based on the rest.
- `_invoke` integration cases (mocking `_subprocess_util.run`): non-zero exit + `_scan_rate_limit` true → expect `LLMRateLimitError` (taking precedence over `LLMSessionError` even when `resume=True`); non-zero exit + `_scan_rate_limit` false + `resume=True` → `LLMSessionError` (existing behaviour); non-zero exit + `_scan_rate_limit` false + `resume=False` → `LLMError`; zero exit → `(text, session_id)` tuple unchanged.
- `_parse_stream_json` regression: signature unchanged, returns `(text, session_id)`, raises `LLMError` on no content. Existing tests stay green.

**ERROR-only aggregate detection:**
- The retry policy is in `mill-plan/SKILL.md` prose; no helper to test directly. Cover via a SKILL.md-level walkthrough in the discussion log, not unit tests.
- If `aggregate_verdict` ends up changing to expose ERROR-only (e.g. a new return value or a flag), that's a programmatic surface and gets a test. Default decision: don't change `aggregate_verdict`; the orchestrator re-checks `all(r["verdict"] == "ERROR" for r in result["reviews"])` itself. No new helper, no new test.

**`_review_plan.run` post-removal-of-total-fail (`_review_plan.py`):**
- Fixture: a fake reviewer that always raises `LLMError`; a plan with two batch files. Run `_review_plan.run` and assert it returns a `ReviewResult(verdict="REQUEST_CHANGES", reviews=[…each entry verdict==ERROR…])` rather than raising. The CLI invocation prints valid JSON.
- Mixed: one batch ERROR, one batch APPROVE, holistic ERROR → aggregate `REQUEST_CHANGES`, three reviews entries.

**`_review_code.run` ERROR-handling parity (`_review_code.py`):**
- Fixture: fake reviewer raising `LLMError` on the first call. Run `_review_code.run` for both `batch_name="<name>"` and `batch_name=None`. Assert it returns a `ReviewResult(verdict="REQUEST_CHANGES", reviews=[{"scope": ..., "verdict": "ERROR", "file": None, "error": "...", "session_id": None}])` rather than raising.
- Same fixture but the failure happens on the resume retry (NEED_CONTEXT path) → assert the same ERROR-recording return.

**CLI `ERROR:` prefix output:**
- Each of the three `millpy-review-*.py` scripts: invoke via `subprocess.run` against a fixture worktree with a deliberate trigger (missing slug → already raises ReviewError), assert stderr starts with `ERROR: `.
- For the `[resolve_ref_paths]`-prefixed case, use a plan with a `Reads:` ref to a non-existent file (no `Deletes:` cover) and assert the hint is appended.
- These tests are stdlib-`subprocess` driven and don't spawn claude.

**Process-tree kill (`_subprocess_util.py`):**
- Not TDD. Optional follow-up integration test using a fixture child that traps SIGTERM and sleeps (POSIX) or a long-running `cmd /c timeout /t 9999` (Windows). Assert that within `grace + small_delta` the parent and the child are both gone (`os.kill(pid, 0)` raises). Marked optional in the plan; can be slot in later.

**Run-all integration:** `python plugins/mill/unit_tests/run-all.py` must be green at the end of every batch.

**Out:** mocking real `claude` CLI; running `_review_code.run` with a real LLM; full mill-plan SKILL.md walkthrough (those are operator-facing; smoke-tested by re-running the review on an existing fixture plan).

## Q&A log

- **Q:** How should "intentional delete" be represented? **A:** New `Deletes:` field on cards, parsed alongside `Reads`/`Modifies`/`Creates`.
- **Q:** Where does `deletes_union` flow? **A:** `resolve_ref_paths` accepts a `deletes_union` keyword (silent-suppress); reviewer prompts get a new `## Intentionally deleted` section.
- **Q:** Should pending-but-not-yet-on-disk creates also be surfaced to the reviewer? **A:** No. Keep silent — the signal is implicit.
- **Q:** `holistic_timeout` config key? **A:** Yes, default 1800s, separate from `bulk_timeout`.
- **Q:** Bump `bulk_timeout` default? **A:** Yes, 600s → 900s.
- **Q:** Subprocess overshoot fix? **A:** `Popen` + manual timeout + `taskkill /T /F` (Windows) / `os.killpg(SIGKILL)` (POSIX). Stdlib only.
- **Q:** Grace period before kill? **A:** 5s.
- **Q:** Mid-round resume in plan review? **A:** Yes — when per-batch round-N files exist and holistic round-N is missing, reuse the per-batch files (regardless of verdict) and only fire the holistic at round N. New helper, not in `discover_round`.
- **Q:** Same resume in code review? **A:** No — single-scope per call, no in-call resume gap.
- **Q:** ERROR-only-aggregate retry location? **A:** mill-plan SKILL.md, new step 4.5; backend stays stateless. Two-pass cap matches the validator gate.
- **Q:** Rate-limit detection? **A:** New `LLMRateLimitError(LLMError)` raised by `_llm_claude` when stream-json shows a rate-limit event + non-zero exit. Backend records `verdict: ERROR` and the orchestrator's ERROR-only retry handles it.
- **Q:** `ReviewError` CLI format? **A:** `ERROR: <msg>` prefix; for `[resolve_ref_paths]` messages append a one-line hint pointing at the new `Deletes:` mechanism.
- **Q:** Test coverage? **A:** Unit tests in-memory / `tempfile` for every helper change. Process-tree kill not TDD (integration-shaped); flagged as optional follow-up.
- **Q:** TDD-first candidates? **A:** `compute_deletes_union`, `resolve_ref_paths` with `deletes_union`, mid-round resume detection, stream-json rate-limit parser.
- **Q (round 1 review):** How does `_invoke` integrate rate-limit detection given that today it raises before `_parse_stream_json` runs? **A:** New sibling `_scan_rate_limit(stdout) -> bool` helper. `_invoke` parses defensively then scans; on non-zero exit + scan-true, raise `LLMRateLimitError` (precedence over `LLMSessionError`). `_parse_stream_json` signature unchanged.
- **Q (round 1 review):** How does the SKILL.md step 4.5 ERROR-only retry get JSON to inspect when `_review_plan.run` raises ReviewError on all-ERROR? **A:** Remove the total-fail check at lines 529–534 entirely. Fall-through path produces a valid JSON envelope (verdict `REQUEST_CHANGES`, reviews[] populated). Same change pattern applied to `_review_code.run` for consistency.
- **Q (round 1 review):** How does the validator avoid false-positives on `Deletes:` tokens? **A:** `_check_non_existent_path` accepts `deletes_union` and skips `Reads:`/`Modifies:` tokens that are in it. `Deletes:` tokens themselves require the path to be on-disk OR in `creates_union` at validation time.
