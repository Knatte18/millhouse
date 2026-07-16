# Conflict Resolution Brief

Your sole job is to resolve git conflict markers in the listed files, stage each resolved file, and report success. Do NOT commit. Do NOT run `git merge --continue` — the SKILL does that after receiving `{"status":"success"}`.

## Task intent

These excerpts describe what THIS branch is trying to accomplish. When the merge introduces a parent-side change that conflicts with this branch's intent, the resolution preserves THIS branch's intent. In particular: if a file appears under a batch's `Deletes:` list and the merge introduces a modified version of that file from the parent, the resolution is to delete the file (your branch's intent overrides). Stage the deletion with `git -C /home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps rm <file>`.

### From discussion.md

# Discussion: Agent-mode dispatch: envelope fields and session/runtime state are unreliable

```yaml
task: Agent-mode dispatch: envelope fields and session/runtime state are unreliable
slug: mill-go-agent-dispatch-reliability-gaps
status: discussing
parent: hanf/linux-port-more
```

## Problem

`mill-go`'s Agent-mode dispatch path (`llm.claude.dispatch: agent` — the default in both shipped configs) has accumulated six distinct reliability gaps, each filed as a separate GitHub issue after being hit in real orchestrator runs. None of these are design-open questions — each issue already diagnoses the bug and proposes a fix direction. The task is to fix all six, choosing between the proposed directions where an issue names more than one.

The gaps split into three groups by symptom:

