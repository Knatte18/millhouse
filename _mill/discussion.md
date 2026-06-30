# Discussion: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode

```yaml
task: Fix mid-batch stop recovery and fixer false-success in agent-dispatch mode
slug: mill-agent-dispatch-gaps
status: discussing
parent: main
```

## Problem

Two reliability bugs surfaced during real `/mill-go` runs in **agent-dispatch mode** (`llm.claude.dispatch: agent`), both filed as GitHub issues:

- **#574 — implementer stops mid-batch and finalize falsely infers success.** A batch with 3 cards committed only Card 15, then the background implementer agent stopped with `status: completed`. The notification payload was a mid-work narration ("Card 15 committed and pushed. Now Card 16: move cli.go ... via git mv"), not the required `{"status":"success",...}` JSON line. The mill-go "Clean mid-work stop" path wrote `.out.md` and ran `--stage finalize`. Because Cards 16–17 were pure `git mv` moves, the one committed card's `verify:` passed — and finalize's completeness gate (`_batch_completeness_stuck`) is deliberately skipped whenever `verify_cmd` is present ("a passing verify is conclusive evidence of batch completeness"). So finalize emitted **inferred success on a 1/3-done batch.** The human orchestrator improvised a recovery — resume the same warm session via SendMessage to finish Cards 16–17 — which worked but is undocumented and not the happy path. A literal reading of the flow risks either false-success (as above) or a transient-retry-fresh that re-does the already-committed Card 15.

- **#575 — fixer self-reports success with no commit.** During a holistic fix round on the `haiku` fix role, the fixer applied source edits but **left them uncommitted** and returned `{"status":"success","commit_sha":"<X>",...}` where `commit_sha == start_sha` (the prepare-stage HEAD — i.e. no new commit was made). It also skipped a new test that a BLOCKING finding explicitly required. The finalize gate in `_forward_output` correctly caught the no-commit case (`stuck_type: logic`, "success reported but no content commit (HEAD == start_sha)"), so the safety net held — but the fixer **self-reporting success while having made no commit** wastes a fix round and produces a confusing report. The fixer briefs (`fixer-batch-brief.md`, `fixer-holistic-brief.md`) lack the pre-report self-check and the "commit_sha must be a real new commit" guard that the implementer brief already carries.

**Why now:** both bugs were hit in production agent-dispatch runs (2026-06-29) on real downstream repos. Agent-dispatch is the mode being stabilized, and these are the two open reliability gaps blocking confidence in unattended runs.

## Scope

**In:**

- Add a distinct **`stuck_type: incomplete`** classification, emitted by finalize on the **no-JSON inference paths** when the implementer made a partial batch (content-commit count `<` card count), **even when `verify:` passes**. This is the deterministic signal that a clean stop left the batch unfinished.
- Make the existing partial-batch detections emit `incomplete` consistently: `_reclassify_verify_failure`'s "0 < content < card_count" branch and `_batch_completeness_stuck` change their `stuck_type` from `transient` to `incomplete`. The `incomplete` dict carries `commits_made` and `session_id`.
- Run the commit-count completeness check on the **no-JSON inference paths regardless of `verify_cmd`** (a new helper or a `force` flag), because on those paths there is no success claim to trust and a passing verify does not prove completeness (a partial batch of `git mv` moves passes).
- Have `_forward_output` recognize an implementer-emitted `status: incomplete` JSON and normalize it to the stuck `incomplete` envelope (so a best-effort partial-progress report from the agent routes the same way as finalize-detected incompleteness).
- **mill-go SKILL routing:** document a first-class **warm-session resume** recovery for `stuck_type: incomplete` in agent mode — SendMessage the still-warm implementer agent to finish the remaining cards and emit the JSON report, then re-run finalize on the resumed output. In subprocess/psmux mode, `incomplete` routes to the existing `commits_made > 0` handling.
- Update the **implementer brief** with a best-effort instruction: when forced to stop before the batch is complete, emit `{"status":"incomplete","cards_done":N,"cards_remaining":M,"session_id":"<SESSION_ID>"}` as the partial-progress signal (finalize detection remains authoritative).
- Update **both fixer briefs** (`fixer-batch-brief.md`, `fixer-holistic-brief.md`) with: (a) a mandatory pre-report self-check that the current HEAD differs from the fix-round housekeeping commit before reporting success; (b) the "`commit_sha` MUST be a real new content commit distinct from the start commit; otherwise report `stuck`" guard mirroring the implementer brief; (c) a line requiring that when a finding mandates a NEW test, the fixer must add it and confirm it runs.
- Unit tests for the new `incomplete` classification and the `status: incomplete` parse normalization.

**Out:**

