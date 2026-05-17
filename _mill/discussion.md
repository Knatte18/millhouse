# Discussion: 61 (A) — Review pipeline fixes

```yaml
task: 61 (A) — Review pipeline fixes
slug: mill-review-pipeline-fixes
status: discussing
parent: main
```

## Problem

Seven bugs were observed in the review subsystem (`_review_*.py`, `millpy-review-*.py`, `mill-go` SKILL.md) during recent autonomous runs:

- **#300** mill-go's holistic-review section has no handling branch for "EXIT non-zero and no JSON summary line"; the per-batch section has one but holistic was forgotten.
- **#306** `millpy-review-discussion.py` (when used from a sub-directory-hub layout) writes review files to `<git_root>/_mill/reviews/` instead of `<hub_path>/_mill/reviews/`. mill-start handles this consistently; review-discussion is inconsistent.
- **#308** The review bulker reads raw `.ipynb` files as UTF-8 text. Notebook cell-output (base64 images, DataFrame renders) dominates size — `new_avm_train.ipynb` is 1.6 MB on disk, only 19 KB is source. A plan-review prompt reached 1.73 M chars (~433 k tokens) and was rejected with API 413.
- **#315** `parse_verdict` already scans the full response for the first `` ```yaml `` fence (verified at [_review_common.py:984-1026](plugins/mill/scripts/_review_common.py#L984-L1026)) — the prose-preamble case is handled today. The remaining gap is the **error envelope** when `parse_verdict` raises `ReviewError`: the CLI exits 1 *without* a JSON envelope, breaking mill-go's step 3.5 ERROR-only-retry path. The historical failure (proposal observation) predates the current parse_verdict; the work for #315 is now backend-side only.
- **#316** Holistic code-review files are sometimes saved as `{ts}-holistic-review-r{N}.md` instead of the documented `{ts}-code-review-r{N}.md`. mill-go's holistic crash-recovery scan globs `*-code-review-r{H}.md`; the `-holistic-` prefix silently breaks resume. (Naming today depends on which code-path runs — verdict-parse-error vs. clean-exit emit different filenames.)
- **#317** Review-file timestamps in `_mill/reviews/` are written in **local time** while every other mill artefact (`_timestamp.now_utc_iso()`, `.scratch/bg-*` log filenames) uses **UTC**. Chronological sorting and cross-correlation with bg logs become unreliable. Example: holistic review ran at `17:43:56Z` UTC, was saved as `20260516-194958-…` (CEST).
- **#319** mill-go has no auto-fallback when the holistic reviewer is rate-limited on consecutive rounds. Step 3.5's ERROR-only retry re-runs the same reviewer, hits the same rate-limit, and halts — the operator must manually edit `.millhouse/config.local.yaml` to swap reviewer model and resume.