1. **`millpy-implement.py --stage prepare`'s envelope and state handling are wrong in three ways**: it never emits `start_sha` despite `mill-go/SKILL.md` documenting that it should (#635, #643 — duplicate reports); a re-run of `--stage prepare` for the same batch/round always mints a fresh `session_id`, desyncing `status.md` from a brief an already-dispatched agent may still be working against (#625); and a transient `git push` failure at the end of prepare aborts with exit 1 and **no envelope**, even though all durable state (status.md, commit) was already mutated (#626).
2. **Effort tier and the resulting audit trail are wrong under agent-mode dispatch**: a compound reviewer/implementer name like `sonnethigh` (model `sonnet` + effort `high`) resolves its `effort` field in the reviewer registry, but the prepare envelope never surfaces it and `mill-go/SKILL.md`'s Agent-mode dispatch pattern never extracts or forwards it to the Agent tool — which itself has no effort parameter (#628, #633 — duplicate reports). Downstream, the review file's `reviewer_model` field is stamped from the config-time reviewer name at prepare time (baked into the rendered prompt, which the reviewer echoes back), not from what was actually dispatched — so an operator who overrides the Agent-tool model mid-run gets an audit trail that lies about which model produced the review (#644).
3. **`resolve_dispatch_mode`'s hardcoded fallback is the wrong mode** — `"subprocess"` — while both the hub `mill-config.yaml` and the plugin template set `dispatch: agent` (#636).
4. **No signal distinguishes a stalled interactive permission prompt from a genuinely running background agent** — `TaskOutput` reports `running` in both cases, so a mid-run permission dialog looks identical to normal progress and the run appears to hang with no diagnostic (#631).

## Scope

**In:**
- `millpy-implement.py --stage prepare`: emit `start_sha` in the envelope; reuse (not regenerate) `session_id` on a re-run against an already-`running` batch; make the trailing `git push` non-fatal (warn + continue, still emit the envelope).
- `_agent_dispatch.py`: `resolve_dispatch_mode`'s fallback default changes from `"subprocess"` to `"agent"`.
- `_implementer_common.emit_prepare` (and the review-CLI prepare paths in `_review_code.py` / equivalent for discussion/plan review): add an `effort` field to the prepare envelope, sourced from the resolved reviewer/implementer spec's `effort` key, whenever non-null.
- `mill-go/SKILL.md`'s "## Agent-mode dispatch" section: document that step 2/3 extracts `effort` from the envelope but the Agent tool has no effort parameter to forward it to — an explicit, documented limitation rather than a silent gap. Separately, step 3 gains an instruction to record the `model` value actually passed to the Agent tool call (a local Builder variable, alongside the existing `agentId` recording), and step 6 gains an instruction to thread that recorded value into review-CLI finalize calls as `--actual-model <value>` — see the "reviewer_model / audit-trail accuracy" Decision below for why the envelope's `model` field alone isn't a sufficient source.
- `reviewer_model` in finalized review files: change to record what was actually dispatched (bare model tier, e.g. `"sonnet"`) rather than the config-time reviewer name (e.g. `"sonnethigh"`), so the audit trail never implies an effort tier was honored when it wasn't. (No implementer-side equivalent exists to fix — confirmed absent, see the same Decision below.)
- `~/.claude/settings.json` (global user settings, merged in by `mill-setup`'s Phase 4.8, extended for this purpose): add bare-tool-name entries to `permissions.allow` (`Bash`, `Read`, `Edit`, `Write`, `Grep`, `Glob`, `Skill` — the union of `mill-implementer.md`'s and `mill-reviewer.md`'s `tools:` frontmatter) so background agent-mode dispatches don't stall on an interactive approval prompt for routine operations — regardless of which repo mill-go is orchestrating.

**Out:**
- Adding a genuine "blocked on permission" liveness signal to `TaskOutput`/the notification contract — that's harness-internal, outside this repo.
- Any mechanism to actually apply an effort tier through the Agent tool — its `model` parameter is a fixed enum (`sonnet`/`opus`/`haiku`/`fable`) with no effort-encoding convention; this task documents the limitation, it does not work around it.
- Any behavior change to `subprocess`/`psmux` dispatch modes — effort tier already threads correctly there (via `_llm_claude`'s CLI argv building); this task touches only the agent-mode path and the effort-field addition to the envelope schema (additive, non-breaking for the other modes).
- The `--resume-incomplete` warm-`SendMessage` recovery path (step 6.5 of Agent-mode dispatch) — already handles session continuity correctly for that specific scenario; #625 is about a *different* re-entry point (a plain re-`--stage prepare` call, not the warm-resume path).

## Decisions

### start_sha in the implement-prepare envelope

- Decision: `millpy-implement.py`'s `--stage prepare` branch (currently calling `emit_prepare(briefs_dir, "implement", args.batch_name, 1, prompt_text, model_tier, session_id)` with no `start_sha`) passes `start_sha=start_sha` — `emit_prepare` already accepts and handles this kwarg (`_implementer_common.py:750-793`), the implement CLI's prepare call simply never passes it.
- Rationale: `mill-go/SKILL.md` already documents extracting `start_sha` "when the CLI emits it, e.g. fix and implementer CLIs" and threading it into `--stage finalize`'s `--start-sha` flag; the field is a one-line addition at the call site, no envelope schema change needed.
- Rejected: correcting `SKILL.md` to stop naming implementer as a `start_sha` carrier (the issue's alternative option) — rejected because `start_sha` is genuinely available at prepare time (captured a few lines earlier in the same function) and finalize's completeness recount benefits from the same envelope-sourced baseline fix/merge-in CLIs already provide.

### session_id reuse on prepare re-run

- Decision: the reuse guard applies **only when `args.stage == "prepare"`** — i.e. only inside the agent-mode re-`--stage prepare` entry point, not the shared `else` branch's `--stage full` path. Concretely: before minting a fresh `session_id`, if `args.stage == "prepare"`, check `_status.read_batches(status_path)` for this batch; if an entry exists with `state == "running"` and a non-null `implementer_session`, reuse that session_id **and read `start_sha` from that same existing batch entry** (mirroring exactly how the `--resume-incomplete` branch reads both fields at line 442/452), skip `capture_snapshot`, `set_batch_fields`, and the housekeeping commit, and re-render the brief with the reused session_id. This is required so the envelope's `start_sha` (added by the "start_sha in the implement-prepare envelope" decision below, emitted at the shared `--stage prepare` call site) carries the batch's original baseline rather than an unbound variable or a freshly-recaptured (wrong) HEAD. Only mint a fresh UUID, capture a new `start_sha` via `git rev-parse HEAD`, and take a new cleanliness snapshot when the batch has no `running` state yet (a genuine first dispatch) **or** when `args.stage == "full"`.
- Rationale: the desync happens because prepare is not idempotent — a second `--stage prepare` call (e.g. an accidental re-prepare while the first-dispatched agent is still mid-flight) always overwrites both `status.md` and the brief file with a new identity, but an already-running agent keeps working from the brief it already read into context and will report the *old* session_id in its final JSON, permanently mismatching the new one in `status.md`. The `--stage full` path is the subprocess/psmux dispatch's own entry point, and `mill-go/SKILL.md`'s existing subprocess transient-retry contract *depends on* a plain re-fire (`millpy-implement.py <batch_name>`, no flag) minting "a fresh batch start" — the guard must not touch that shared `else` branch's `--stage full` behavior, or it silently breaks the existing, documented subprocess retry semantics (a Scope-Out violation this task must not commit).
- Rejected: always re-rendering the brief to match a freshly-minted session_id (the issue's other proposed option) — doesn't fix the reported symptom, since an agent already mid-flight against the old brief content has no way to learn about the new session_id; the mismatch this issue reports would still occur. Rejected: gating the guard on batch state alone with no stage check (the original draft of this decision) — this would also fire during `--stage full`'s shared `else` branch, changing subprocess/psmux dispatch's existing fresh-start retry behavior, which Scope Out explicitly forbids.

### Non-fatal prepare-stage push

- Decision: wrap the `git push origin <branch>` call in the non-`--resume-incomplete` prepare/full branch (`millpy-implement.py` around line 524) so a non-zero return code prints a warning to stderr and continues to prompt/render/emit_prepare, rather than returning 1.
- Rationale: matches the issue's suggested fix; the push is non-essential for correctness since `mill-merge` pushes the full branch at task end regardless, and by the time push runs, `status.md`, the cleanliness snapshot, and the housekeeping commit are already durably committed locally — aborting here strands a fully-prepared batch for no benefit.
- Rejected: keeping the push fatal but still emitting the envelope on failure — would require `mill-go/SKILL.md`'s Agent-mode dispatch step 2 to learn a new "exit 1 with envelope present" contract it doesn't have today (today's rule is "only treat exit 1 as unrecoverable when the JSON line is absent" — applies to the full-stage stuck path, not prepare); non-fatal push avoids expanding that contract.

### resolve_dispatch_mode default

- Decision: change `_agent_dispatch.py:80`'s `claude_cfg.get("dispatch", "subprocess")` to `claude_cfg.get("dispatch", "agent")`.
- Rationale: both the hub `mill-config.yaml` (`llm.claude.dispatch: agent`, confirmed at `mill-config.yaml:10`) and the plugin template (`plugins/mill/templates/mill-config.yaml:106`) already set `agent`; the fallback should match the documented default path, not silently diverge from every shipped config.
- Rejected: making the key required (raise instead of default) — bigger behavior change than this task covers; any caller currently relying on the implicit default (even if unintentionally) would break outright rather than getting corrected behavior.

### Effort tier: envelope field + documented harness limitation

- Decision: add an `effort` field (sourced from the resolved spec's `effort` key, e.g. via `impl_spec.get("effort")` in `millpy-implement.py`, already computed but currently discarded at the prepare call site) to prepare envelopes across the implement, fix, and review CLIs, wherever the resolved spec has a non-null effort. Update `mill-go/SKILL.md`'s "## Agent-mode dispatch" step 2 to list `effort` among the extracted envelope fields, and step 3 to state explicitly that it cannot be forwarded to the Agent tool call (no effort parameter exists on that tool) — a documented limitation, not a silently dropped field.
- Rationale: the field is genuinely available (already resolved from the registry for other purposes) and is meaningful today for `subprocess`/`psmux` dispatch modes, which already pass an explicit effort flag; adding it to the envelope is additive and harmless for agent-mode, and turns an invisible gap into a documented one. Actually encoding effort through the Agent tool isn't possible — its `model` parameter is a fixed enum with no effort-encoding convention — so there's nothing further this task can implement on the dispatch side.
- Rejected: leaving the envelope/docs gap alone and fixing only the audit-trail issue (#644) — rejected because the task brief explicitly names #628/#633 (the envelope-drops-effort issues) as in-scope, not just #644.

### reviewer_model / audit-trail accuracy

- Decision: change the review-file's `reviewer_model` field to record the bare model tier the Agent tool call actually used (e.g. `"sonnet"`), not the config-time reviewer/implementer name it was resolved from (e.g. `"sonnethigh"`). `reviewer_model` is currently a value the *reviewer itself* writes into its own YAML block — it's a prompt token (`<REVIEWER_MODEL>` in `review-code-batch.md:53` / `review-code-holistic.md:51`, substituted from `reviewer_name` at `_review_code.py:362`) that lands in `raw_text`, which `finalize_scope`/`write_review_file` (`_review_common.py:1632-1693`) then writes to disk **verbatim** — finalize never independently computes or writes this field today. Adding an override therefore means finalize post-processing `raw_text` (e.g. a targeted regex rewrite of the `reviewer_model: <value>` line) *before* calling `write_review_file`, driven by a new optional flag on the finalize CLI invocation (e.g. `--actual-model <tier>`) that the orchestrator passes when reasoning-effort or an explicit override caused the dispatched model to diverge from the config-resolved name. When `--actual-model` is passed and the `reviewer_model:` line is present and well-formed in `raw_text`, rewrite it in place; when the line is missing or malformed (the reviewer omitted or garbled the echoed line), **inject** a correct `reviewer_model: <value>` line into the YAML block rather than silently no-op-ing, so a passed `--actual-model` is always authoritative in the output file regardless of what the reviewer echoed. Absent the `--actual-model` flag entirely, finalize leaves `raw_text` untouched (today's behavior — not a "config-derived fallback" finalize computes, since finalize never touches this field at all in the no-override case).
- Rationale: today's `reviewer_model` is baked into the rendered prompt at prepare time and simply echoed back by the reviewer in its own report — it reflects config intent, never dispatch reality. This is misleading in the specific case #644 reports (an operator-directed model override) and, combined with the effort-tier drop above, would otherwise make agent-mode audit trails claim an effort tier was honored when it silently wasn't. A second, non-operator-driven divergence source exists too: `_review_code.py:371`'s `maybe_switch_spec_for_large_prompt` can swap `spec`/`reviewer_name` for an oversized holistic prompt *after* `prompt_text` (and the baked-in `reviewer_model` token) was already rendered at line 368 — so the returned `model` (line 377, which becomes the envelope's `model` field) reflects the switched spec while the reviewer's own echoed `reviewer_model` still names the original.

`--actual-model`'s value comes from **the model tier `mill-go/SKILL.md` step 3 actually passes to the Agent tool call**, not from re-reading the envelope a second time — the envelope's `model` field alone provably cannot capture a manual operator override (that override happens *at* the step-3 Agent tool call, strictly after the envelope was already read), so deriving `--actual-model` from the envelope again would just reproduce the same blind spot #644 reports. Concretely: `mill-go/SKILL.md` step 3 ("Call Agent tool") already documents recording the `agentId` returned by the Agent tool call into a local Builder variable for the duration of the batch/round — step 3 gains a parallel instruction to also record the `model` value it actually passed to that same call (ordinarily just the envelope's `model` field, copied through unchanged; a different value only when the operator explicitly instructed an override for this dispatch). Step 6 ("Run finalize stage") then threads that recorded value into review-CLI finalize calls as `--actual-model <value>`, alongside the existing `--round` threading. This single recorded value covers both divergence sources: the normal case (envelope value, unchanged), the manual-override case (#644's actual scenario), and the auto-switch case (the envelope's `model` field already reflects the switched spec by the time step 3 reads it, so the recorded value is automatically the post-switch one).
- Rejected: stamping the actual model unconditionally from the envelope's `model` field with no orchestrator override channel — insufficient, because the envelope's `model` field is itself just the config-resolved tier (`_agent_dispatch.model_to_tier(prepare_result["model"])`); it never reflects a manual operator override at Agent-tool-call time, which is exactly the scenario #644 reports. An explicit override input is required to capture that case. Rejected (originally hedged, now resolved): a parallel fix for an "implementer-side `reviewer_model` equivalent" — confirmed **out of scope**. `finalize_from_output` (`_implementer_common.py:834+`) writes no model-related field at all; the only `"model"` keys anywhere in `_implementer_common.py` are in `emit_prepare`/`emit_prepare_no_dispatch` (lines 782, 823 — the prepare-side envelope, already covered by the `effort`-field decision above). There is no implementer-side audit-trail field to correct because none exists.

### Permission allowlist for background implementer/reviewer dispatch

- Decision: the allowlist is written to **`~/.claude/settings.json`** — the user's global Claude Code settings — not a per-repo `.claude/settings.json`. This repo's own `.claude/settings.json` is confirmed empty (`{}`) and, per this repo's `CLAUDE.md`, external repos mill-go orchestrates (e.g. the loomyard/Models repos named in the source GitHub issues) have no millhouse checkout at all — a rule written to *this* repo's `.claude/settings.json` would never be present when mill-go is running against one of those external repos, and #631 was in fact observed on exactly such an external-repo run. `~/.claude/settings.json` is global to the operator's machine and applies to every mill-go session regardless of which hub/repo is active, so it's the only surface that actually reaches the failure #631 reports. Mechanically: extend `mill-setup`'s existing Phase 4.8 (which already idempotently writes to `~/.claude/settings.json` — today only the `MILL_PYTHON` env key, per `plugins/mill/skills/mill-setup/SKILL.md:347-371`) to also **merge** (not overwrite) bare-tool-name entries into `permissions.allow`: `Bash`, `Read`, `Edit`, `Write`, `Grep`, `Glob`, `Skill` — the union of `mill-implementer.md`'s (`Read, Edit, Write, Bash, Grep, Glob, Skill`) and `mill-reviewer.md`'s (`Read, Grep, Glob, Write` — no `Bash` at all, confirmed from its `tools:` frontmatter, so the reviewer subagent structurally cannot hit a Bash approval prompt in the first place) `tools:` frontmatter. This is a **bare tool-name allowlist, not a Bash command-pattern list** — no scan or pattern derivation of any kind is needed, since the exact tool surface is already fully known and statically declared in these two files. A bare-tool `Bash` entry grants no *new* capability: `mill-implementer.md` already grants the `Bash` tool outright (full shell access, by design — it is "a full-capability sub-agent"), so pre-approving it in `permissions.allow` only removes a redundant interactive re-confirmation of a capability the operator already deliberately granted by choosing agent-mode dispatch; it does not widen what the subagent can do. This precedent already exists on this machine: `~/.claude/settings.json`'s current `permissions.allow` already contains bare `"Bash"`, `"Edit"`, `"Read"`, `"Write"` (confirmed) alongside a `deny` list scoping out specific dangerous git invocations (`git reset --hard`, `git push --force`, etc.) — the mill-owned merge follows that same established pattern rather than inventing a new, finer-grained one. Merge semantics matter because `~/.claude/settings.json` is a shared, hand-editable file the operator may already have customized — mill-setup must add its entries without clobbering the existing `allow`/`deny`/`additionalDirectories` content.
- Rationale: #631's failure mode is a *global*, cross-repo problem — the operator's Claude Code installation is what runs every mill-go session, whichever hub is checked out — so the fix belongs at the global-settings layer mill-setup already owns and idempotently maintains, not duplicated per-repo where it would silently fail to apply to the majority of orchestrated repos (any repo other than millhouse itself). A pre-approved allowlist is the only fix available within this repo's control; it removes the failure mode rather than working around its invisibility.
- Rejected: a per-repo `.claude/settings.json` (this repo's root, or "the equivalent plugin-shipped settings surface") — rejected because it does not reach external orchestrated repos, which is where #631 was actually observed; a millhouse-repo-scoped fix would only ever help mill-go runs against the millhouse repo itself. Rejected: adding a "blocked on permission" liveness signal to `TaskOutput`/notification handling — rejected as out of scope, since that contract is harness-internal (Claude Code CLI), not something `mill-go/SKILL.md` or the plugin scripts can add to. Rejected: documentation-only ("operator should stay attentive") — doesn't fix anything, just describes the failure mode `mill-go`'s whole agent-mode design point is to avoid (unattended background execution).

## Technical context

- `_agent_dispatch.py` (`plugins/mill/scripts/_agent_dispatch.py`): shared dispatch helpers. `resolve_dispatch_mode` (line 66-85) has the wrong default. `write_brief`/`output_path_for` are the shared brief-file helpers every prepare call routes through — no change needed there beyond what `emit_prepare` already threads.
- `_implementer_common.py` (`plugins/mill/scripts/_implementer_common.py`): `emit_prepare` (line 750-793) already supports `start_sha` and could be extended with an `effort` kwarg the same way. `finalize_from_output` (line 834+) is where an `--actual-model` override, if added, would need a new parameter threaded down to wherever `reviewer_model`/equivalent gets written.
- `millpy-implement.py` (`plugins/mill/scripts/millpy-implement.py`): the `--stage prepare` branch is at lines 574-586 — this is the single call site for the `start_sha` and `effort` envelope additions. The session_id-reuse logic belongs in the "Stages: prepare and full" block starting at line 419 (specifically the `else` branch at line 461, which currently always mints fresh state) — **but this `else` branch is shared by both `--stage prepare` and `--stage full`** (the subprocess/psmux entry point), so the reuse guard must itself check `args.stage == "prepare"` before consulting batch state, or it will change `--stage full`'s existing fresh-start retry behavior too (see the "session_id reuse on prepare re-run" Decision above). `impl_spec` (line 308) already has `.get("effort")` available at line 313 (`impl_effort`) but it's currently unused past the `_implementer_claude.run` call for `--stage full` — the prepare branch never sees it. The push call is at lines 524-530.
- `_review_code.py` (`plugins/mill/scripts/_review_code.py`): `prepare()` (line 194-381) resolves `spec` (line 336, includes `effort`) but only passes `spec.get("model")` through the returned dict (line 377) — `effort` is dropped here too, one layer up from `millpy-review-code.py`'s envelope construction (`plugins/mill/scripts/millpy-review-code.py:156-167`, which calls `_agent_dispatch.model_to_tier(prepare_result["model"])` for the `model` field with no `effort` counterpart). `reviewer_model` is baked into `prompt_kwargs` at line 362, sourced from `reviewer_name` (the config key, not a dispatch-time value) — this is the render-time injection point #644 traces back to. `finalize()` (line 513-590) has no model-related parameter at all today; adding an override flag means extending this signature and its caller in `millpy-review-code.py`'s `--stage finalize` branch (lines 172-202).
- Other review CLIs likely share the same `reviewer_model`/effort-drop pattern — check `_review_plan.py` and `_review_discussion.py` (referenced via `millpy-review-discussion.py`) for parallel `prepare()`/`finalize()` structure before assuming `_review_code.py` is the only site to fix; `_review_common.py` (1823 lines) is the shared backend template/dispatch/verdict-parsing layer named in this repo's `CLAUDE.md` review-terminology table and may hold shared logic worth centralizing the fix in, rather than duplicating across three `_review_*.py` files.
- `mill-go/SKILL.md`'s "## Agent-mode dispatch" section (`plugins/mill/skills/mill-go/SKILL.md:105-197`) is the single source of truth for the three-step dispatch pattern (resolve mode → prepare → Agent tool call) that steps 2-6.5 elaborate; both the `effort`-extraction addition and its documented can't-forward-it limitation belong in step 2/3's field lists (currently lines 111-121).
- This repo's own `.claude/settings.json` at the repo root is currently `{}` — confirmed empty, but per the "Permission allowlist" Decision above, that file is *not* the fix target; `~/.claude/settings.json` (this machine's copy already has non-empty `permissions.allow`/`deny` blocks, confirmed) is. `mill-setup`'s Phase 4.8 (`plugins/mill/skills/mill-setup/SKILL.md:347-371`) is the existing code that writes to `~/.claude/settings.json` today (only the `MILL_PYTHON` env key) — the merge-a-permission-allowlist logic extends that same phase.
- The `mill-implementer` and `mill-reviewer` subagent definitions (`plugins/mill/agents/mill-implementer.md`, `plugins/mill/agents/mill-reviewer.md`) declare `tools:` frontmatter (wholesale grants, e.g. implementer has `Bash` with no path/command scoping) — the permission-prompt gap in #631 is a *permission-mode* approval issue on top of these grants, not a missing tool grant; the fix is in settings-level allow rules, not the agent frontmatter.

## Constraints

No `CONSTRAINTS.md` exists at the hub root.

## Testing

- `test-millpy-implement.py` (existing): extend for the `--stage prepare` changes — assert `start_sha` appears in the envelope; assert a second `--stage prepare` call against a batch already `state: running` reuses the prior `implementer_session` rather than minting a new one; assert a simulated push failure (non-zero `git push` return) still reaches the envelope print with a warning on stderr, rather than returning 1.
- `test-implementer-common.py` (existing): extend `emit_prepare`'s test coverage for the new `effort` field (present when passed, omitted when `None`, matching the existing `start_sha`/`nits_only` optional-field pattern already tested there per `_implementer_common.py:788-791`).
- New or extended unit test for `_agent_dispatch.resolve_dispatch_mode`: assert the default (config with `llm.claude` present but `dispatch` key absent) resolves to `"agent"`, not `"subprocess"`. No dedicated `test-agent_dispatch.py` exists today — check whether dispatch-mode resolution is covered indirectly elsewhere (e.g. via `_llm_claude` tests) before deciding whether a new file is warranted or an existing one should gain a case.
- `test-review-prepare-envelope.py` (existing): natural home for asserting the `effort` field appears in review-CLI prepare envelopes when the resolved spec has one, and is absent when it doesn't — mirrors whatever pattern that file already uses for `model`/`session_id`.
- `test-review-finalize.py` / `test-review-cli.py` (existing): extend for the `reviewer_model` audit-trail fix — assert the review file records the bare-tier value passed via the new override flag when supplied, and falls back to today's config-derived value when it isn't.
- TDD candidates: the session_id-reuse guard (`#625`'s fix) and the `resolve_dispatch_mode` default (`#636`'s fix) are both small, pure-logic changes well suited to writing the test first — the expected before/after behavior is unambiguous from the issue reports.
- Permission allowlist (`#631`'s fix): the merge logic mill-setup's Phase 4.8 gains (reading, deep-merging, and writing back `~/.claude/settings.json`'s `permissions.allow` list without clobbering existing entries) *is* unit-testable — extend whatever test module covers Phase 4.8's existing `MILL_PYTHON`-write behavior with cases asserting: (a) a pre-existing custom `permissions.allow`/`deny`/`additionalDirectories` block survives the merge untouched; (b) the merged `allow` list contains exactly the bare tool names `Bash`, `Read`, `Edit`, `Write`, `Grep`, `Glob`, `Skill` (deduplicated against any the operator already had); (c) the merge is idempotent — running it twice produces the same result as running it once. Since the allowlist content is now a fixed, statically-known set of bare tool names (not a scanned or derived Bash command-pattern list), there is no separate "does the pattern list have gaps" verification step — the fixed set is exhaustively correct by construction (it's the literal union of the two subagent definitions' `tools:` frontmatter, itself covered by asserting against `mill-implementer.md`/`mill-reviewer.md`'s current content in the same test).
- No new test infrastructure needed — the five code fixes are unit-testable with the existing in-memory/tempfile fixture patterns (`plugins/mill/unit_tests/`, per this repo's `CLAUDE.md`); none require real git/LLM integration coverage beyond what's already exercised. The permission-allowlist fix is the one exception, verified as described above rather than by a unit test.

## Q&A log

- **Q:** How should the six bug clusters be organized into implementation batches? **A:** [auto-pick] Three batches by fix surface: implement-prepare reliability (#625/#626/#635/#643/#636), effort-tier/audit-trail (#628/#633/#644, including its SKILL.md doc edit), permission allowlist (#631). **Why:** groups changes touching the same call sites while keeping the settings.json-only work isolated for focused review.
- **Q:** `resolve_dispatch_mode`'s fallback default — change to `"agent"` or make the key required? **A:** [auto-pick] Change fallback to `"agent"`. **Why:** matches every shipped config; a required key is a bigger behavior change than this task covers.
- **Q:** How should prepare avoid desyncing `session_id` on a re-run against an already-`running` batch? **A:** [auto-pick] Reuse the existing session_id (guard on batch state), only mint fresh on a genuine first dispatch. **Why:** always-mint-fresh doesn't fix the reported symptom — an agent already mid-flight against the old brief still reports the old session_id regardless of how the brief is re-rendered.
- **Q:** How should a prepare-stage `git push` failure be handled? **A:** [auto-pick] Non-fatal — warn to stderr, still emit the envelope. **Why:** the issue's own suggested fix; avoids teaching the orchestrator a new "exit 1 with envelope" contract.
- **Q:** How should the effort-tier drop under agent-mode dispatch be handled, given the Agent tool has no effort parameter? **A:** [auto-pick] Add `effort` to the envelope (informational, already meaningful to subprocess/psmux) and document the can't-forward-it limitation explicitly in `mill-go/SKILL.md`; also fix the audit-trail (#644) so it never implies effort was honored. **Why:** both issues are named in-scope by the task brief; there's no way to actually apply effort through the Agent tool's fixed model enum.
- **Q:** How should the stalled-permission-prompt gap (#631) be addressed? **A:** [auto-pick] Ship a bare-tool-name permission allowlist for the implementer/reviewer subagents' expected tool surface. **Why:** the only actionable fix within this repo's control; a new liveness signal would require harness-internal changes this repo can't make.
- **Q:** [round 4 gap] How does the plan writer derive the exact Bash allowlist patterns, since no `fewer-permission-prompts`-named file exists anywhere in this repo or `~/.claude`? **A:** [auto-pick] Drop pattern derivation entirely — allowlist bare tool names (`Bash`, `Read`, `Edit`, `Write`, `Grep`, `Glob`, `Skill`) instead of fine-grained Bash command patterns, taken directly from the two subagent definitions' `tools:` frontmatter. **Why:** the tool surface is already fully known and static; a bare-tool `Bash` entry grants no new capability beyond what `mill-implementer.md` already grants outright, and this matches the precedent already present in this operator's own `~/.claude/settings.json` (bare `"Bash"`/`"Edit"`/`"Read"`/`"Write"` entries, not command-pattern rules).
- **Q:** [round 4 gap] `--actual-model`'s decision said it derives from "the prepare envelope's `model` field," but the same decision says that field never reflects a manual operator override — where does the value actually come from? **A:** [auto-pick] From the model tier `mill-go/SKILL.md` step 3 actually passes to the Agent tool call (recorded as a local Builder variable, same pattern as the existing `agentId` recording), threaded into finalize by a new step-6 instruction — not re-derived from the envelope a second time. **Why:** the envelope is read *before* an operator override could apply; only the value actually used in the step-3 tool call can capture that case.
- **Q:** [round 4 gap] Does `millpy-implement`'s finalize path have an implementer-side equivalent of `reviewer_model` that also needs fixing? **A:** [auto-pick] No — confirmed absent. `finalize_from_output` writes no model-related field; every `"model"` key in `_implementer_common.py` is prepare-side (`emit_prepare`/`emit_prepare_no_dispatch`), already covered by the `effort`-field decision. **Why:** resolving this now (rather than leaving it as a plan-time discovery) removes an open hedge from Scope In.
- **Q:** [round 1 gap] How does finalize override a `reviewer_model` value that is embedded in reviewer-authored `raw_text`, not computed by finalize itself? **A:** [auto-pick] Finalize post-processes `raw_text` (regex-rewrite of the `reviewer_model:` line) before `write_review_file`, driven by a new `--actual-model` finalize flag. **Why:** the field is a prompt-template token the reviewer echoes into its own output — finalize has no independent channel to it today; correcting the mechanism description avoids specifying an override that can't actually work against the real write path.
- **Q:** [round 1 gap] How many implementation batches are there — the Q&A summary said four but only three were enumerated? **A:** [auto-pick] Three. **Why:** the three enumerated groups (implement-prepare reliability, effort/audit-trail, permission allowlist) already cover all six issues; a fourth boundary was never actually defined, so the count was simply wrong.
- **Q:** [round 2 gap] Does the session_id-reuse guard also change `--stage full` (subprocess/psmux) behavior, since it shares the same `else` branch as `--stage prepare`? **A:** [auto-pick] No — the guard is gated on `args.stage == "prepare"` explicitly; `--stage full` keeps today's always-mint-fresh behavior untouched. **Why:** `mill-go/SKILL.md`'s existing subprocess transient-retry contract depends on a plain re-fire minting a genuinely fresh batch start; applying the reuse guard there would silently break that documented behavior, which Scope Out forbids.
- **Q:** [round 3 gap] What `start_sha` does the prepare envelope carry when the session_id-reuse path fires (no fresh `git rev-parse HEAD` is captured on that path)? **A:** [auto-pick] Read `start_sha` from the same existing batch entry the reused `session_id` came from (mirroring `--resume-incomplete`'s existing read), not a freshly-captured HEAD. **Why:** the reuse path's whole point is preserving the original baseline for an already-dispatched agent; a fresh HEAD capture here would silently corrupt that baseline the same way a fresh session_id would.
- **Q:** [round 3 gap] Which settings surface should the permission allowlist target — this repo's `.claude/settings.json` or the operator's global `~/.claude/settings.json`? **A:** [auto-pick] `~/.claude/settings.json`, merged in via `mill-setup`'s existing Phase 4.8. **Why:** a repo-scoped rule never applies when mill-go orchestrates an external repo with no millhouse checkout — exactly where #631 was observed; the global settings file is the only surface every mill-go session actually reads.


### From _mill/plan/00-overview.md


```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
slug: mill-go-agent-dispatch-reliability-gaps
approved: true
started: "20260716-135443"
parent: hanf/linux-port-more
root: ""
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-millpy-implement.py test-implementer-common.py test-millpy-fix.py test-review-prepare-envelope.py test-review-common.py test-review-finalize.py test-review-cli.py test-claude-settings.py
```

### From _mill/plan/01-implement-prepare-reliability.md


```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: implement-prepare-reliability
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-millpy-implement.py
depends-on: []
```



- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/02-effort-tier-implementer.md


```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: effort-tier-implementer
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py test-millpy-fix.py
depends-on: [1]
```



- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/03-effort-tier-review-cli.md


```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: effort-tier-review-cli
number: 3
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-prepare-envelope.py
depends-on: [2]
```



- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/unit_tests/test-review-prepare-envelope.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/04-reviewer-model-audit-trail-backend.md


```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: reviewer-model-audit-trail-backend
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
depends-on: [3]
```



- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/05-reviewer-model-audit-trail-cli.md


```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: reviewer-model-audit-trail-cli
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-finalize.py test-review-cli.py
depends-on: [4]
```



- **Edits:**
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/unit_tests/test-review-finalize.py`
  - `plugins/mill/unit_tests/test-review-cli.py`
- **Creates:** none
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none

### From _mill/plan/06-permission-allowlist.md


```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: permission-allowlist
number: 6
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-claude-settings.py
depends-on: []
```



- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_claude_settings.py`
  - `plugins/mill/unit_tests/test-claude-settings.py`
- **Deletes:** none
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none

## Conflicting files

- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-implementer-common.py`

## Instructions

For each file listed above:

1. Read the file and locate every conflict block (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Understand both sides of the conflict — what each branch intended.
3. Write a resolution that preserves the intent of both sides. When both sides modify **different, non-overlapping parts** of the same conflict region — for example, different columns of one table row, different keys of one object, or disjoint lines of a prose block — **combine both edits** into a single resolved structure. Do NOT pick one side wholesale just because the region overlaps syntactically; picking one side wholesale is correct only when the two changes are genuinely mutually exclusive (e.g. the same key is renamed to two different values). Worked example: if `ours` changes column A and `theirs` changes column B of the same table row, the resolution keeps both column changes in a single row — it does not discard either.
4. Run `git -C /home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps add <file>` to stage the resolved file.
5. For modify/delete (DU) conflicts: if Task intent above lists this file under a batch's `Deletes:`, run `git -C /home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps rm <file>` instead of editing; that stages the intentional deletion.
6. For UD conflicts — files this branch **modified** that the parent branch **deleted**: do not silently keep the modification. Instead:
   a. Run `git log --diff-filter=D --oneline MERGE_HEAD -- <file>` to find the deletion commit on the parent.
   b. Run `git show <deletion-commit>` to inspect context.
   c. If the deletion commit message mentions a replacement file (e.g. "replaced by", "moved to", "consolidated into"), or the commit also adds a file in the same directory with overlapping content: stage the deletion — `git -C /home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps rm <file>`.
   d. If detection is inconclusive: report `{"status":"stuck","stuck_type":"logic","reason":"modify/delete conflict on <file>: cannot determine if parent deletion is a replacement -- operator must decide"}` and halt. Do NOT silently keep the modification.

Never use `git checkout --ours` or `git checkout --theirs` — they silently discard one side of the conflict.

## Report

Your last output line MUST be a bare JSON object (no code fence, no backticks):

On success (nothing discarded):

{"status":"success"}

On success with discarded content — if you had to drop content from one side (e.g. two sides made mutually exclusive changes and only one could survive), list each dropped item:

{"status":"success","discarded":["<short description of what was dropped from which side>"]}

An empty or absent `discarded` field means nothing was lost. If anything was discarded, you MUST list it; an empty list when content was actually dropped is a protocol violation. The `mill-merge-in` frontend reads this field and surfaces any losses to the operator before continuing, rather than silently running `git merge --continue`.

If you cannot resolve one or more conflicts:

{"status":"stuck","stuck_type":"logic","reason":"<one-line description of what you could not resolve>"}

Anything other than this JSON object on the last line is a protocol violation; the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost. Do not wrap the JSON in a code fence; do not add commentary after it.

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob. Use `git -C /home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps` for any git commands; do not `cd`. Worktree cwd is `/home/knatte/Code/millhouse/wts/mill-go-agent-dispatch-reliability-gaps`.