- **No change to the fixer default model** (`haiku`). #575 suggests haiku "is too weak," but model choice is a separate config decision; the brief fix plus the existing finalize safety net are sufficient. Bumping the default fixer model would raise cost for every fix and is out of scope.
- **No change to the explicit-success-JSON completeness gate** (line ~939 in `_forward_output`). When the implementer emits a real `status: success` JSON, trusting a passing verify stays the design — changing it would falsely flag legitimately-complete batches that used combined commits. Only the **no-JSON inference paths** get stricter detection.
- **No change to subprocess/psmux dispatch mechanics** beyond routing `incomplete` to the existing `commits_made > 0` path. The warm-session-resume recovery is agent-mode-specific.
- No new config keys, no change to `pipeline.autonomous_mode` semantics.
- Not attempting to fully solve "fixer skips a required new test that doesn't exist to fail verify" — the brief line is a mitigation, not a mechanical guarantee (a test that was never written cannot be detected by running verify).

## Decisions

### incomplete-stuck-type

- Decision: Introduce `stuck_type: incomplete` as a first-class classification distinct from `transient`, `verify`, and `logic`. It means: the batch is provably partial (fewer content commits than cards) on a path where no trustworthy success report exists, and the correct recovery is to **finish the remaining work in the existing session**, not retry from scratch and not accept it as done.
- Rationale: `transient` routes to "retry fresh" (which re-does committed cards) or "skip to cleanliness gate" (which accepts a partial batch as complete). Neither matches the actual situation. A dedicated type lets the orchestrator route deterministically to warm-session resume.
- Rejected: Reusing `transient` + `commits_made` (the issue's status quo) — ambiguous routing, conflates network blips with partial batches. Relying only on an implementer-emitted partial JSON (#574 suggestion 3) — unreliable, since the agent stops precisely because it ran out of budget to report.

### completeness-check-on-no-json-path-ignores-verify

- Decision: On the no-JSON inference paths, run the content-commit-vs-card-count check **even when `verify_cmd` is set**, and emit `incomplete` when `count < card_count`. Implement via a dedicated helper (e.g. `_incomplete_batch_stuck`) or a `force=True` flag on `_batch_completeness_stuck` that bypasses the `verify_cmd is not None → return None` short-circuit.
- Rationale: #574 proves a passing verify is **not** conclusive of completeness — a partial batch whose unfinished cards are file moves passes the committed card's tests. The "verify is conclusive" short-circuit is only safe on the explicit-success path where the agent affirmatively claimed completion.
- Rejected: Removing the `verify_cmd` short-circuit everywhere — would falsely flag legitimately-complete batches (combined commits) that emit a proper success JSON. Keep that short-circuit on the explicit-success path.

### false-positive-incomplete-is-safe

- Decision: Accept that the no-JSON `incomplete` detection can false-positive (a genuinely-complete batch that used combined commits AND lost its JSON to truncation will show `count < card_count`). The recovery — resume the warm session asking it to "finish any REMAINING cards, then emit the JSON" — is self-correcting: a complete batch's resumed session confirms completion and emits success in one cheap round.
- Rationale: Correctness dominates cost here. A false `incomplete` costs one short resume round; a false `success` (the #574 bug) ships an unfinished batch. The asymmetry favors over-detecting incompleteness.
- Rejected: Trying to perfectly distinguish truncated-but-complete from genuinely-incomplete from commit/tree state alone — impossible given combined commits are allowed, which is the root of the ambiguity.

### warm-session-resume-recovery

- Decision: In agent mode, `stuck_type: incomplete` routes to a documented **warm-session resume**: the orchestrator retains the Agent runtime ID returned when it dispatched the implementer, and on `incomplete` issues `SendMessage(<agent_id>, "Finish any remaining cards in this batch, run verify, then emit the required JSON report as your final line.")`, captures the resulting notification to `.out.md`, and re-runs `--stage finalize`. If the agent cannot be resumed (no retained ID, or the resume itself stops without JSON again), fall back to a fresh re-dispatch.
- Rationale: This is exactly the recovery the human orchestrator improvised in #574, and it worked. Making it first-class removes the improvisation. Resuming preserves the committed cards (no re-doing Card 15) and drives the session to a definitive JSON report.
- Rejected: Fresh re-dispatch as the primary path (re-does committed cards, risks a second completeness loop). Auto-accepting partial work via the cleanliness gate (ships an unfinished batch).

### fixer-brief-commit-guard

- Decision: Add to both fixer briefs a mandatory pre-report self-check — confirm `git -C <PROJECT_ROOT> rev-parse HEAD` differs from the fix-round housekeeping commit (whose message starts with `mill-go: fixing` or `mill-go: holistic fix`) before reporting success — plus the implementer brief's "`commit_sha` MUST be a real new content commit; otherwise report `stuck`" guard, and a requirement that a finding mandating a NEW test be satisfied by actually adding and running that test.
- Rationale: The implementer brief already carries this guard and the implementer side does not exhibit #575. Porting the same discipline to the fixer briefs prevents the false-success self-report at the source, upstream of the finalize safety net that currently has to catch it.
- Rejected: Relying solely on the finalize gate (works, but wastes a round and confuses the report). Bumping the fixer model off haiku (separate cost decision; out of scope).

## Technical context

Key files (all under `plugins/mill/`):

- **`scripts/_implementer_common.py`** — shared finalize logic for both `millpy-implement.py` and `millpy-fix.py`. The relevant functions:
  - `_content_commit_count(project_root, start_sha)` — counts content commits since `start_sha`, subtracting the `"mill-go: start batch"` housekeeping commit. Reuse for the new detection.
  - `_batch_completeness_stuck(...)` — currently returns `None` when `verify_cmd is not None`; emits `stuck_type: transient` when `count < card_count`. Change emitted type to `incomplete`; add a way to bypass the `verify_cmd` short-circuit on inference paths.
  - `_reclassify_verify_failure(...)` — its `0 < content < card_count` branch emits `transient`; change to `incomplete`.
  - `_forward_output(...)` — the central dispatcher. The explicit-success path is lines ~870–977 (leave its completeness gate as-is). The no-JSON inference paths are the three blocks at ~1051, ~1136, ~1219 (snapshot-present formatter-drift path, snapshot-present clean-tree path, no-snapshot path) — these emit `inferred success` and must first run the verify-ignoring completeness check and emit `incomplete` when partial. Also add `status: incomplete` recognition near the top of the `parsed is not None` block (alongside the `status == "success"` special-case).
  - `_extract_status_json(...)` — already returns any dict with a `status` key, so an implementer `{"status":"incomplete",...}` is parsed; `_forward_output` must branch on it.
- **`scripts/millpy-implement.py`** — finalize stage (lines ~246–276) threads `card_count` (counted via `^###\s+Card\s+\d+\s*:`), `verify_cmd`, `module_wide_verify_cmd`, `snapshot_path`, and `session_id` (from `implementer_session` in status.md). All inputs the new detection needs are already available; `session_id` flows into the `incomplete` dict for the SKILL to resume.
- **`scripts/millpy-fix.py`** — fixer dispatch; finalize stage (lines ~221–253). The housekeeping commit it makes before dispatch is `mill-go: fixing batch <name> round <N>` (batch) / `mill-go: holistic fix round <N>` (holistic); `start_sha` is captured as HEAD *after* that commit. No code change strictly required for #575 (the gate already catches it) — the fix is in the brief templates — but confirm the finalize `start_sha`/`HEAD` comparison stays intact.
- **`templates/implementer-brief.md`** — already has the "Pre-report self-check" and "commit_sha MUST be a real content commit" guards (lines ~87, ~98). Add the best-effort partial-progress `status: incomplete` instruction in the Report / Implementation-discipline section.
- **`templates/fixer-batch-brief.md`** and **`templates/fixer-holistic-brief.md`** — add the pre-report commit self-check, the real-commit guard, and the new-test requirement. Mirror the implementer brief's wording.
- **`skills/mill-go/SKILL.md`** — `## Agent-mode dispatch` (lines 105–147), specifically step 4 "Clean mid-work stop (implementer only)" (line 129) and the `### Stuck escalation` section (lines 400–416). Add the `incomplete` routing: agent mode → warm-session SendMessage resume; subprocess/psmux → existing `commits_made > 0` path. Document that the orchestrator must retain the Agent runtime ID at dispatch to enable resume.

Gotchas:

- The housekeeping-commit subtraction (`_content_commit_count`) and the Bug #557 `_is_only_start_batch_commit` guard already exist — reuse them; do not re-implement commit counting.
- `print()`/`_log()` output is ASCII-only (Windows cp1252). Keep new reason strings ASCII (`--`, `->`).
- Both `millpy-implement.py` and `millpy-fix.py` share `_forward_output`; the fixer does **not** pass `card_count`, so the new `incomplete` detection is a no-op for fixer finalize (card_count is None → gate disabled). That is correct — `incomplete` is an implementer concept.
- The mill-go autonomous-mode branch in Stuck escalation must also handle `incomplete` (auto-resume once, then block if still incomplete) for parity with interactive mode.

## Constraints

- `stuck_type: incomplete` must be additive — every existing routing (`transient`/`verify`/`logic`/`infrastructure`) keeps current behavior. No existing test for those types may change verdict.
- The explicit-`status: success` finalize path must be byte-for-byte unchanged in behavior (only the no-JSON inference paths gain the stricter check).
- Reason strings ASCII-only.
- Brief template edits must keep the existing `<TOKEN>` set intact (no new tokens that `_render.render` would leave unsubstituted); the commit self-check uses values the fixer can compute itself (`git rev-parse HEAD`, the housekeeping commit message prefix) — no new render token required.

## Testing

- **`_implementer_common` / finalize (unit, primary TDD target):** in `plugins/mill/unit_tests/`, extend the existing finalize/`test-millpy-implement.py`-style tests (in-memory / mocked `_subprocess_util.run`). Cover:
  - No-JSON inference path, `content_commit_count < card_count`, `verify_cmd` set and passing → emits `stuck_type: incomplete` with `commits_made` and `session_id` (the #574 regression).
  - No-JSON inference path, `content == card_count` (complete) → still emits inferred `success`.
  - Explicit `status: success` JSON, `verify` passing, `count < card_count` (combined commits) → stays `success` (no false `incomplete`).
  - `_reclassify_verify_failure` `0 < content < card_count` branch now returns `incomplete` (was `transient`); `content == 0` still `logic`; `content >= card_count` unchanged.
  - `_forward_output` given an implementer `{"status":"incomplete",...}` line → normalized to the `incomplete` stuck envelope.
  - Fixer finalize (`card_count=None`) → `incomplete` detection is inert (no regression to #575 path); `HEAD == start_sha` success still demoted to `logic`.
- **Brief templates:** prose, not unit-tested for content. A light assertion that the rendered fixer briefs contain the commit self-check phrase is acceptable but optional; do not over-test prose.
- **mill-go SKILL routing:** documentation change; verify by reading, not by automated test. Ensure the `incomplete` branch references the warm-resume recovery and the subprocess fallback.
- Follow `python-testing` conventions; verify commands must use the mandated `PYTHONPATH= ` prefix per CLAUDE.md.

## Q&A log

- **Q:** Which bugs does this task fix? **A:** [auto-pick] Both #574 (mid-batch false-success) and #575 (fixer false-success). **Why:** the task title and wiki brief explicitly name both; they share the agent-dispatch finalize/brief surface.
- **Q:** How should finalize detect an incomplete batch? **A:** [auto-pick] Add `stuck_type: incomplete`, emitted on the no-JSON inference path when content-commit-count < card_count, running the count even when verify passes. **Why:** #574 proves a passing verify is not conclusive of completeness; a dedicated type enables deterministic routing where `transient` cannot.
- **Q:** How should the orchestrator recover from `incomplete` in agent mode? **A:** [auto-pick] First-class warm-session resume — SendMessage the warm implementer agent to finish remaining cards and emit JSON, then re-finalize. **Why:** matches the recovery that worked in #574, preserves committed cards, avoids re-doing work and false-success.
- **Q:** Should the no-JSON completeness check override the "verify is conclusive" short-circuit only on inference paths, or everywhere? **A:** [auto-pick] Only on the no-JSON inference paths; leave the explicit-`status: success` path's verify-conclusive short-circuit unchanged. **Why:** the explicit-success path has a trustworthy completion claim; changing it would falsely flag legitimate combined-commit batches.
- **Q:** Is a false-positive `incomplete` (combined-commit + truncated-JSON but actually complete) acceptable? **A:** [auto-pick] Yes — the warm-resume is self-correcting and cheap; over-detecting incompleteness is far safer than shipping a partial batch. **Why:** correctness asymmetry favors over-detection.
- **Q:** Should the implementer brief emit a partial-progress JSON on forced stop? **A:** [auto-pick] Yes, as a best-effort `status: incomplete` signal that `_forward_output` normalizes, with finalize detection remaining authoritative. **Why:** cheap defense-in-depth; gives a deterministic route when the agent does have a moment to report, without relying on it.
- **Q:** How is `incomplete` routed in subprocess/psmux dispatch? **A:** [auto-pick] To the existing `commits_made > 0` handling (resume via `--resume` / skip-to-cleanliness); the warm-SendMessage recovery is agent-mode-specific. **Why:** keeps the change additive and avoids destabilizing subprocess mode, which is out of the issues' scope.
- **Q:** How to prevent the fixer false-success (#575)? **A:** [auto-pick] Add a pre-report HEAD-vs-housekeeping-commit self-check, the real-commit `commit_sha` guard, and a new-test-required line to both fixer briefs. **Why:** ports the implementer brief's working discipline upstream of the finalize safety net that currently has to catch it.
- **Q:** Should the fixer default model be bumped off haiku? **A:** [auto-pick] No — keep haiku; the brief fix plus the existing finalize gate suffice; model choice is a separate config decision. **Why:** bumping raises cost for every fix and is out of scope for these reliability fixes.
- **Q:** What is the primary test target? **A:** [auto-pick] Unit tests in `plugins/mill/unit_tests/` for the new `incomplete` classification and `status: incomplete` parse normalization, with mocked git; brief prose is not unit-tested. **Why:** the finalize classification is the behavioral core and is already covered by mocked-subprocess unit tests.