**Why now:** these bugs surface as silent corruption (#316, #317), pipeline halts (#300, #315, #319), or catastrophic prompt size (#308). Each is independently observed during autonomous runs and blocks `pipeline.autonomous_mode` from being reliable. Task 60 is upstream; this is the immediate next layer.

## Scope

**In:**
- `mill-go` SKILL.md — holistic-section EXIT-without-JSON branch (#300), holistic step 3.5 rate-limit fallback hook (#319).
- `_review_common.py` — `.ipynb`-aware reader for `bulk_files` / `bulk_files_with_diff` (#308); audit/affirm UTC timestamps in `write_review_file` (#317); extend `parse_verdict` test coverage (multiple yaml blocks, trailing prose) — no production code change for #315 part 1 (already handled).
- `_review_code.py`, `_review_discussion.py`, and `_review_plan.py` (parity verify only — already has the envelope at [_review_plan.py:607-617](plugins/mill/scripts/_review_plan.py#L607-L617)) — wrap `parse_verdict` failures into a JSON envelope so the CLI emits `verdict: "ERROR"` instead of bare exit-1 (#315 part 2). Ensure every save path routes through `write_review_file` and never bypasses it (#316). `_review_plan.py` is verified-only: confirm the existing catch covers all parse paths including the NEED_CONTEXT retry surfaces.
- `millpy-review-discussion.py` — resolve `project_root` / `mill_dir` via `_paths.resolve_active_hub`, identical to mill-start's convention (#306).
- `mill-config.yaml` template + hub-root `mill-config.yaml` — add `roles.code-review.holistic.fallback_reviewer` schema entry (default `null`), documented (#319).
- Unit tests covering: `.ipynb` reader (code-cell-only, markdown-cell-only, mixed, malformed); `parse_verdict` with prose preamble, trailing prose, multiple yaml blocks; UTC timestamp shape regression.

**Out:**
- Adding new review types or scopes.
- Re-architecting the reviewer registry / cluster mode.
- Discussion-review CLI semantics beyond the path-resolution fix.
- mill-go behaviour outside the per-batch / holistic review loops (Builder lock, batch DAG, finalize handoff).
- Touching `_llm_*.py` — rate-limit detection already lives there via `LLMRateLimitError`; the fallback is mill-go's responsibility.
- Reformatting / renaming review-output schema or the `[BLOCKING]` / `[NIT]` / `[GAP]` / `[NOTE]` severity vocabulary.
- Auto-installing a "kinder" reviewer model — the fallback list is operator-configured, not synthesised.

## Decisions

### per-bug-scope-grouping

- **Decision:** Group bugs into four batches keyed by file/module, not one batch per bug. Bugs touching the same file land in the same batch to minimise merge friction. Tests come in the matching batch with the production code.
- **Rationale:** `_review_common.py` (#308 + #317), `_review_code.py` + `_review_plan.py` + `parse_verdict` (#315 + #316), CLI (#306), and `mill-go` SKILL.md (#300 + #319) are largely independent. Each batch can be reviewed end-to-end including tests.
- **Rejected:** One batch per bug — too granular; many tiny commits with shared imports/helpers; review burden multiplies.

### parse_verdict-yaml-search-strategy

- **Decision:** No production-code change for `parse_verdict`. The current implementation at [_review_common.py:984-1026](plugins/mill/scripts/_review_common.py#L984-L1026) already scans the entire response for the first `` ```yaml `` fence — prose preamble is already accepted. Existing test `test-review-common.py:398-401` covers the preamble case. This decision now requires only **additional test coverage**: multiple yaml blocks (first wins), trailing prose after yaml, yaml fence with trailing whitespace.
- **Rationale:** Original proposal observation predates the current parse_verdict scan-from-top logic; the bug is already fixed. Adding tests prevents regression. No code rewrite needed.
- **Rejected:** Rewriting the scanner — would duplicate existing behaviour; risk of regression with no payoff.

### parse_verdict-error-envelope

- **Decision:** When `parse_verdict` raises `ReviewError`, the backend catches it inside the existing post-LLM block, writes the raw response to disk via `write_review_file` (still useful for operator inspection), and returns a `ReviewResult` with `verdict="ERROR"` (top-level) and `reviews=[{"scope": ..., "verdict": "ERROR", "file": <path>, "error": <str(exc)>}]`. CLI exits 0 (a structured ERROR is a normal envelope, not a crash). Targets:
  - **`_review_code.run`** — implement the catch (currently bare-raise at [_review_code.py:374](plugins/mill/scripts/_review_code.py#L374)).
  - **`_review_discussion.run`** — implement the catch (currently bare-raise at [_review_discussion.py:122](plugins/mill/scripts/_review_discussion.py#L122)).
  - **`_review_plan.run`** — verify-only; the catch already exists at [_review_plan.py:607-617](plugins/mill/scripts/_review_plan.py#L607-L617). Audit the NEED_CONTEXT retry path to confirm the catch covers it.
- **Rationale:** mill-go's step 3.5 ERROR-only retry path depends on a well-formed JSON envelope. Bare exit-1 with no JSON breaks the retry. Existing LLMError handling already does this for total-LLM-failure; parse failure deserves the same shape.
- **Rejected:** Re-raise to CLI and have CLI emit a synthetic envelope — duplicates logic; backend already owns the result-shape contract.

### ipynb-reader-strategy

- **Decision:** Add `_read_for_bulk(p: Path) -> str` to `_review_common.py`. For `.ipynb`: `json.loads(...)`, return `"\n\n".join(...)` of `cell.source` (joined if list-form) for cells with `cell_type in {"code", "markdown"}`. For everything else: existing `p.read_text(encoding="utf-8", errors="replace")` behaviour. Both `bulk_files` and `bulk_files_with_diff` route reads through this helper.
- **Rationale:** Matches proposal verbatim. The notebook source is what reviewers care about — cell outputs are bytes-on-disk noise. Code+markdown cells cover authored intent; raw cells are vanishingly rare in this codebase. Malformed JSON falls through to a `JSONDecodeError`, which is caught by the existing FileNotFoundError-equivalent skip path with a stderr warning (defensive).
- **Rejected:** (a) `jupyter nbconvert --to script` — external dependency; slow; fragile on Windows. (b) Generic size cap — discards too much; doesn't address the root cause (output cells, not source). (c) `nbformat` library — pulls a dependency for a 5-line parse.

### holistic-filename-enforcement

- **Decision:** Audit every code-path that writes a code-review file. Confirm each routes through `_review_common.write_review_file(..., scope=batch_name)` where `scope=None` (or `"holistic"`) produces the documented `{ts}-code-review-r{N}.md`. Add a regression unit test that calls `write_review_file` with `scope=None`, `scope="holistic"`, and `scope="some-batch"` and asserts the exact filename for each. If any direct `.write_text` of a review file exists outside `write_review_file`, route it through.
- **Rationale:** Today's bug is suspected to come from an error-recovery path (parse failure?) that names the file differently. Single naming gate prevents the regression from re-emerging.
- **Rejected:** Glob-and-rename retroactively — band-aid; the wrong filename is the symptom, not the cause.

### utc-timestamps-affirmation

- **Decision:** Confirm `write_review_file` uses `datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")`. Add a unit test that freezes the clock and asserts the filename's timestamp portion is UTC-derived. If any timestamp generation in the review pipeline still uses `datetime.now()` (naive) instead of `_timestamp.now_utc_compact()` or `now(timezone.utc)`, fix it.
- **Rationale:** `write_review_file` is already UTC; the proposal's observation may have been against an older revision. Affirm with a test so future drift is caught.
- **Rejected:** Skip the audit — risks repeat. The work is one grep + one test.

### review-discussion-path-resolution

- **Decision:** Rewrite `millpy-review-discussion.py`'s setup block to derive `mill_dir` from the hub path (`_paths.resolve_hub_path()` for cwd-as-hub, then `hub_path / ".millhouse"`) and `project_root` from `_paths.resolve_active_hub(container, slug, ...)`. Mirror mill-start's pattern exactly. The backend's `worktree_snapshot_guard(project_root, ...)` then operates on the hub, not git_root. `wiki_root` comes from `_paths.resolve_wiki_path(git_root)` (unchanged — the wiki is git-root-relative by definition).
- **Rationale:** `_review_common.resolve_path(...)` already resolves correctly via `_paths.resolve_active_hub`; the bug is that the CLI's `project_root = Path.cwd()` is shipped through to the backend for `worktree_snapshot_guard` and `read_constraints_md`. In a sub-dir-hub layout, cwd is the hub but `Path.cwd()` equals git_root when the operator runs from the worktree top. Aligning with mill-start removes the divergence.
- **Rejected:** Patch only `worktree_snapshot_guard`'s expected_paths — masks the root cause; future call sites repeat the bug.

### mill-go-holistic-exit-no-json-branch

- **Decision:** In `mill-go` SKILL.md `## Holistic code review` step 3 (after polling for `[mill-bg] EXIT`), add the same branch the per-batch section has at the end of its sub-step: "Only treat exit 1 as an unrecoverable pre-launch error when the JSON line in the log file is absent. If JSON is present with `stuck_type: transient`, route through *Stuck escalation*." (Holistic doesn't use the implementer's stuck flow, so the parallel phrasing for holistic is: "If exit is non-zero AND no JSON summary line is present, halt with the last stderr line. If exit is non-zero AND a JSON envelope is present with `verdict: ERROR`, drop through to step 3.5 ERROR-only retry as normal.")
- **Rationale:** mill-go must not crash on a partial-stderr CLI; the JSON envelope is the contract, and the doc was missing the absent-JSON branch for holistic.
- **Rejected:** Make CLI exit 0 on all paths — hides legitimate pre-launch failures (missing config, dead venv).

### mill-go-rate-limit-fallback

- **Decision:** Two-part fix:
  1. **Schema:** Add `roles.code-review.holistic.fallback_reviewer` (string or null, default `null`) and `roles.code-review.holistic.fallback_on:` (list-of-strings, default `["rate-limit"]`) to the template `mill-config.yaml` and mirror to the hub-root `mill-config.yaml`. The fallback applies only to the holistic scope (per-batch reviews don't hit the same cliff in practice).
  2. **mill-go step 3.5 (holistic):** After the two-pass ERROR-only retry exhausts: inspect `reviews[*].error` strings. If any contains `"rate-limit"` (case-insensitive) AND `fallback_reviewer is not None`: emit a one-line notify, mutate the in-memory config for the remainder of this holistic loop (don't write back to disk), and re-run step 3 with the override. If `pipeline.autonomous_mode: true` AND no fallback is configured AND the failure is rate-limit: still halt with `BLOCKED: holistic rate-limited, no fallback_reviewer configured` (operator visibility — silent infinite fallback is wrong). Operator interactive path stays as today.
- **Rationale:** Rate-limit is a transient, model-specific failure; falling back to a different reviewer is the established manual workaround. Config-driven and explicit so an operator can opt out by leaving `fallback_reviewer: null`.
- **Rejected:** Auto-pick "the next reviewer in the registry" — non-deterministic; surprises operators. Auto-bump model tier — implicit cost change; tier ordering isn't in config schema.

## Technical context

**Codebase layout.** Review subsystem lives at [plugins/mill/scripts/](plugins/mill/scripts/). Per CLAUDE.md `## Review terminology`:
- API (CLI): `millpy-review-discussion.py`, `millpy-review-plan.py`, `millpy-review-code.py`.
- Backend: `_review_common.py` (shared helpers), `_review_discussion.py`, `_review_plan.py`, `_review_code.py`.
- LLM providers: `_llm_claude.py`, `_llm_gemini.py`, `_llm_common.py` (incl. `LLMError`, `LLMRateLimitError`).
- Reviewer dispatch: `_reviewer_single.py`, `_reviewer_cluster.py`, `_reviewers.py`.

**Key helpers (used by this task):**
- `_review_common.parse_verdict(raw_output: str) -> str` — currently expects leading yaml block. Lines [954-1026 in _review_common.py](plugins/mill/scripts/_review_common.py#L954-L1026).
- `_review_common.write_review_file(reviews_dir, review_type, round_num, content, scope=None) -> Path` — central naming gate. [_review_common.py:1073-1106](plugins/mill/scripts/_review_common.py#L1073-L1106). Already UTC.
- `_review_common.bulk_files(file_paths)` / `bulk_files_with_diff(...)` — both call `p.read_text(...)`. [_review_common.py:691-757](plugins/mill/scripts/_review_common.py#L691-L757).
- `_review_common.resolve_path(path_tmpl, slug)` — uses `_paths.resolve_active_hub`. Already correct for sub-dir hubs. [_review_common.py:279-307](plugins/mill/scripts/_review_common.py#L279-L307).
- `_paths.resolve_hub_path()`, `_paths.resolve_active_hub(container, slug, *, cfg, git_root)`, `_paths.resolve_wiki_path(git_root)` — see CLAUDE.md `## Path invariants`.

**LLM rate-limit signal.** `_llm_claude.py` already detects rate-limits and raises `LLMRateLimitError`. `_review_*.py` catch it and emit `{"verdict": "ERROR", "error": "claude rate-limited (exit 1): …"}` in the result envelope. The fallback is consumed at the mill-go orchestrator layer, not the LLM layer.

**Filename schema.** `RE_SIMPLE` and `RE_BATCH` at [_review_common.py:74-85](plugins/mill/scripts/_review_common.py#L74-L85) define the canonical patterns:
- `RE_SIMPLE`: `^\d{8}-\d{6}-(discussion|code|plan)-review-r(\d+)\.md$`
- `RE_BATCH`: `^\d{8}-\d{6}-(plan|code)-review-([a-z0-9-]+)-r(\d+)\.md$`
A `-holistic-review-` prefix matches NEITHER regex, so crash-recovery `discover_round` / `detect_resume_round` ignore the file. That's the silent breakage path.

**Config schema.** Template at [plugins/mill/templates/mill-config.yaml](plugins/mill/templates/mill-config.yaml). Hub-root canonical schema at [mill-config.yaml](mill-config.yaml). Both must stay in sync — CLAUDE.md rule: "When changing a config key in `mill-config.yaml` at the hub repo root, mirror the change in `plugins/mill/templates/mill-config.yaml`."

**Test layout.** Unit tests at [plugins/mill/unit_tests/](plugins/mill/unit_tests/), one `test-<name>.py` per helper. Run via `python plugins/mill/unit_tests/run-all.py`. In-memory `tempfile` fixtures; no real git, no real LLM.

**Output encoding.** Per CLAUDE.md: all `print()` / `_log()` strings ASCII only (em-dash → `--`, arrow → `->`). Docstrings exempt.

## Constraints

- All paths in modified files must use ASCII-only output (em-dash → ` -- `, arrow → ` -> `). Windows cp1252 terminals crash on non-ASCII.
- Filename / regex changes must keep `RE_SIMPLE` and `RE_BATCH` as the authoritative shape — both `discover_round` and `detect_resume_round` rely on them.
- Config schema changes must update BOTH `plugins/mill/templates/mill-config.yaml` AND the hub-root `mill-config.yaml`.
- `.ipynb` reader must handle malformed JSON gracefully (log + skip, not crash) — review pipeline is high-blast-radius.
- No new external dependencies — stay within `pyyaml` + stdlib. The plugin venv is intentionally minimal.
- `mill-go` SKILL.md edits must preserve the documented step-numbering (3, 3.5, 4, 5, …) — operators and other skills reference them by number.

## Testing

**`.ipynb` reader (`_review_common._read_for_bulk`).**
- TDD candidate. Write `test-review-common-ipynb-reader.py`.
- Cases: code-cell-only notebook → source concatenated; markdown-cell-only → source concatenated; mixed code+markdown → both included; cell with `source` as string vs. list-of-strings — both forms produce the same output; raw cell present → skipped; malformed JSON → caller sees raised exception (or empty-string + warning per chosen contract); non-`.ipynb` extension → existing `p.read_text` path unchanged.
- Regression: full integration via `bulk_files([path-to-fixture.ipynb])` returns `--- FILE: … ---\n<sources>` shape.

**`parse_verdict` robustness (`_review_common.parse_verdict`).**
- TDD candidate. Extend `test-review-common-parse-verdict.py`.
- Cases: leading yaml block (existing) → APPROVE; prose preamble + yaml → APPROVE; multiple yaml blocks → first one wins; yaml block without `verdict:` key → ReviewError; invalid verdict value → ReviewError; trailing prose after yaml → still parses.

**Filename schema (`_review_common.write_review_file`).**
- TDD candidate. Add `test-review-common-write-review-file.py`.
- Cases: `(scope=None, review_type="code")` → `{ts}-code-review-r1.md`; `(scope="holistic", review_type="code")` → same; `(scope="01-foundation", review_type="code")` → `{ts}-code-review-01-foundation-r1.md`; same matrix for `"plan"`; `(scope=None, review_type="discussion")` → `{ts}-discussion-review-r1.md`.
- UTC regression: monkeypatch `_review_common.datetime` to a frozen UTC instant; assert the `ts` portion of the filename equals the expected `YYYYMMDD-HHMMSS` string. Naive `datetime.now()` would diverge.

**Backend ERROR envelope on parse failure.**
- Integration-style unit test. Mock `_reviewer_single.run` to return a string with NO yaml block. Assert `run(cfg, …)` returns `ReviewResult(verdict="ERROR", reviews=[{verdict: "ERROR", file: <existing-path>, error: <str>}])` and the CLI's `print(json.dumps(result.to_dict()))` produces a well-formed line.
- Repeat for `_review_plan.run` and `_review_discussion.run`.

**`millpy-review-discussion.py` path resolution.**
- Integration-style. Create a `tempfile` fixture with a sub-dir hub (`hub_relative_path: "hub"`); run the CLI with `Path.cwd() == git_root`; assert the written review file lands under `<git_root>/hub/_mill/reviews/` not `<git_root>/_mill/reviews/`.

**mill-go SKILL.md changes.**
- No automated test — SKILL.md is prose. Add a phrasing-parity check by grep: per-batch and holistic sections both contain `"exit 1"` AND `"JSON"` AND `"absent"` (or equivalent). Manual review confirms parity.

**Rate-limit fallback (mill-go step 3.5).**
- No automated test in this task. Smoke-verify via integration test (`integration_tests/`) only if a stub LLM provider can be wired. Out-of-scope for unit tests.

## Q&A log

- **Q:** Group all seven bugs into one task or split? **A:** [auto-pick] Single task. **Why:** tight coupling in the review subsystem; one PR; per-batch commits give the same granularity at review time.
- **Q:** For #300 (holistic exit-1 with no JSON) — add explicit handling branch or change CLI exit semantics? **A:** [auto-pick] Add explicit branch in `mill-go` SKILL.md mirroring the per-batch wording. **Why:** SKILL.md is the contract; CLI exit semantics are stable across reviewers.
- **Q:** For #306 — fix in CLI setup vs. patch worktree_snapshot_guard? **A:** [auto-pick] Fix in CLI setup; derive `mill_dir` and `project_root` via `_paths.resolve_hub_path` + `resolve_active_hub`, identical to mill-start. **Why:** root-cause; CLI is the consistent entry point for path conventions.
- **Q:** For #308 — `.ipynb`-aware reader vs. generic size cap? **A:** [auto-pick] `.ipynb`-aware reader per the proposal snippet. **Why:** addresses cause (cell-output), not symptom (size). Size cap discards too much real source.
- **Q:** For #315 part 1 — search anywhere for yaml block vs. preserve "must-be-leading" semantics? **A:** [auto-pick] Search anywhere; first yaml block wins. **Why:** reviewer prose preamble is benign; first-block-wins stays deterministic.
- **Q:** For #315 part 2 — emit JSON envelope on parse failure inside backend or CLI? **A:** [auto-pick] Inside backend (parallel to existing LLMError handling). **Why:** backend owns the result-shape contract.
- **Q:** For #316 — enforce single naming pattern via `write_review_file` audit, or add a glob-rename? **A:** [auto-pick] Audit + regression test. **Why:** single source of truth; rename is band-aid.
- **Q:** For #317 — full audit of all timestamp call sites or trust the central `write_review_file`? **A:** [auto-pick] Confirm `write_review_file` is UTC and add a frozen-clock unit test; grep for naive `datetime.now()` in `_review_*.py`. **Why:** cheap insurance; grep is one line.
- **Q:** For #319 — config-driven fallback reviewer or model-tier auto-bump? **A:** [auto-pick] Config-driven `fallback_reviewer` + `fallback_on` list. **Why:** explicit, deterministic, operator can opt out by leaving null.
- **Q:** For #319 — autonomous-mode behaviour when rate-limited and no fallback configured? **A:** [auto-pick] Halt with explicit `BLOCKED: holistic rate-limited, no fallback_reviewer configured`. **Why:** silent infinite fallback is wrong; operator needs visibility.
- **Q:** Test layout — group tests per bug or per helper? **A:** [auto-pick] Per helper file (`test-review-common-ipynb-reader.py`, etc.), matching the existing `test-<name>.py` convention. **Why:** matches project convention.
- **Q:** Batch decomposition — by bug or by file? **A:** [auto-pick] By file/module: (1) `_review_common.py` + tests (#308 + #315 part 1 + #317); (2) `_review_*.py` backends + tests (#315 part 2 + #316); (3) `millpy-review-discussion.py` (#306); (4) `mill-go` SKILL.md + config schema (#300 + #319). **Why:** minimises within-batch file overlap; each batch reviewable end-to-end.
- **Q:** Config schema mirror — do both files in the same batch? **A:** [auto-pick] Yes — template and hub-root `mill-config.yaml` go in the mill-go SKILL.md batch (#319). **Why:** CLAUDE.md mandates synchronicity; mirroring belongs with the consuming SKILL change.
