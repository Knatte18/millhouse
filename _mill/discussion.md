# Discussion: mill-setup/wiki/docs/build-env: misc small bugs, round 3

```yaml
task: mill-setup/wiki/docs/build-env: misc small bugs, round 3
slug: mill-setup-wiki-doc-misc-r3
status: discussing
parent: main
```

## Problem

Five small, mutually unrelated bugs surfaced during recent sessions, all outside the live-run
critical path. Each is already fully described and (mostly) diagnosed in its own closed GitHub
issue; none shares a root cause or touches an overlapping file with another. They're bundled into
one round-3 cleanup task rather than five separate tasks because each is a few-line diff.

## Scope

**In:**

- **#1113** — a wiki task's stored `title` field can contain a doubled apostrophe (`''` instead of
  `'`) when the title was synthesized (not copied verbatim from a single source issue) — e.g. by
  fold/triage tooling consolidating multiple GitHub issues into one task. Locate the call site that
  double-applies quote-escaping (or otherwise corrupts the apostrophe) and fix it there.
- **#1138** — the `handoff` skill (`plugins/mill/skills/handoff/SKILL.md`) tells the agent not to
  let a prior handoff document become a structural template, but doesn't sequence *when* the old
  file is read — so reading it before drafting makes it the template anyway. Reorder the skill's
  instructions: draft the new handoff first from the conversation and current state, without
  opening the old file; only afterward read the old file, as a fact-check pass that can carry
  forward still-true facts (never structure).
- **#1127** — `mill-setup` Phase 4.8 reconciles `permissions.allow` (via
  `_claude_settings.merge_permission_allowlist`) but not `permissions.deny`. A common operator
  `deny` rule, `Bash(rm -rf:*)`, is target-blind — it blocks `rm -rf` against a throwaway scratch
  dir exactly as hard as `rm -rf ~`, which trains people to route around it and protects nothing.
  Add a sibling reconciliation function to `_claude_settings.py`, called from the same Phase 4.8
  block, that retires target-blind `rm -rf` deny rules and replaces them with a stricter pair:
  system-tree prefixes (`/etc`, `/usr`, `/var`, `/boot` — prefix-matched with `:*`) and user-root
  exact matches (`~`, `$HOME`, `/home`, `/Users`, `/` — exact match only, so anything *below* those
  roots stays deletable).
- **#1111** — `golang-build/SKILL.md` requires `golangci-lint` and instructs stopping the build
  workflow if it can't be installed. In network-restricted sandboxes, `go install .../golangci-lint`
  fails because a transitive dependency host is unreachable — observed twice, both times worked
  around ad hoc with `goimports -w` + `go vet ./...` instead. Document that substitute as the
  official fallback in the skill's Tool Installation / Failure Handling sections.
- **#1112** — a pre-command guard hook that's supposed to enforce "read wiki data via
  `wiki._client`, not raw shell access to the `.wiki` junction" appears to key on the junction-name
  string appearing anywhere in the Bash command text, rather than on whether the command actually
  touches the junction outside the documented API. Confirmed false-positive on (a) a compliant
  `_client.get_task` call that merely passes the junction name as a literal path argument, and (b) a
  `gh issue create` call with zero wiki file access, whose body just quotes the junction name in
  prose. The hook's implementation location is not yet confirmed anywhere in this repo or in global
  Claude Code settings (see Technical context) — locating it is part of this task's scope, not a
  precondition for including it.

**Out:**

- No other golang-build changes beyond the sandbox-fallback documentation (no vendoring/caching of
  `golangci-lint`).
- No change to `permissions.ask` handling — #1127 stays in `permissions.deny` only (see Decisions).
- No broader audit of other wiki-task fields for similar escaping bugs — #1113 is scoped to `title`.
- No general rewrite of the guard-hook mechanism if found — only the substring-vs-actual-access
  scoping fix described in #1112.
- No live-run-path changes of any kind — all five items are explicitly outside that path per the
  brief.

## Decisions

### bundling

- Decision: fix all five bugs in this single task, one plan batch per bug (5 independent batches,
  no DAG dependencies between them).
- Rationale: zero file overlap between the five; brief already frames them as one "round 3" batch of
  small fixes; splitting into five tasks adds coordination overhead for no benefit.
- Rejected: separate task per bug (more overhead, no isolation benefit since batches are already
  independent within one task).

### 1113-investigation-in-plan

- Decision: the exact call site that double-escapes/corrupts the title is not located during
  discussion. `_yaml_writer.py`'s `quote_scalar` (used for `status.md`'s `task:` field) was checked
  and confirmed correct — not the bug site. mill-plan's batch for #1113 must include locating the
  actual synthesis/upsert call site (likely in fold/triage tooling — see Technical context) as part
  of implementation, then fix it there with a regression test.
- Rationale: the brief includes #1113 in this round; the issue's own repro is precise enough
  (inspect a synthesized, not-copied-verbatim title for a doubled apostrophe) to locate the bug
  during implementation without needing it pre-diagnosed here.
- Rejected: a defensive normalize-on-write in `_client.upsert_task` that doesn't find the real call
  site — risks masking the bug instead of fixing it, and doesn't explain the mechanism.

### 1112-investigation-in-plan

- Decision: the guard hook's implementation is not located during discussion (checked:
  `.claude/settings.json` is `{}`; `plugins/mill/.claude-plugin/plugin.json` has no `hooks` key;
  `~/.claude/settings.json` has no `hooks` key). mill-plan's batch for #1112 must include locating
  the hook (check other plugins' `hooks.json`/settings, any global Claude Code hook config outside
  this repo, or OS-level command interceptors) before it can apply the scoping fix. If the hook
  genuinely cannot be located within reasonable plan-time effort, the plan must document this batch
  as blocked/deferred with the investigation findings recorded — not silently dropped and not
  invented as a stub.
- Rationale: brief includes #1112 in this round with "location unconfirmed" already flagged as a
  known constraint, not an oversight to paper over.
- Rejected: dropping #1112 from this task now — loses the two concrete repro cases already captured
  in the issue.

### 1127-denylist-shape

- Decision: adopt the issue's proposed code shape as-is: `RETIRED_DENY` (retire target-blind
  `Bash(rm -rf:*)` / `Bash(rm -rf *)`), `DESTRUCTIVE_DENY` (system-tree prefixes + user-root exact
  matches, listed in the issue body), and `reconcile_destructive_denylist(settings_path: Path) ->
  dict`, added to `_claude_settings.py` next to the existing `merge_permission_allowlist`, called
  from mill-setup's Phase 4.8 block following the same idempotent read/change/write-only-if-changed
  pattern. No unit test file exists yet for `_claude_settings.py` — mill-plan's batch adds one.
- Rationale: the issue's proposal is already fully specified, reviewed-shaped, and follows the
  existing function's exact conventions in the same file.
- Rejected: using `permissions.ask` instead of `deny` — parks the session on an unanswerable prompt
  in background dispatch (the #631 failure mode `merge_permission_allowlist`'s own docstring already
  guards against), so `deny` is the only correct instrument here.

### 1138-handoff-reorder

- Decision: adopt the issue's proposed two-step reorder in `handoff/SKILL.md`: (1) draft the new
  handoff from the conversation and current state without opening the old file, (2) read the old
  file afterward only to fact-check — pick up still-true, still-open facts and slot them into the
  already-drafted structure, never let it change that structure.
- Rationale: the skill's current wording bans the *effect* (old file as template) but not the
  *cause* (reading it before drafting) — the issue's fix targets the cause directly.
- Rejected: none proposed; issue's fix is a direct instruction-ordering change with no real
  alternative shape.

### 1111-sandbox-fallback

- Decision: document the `goimports -w <changed-files>` + `go vet ./...` substitute as the official
  fallback in `golang-build/SKILL.md` when `golangci-lint` install fails specifically due to network
  restriction (transitient dependency host unreachable), in both the Tool Installation and Failure
  Handling sections.
- Rationale: this exact substitute was already used ad hoc twice in the same session and unblocked
  the task; documenting it costs nothing and closes the gap between documented and actual behavior.
- Rejected: vendoring/caching `golangci-lint` so `go install` never needs network — heavier
  (introduces a vendoring/update-maintenance burden) for a problem the doc fallback already solves
  at zero cost; the issue itself lists this as the fallback option, not the primary one.

## Technical context

- **#1113** — `plugins/mill/scripts/_yaml_writer.py`'s `quote_scalar()` (PyYAML-backed) is confirmed
  correct for `status.md`'s `task:` field escaping — not the bug site. The corrupted value lives in
  the wiki task's stored `title` field itself, read back verbatim via `wiki._client.get_task`.
  Candidate synthesis/upsert call sites to check: `plugins/mill/scripts/millpy-fold.py`,
  `plugins/mill/scripts/millpy-add.py`, `wiki._client.upsert_task`/`merge_tasks`, and whatever
  drives the `mill-triage-to-tasks`/`mill-ghissues-to-tasks`/`mill-report-to-tasks` skills' task
  upsert path — the task in question was created by consolidating ten duplicate GitHub issues, i.e.
  through a fold/triage flow, not `mill-add`'s single-source path.
- **#1138** — target file: `plugins/mill/skills/handoff/SKILL.md`. Note:
  `plugins/mill/skills/mill-go-base/handoff.md` is a **different, unrelated** "Handoff phase" (task
  completion handoff inside mill-go) — confirmed during exploration to share only the word
  "handoff"; do not touch it.
- **#1127** — `plugins/mill/scripts/_claude_settings.py` currently exports
  `MILL_SUBAGENT_TOOLS` and `merge_permission_allowlist(settings_path, tool_names)`. mill-setup's
  Phase 4.8 (`plugins/mill/skills/mill-setup/SKILL.md`, around line 428) already calls
  `_claude_settings.merge_permission_allowlist(settings_path, _claude_settings.MILL_SUBAGENT_TOOLS)`
  in the same block that writes `MILL_PYTHON`. The new `reconcile_destructive_denylist` call goes in
  that same block.
- **#1111** — `plugins/golang/skills/golang-build/SKILL.md`, "Tool Installation" section (current
  behavior: report missing-tool message and stop) and "Failure Handling" section.
- **#1112** — no hook implementing this guard was found in this repo's `.claude/settings.json`
  (currently `{}`), `plugins/mill/.claude-plugin/plugin.json` (no `hooks` key), or
  `~/.claude/settings.json` (no `hooks` key). mill-plan's investigation should also check other
  installed plugins' own hook configs and any Claude Code hook mechanism outside this repo's
  filesystem entirely (e.g. a hook registered against a different settings scope or a wrapper
  around the CLI itself).

## Testing

- **#1113**: once the call site is located, add a regression test (unit test if the fix lands in a
  `plugins/mill/scripts/*.py` helper with existing test coverage under `unit_tests/`) that
  synthesizes a title from an apostrophe-containing source string and asserts a single apostrophe
  survives.
- **#1127**: new unit test file for `_claude_settings.py` (none exists yet) covering
  `reconcile_destructive_denylist`: retires a present `Bash(rm -rf:*)` entry, adds the
  `DESTRUCTIVE_DENY` set, preserves unrelated existing `deny` entries, and is idempotent (second run
  is a no-op) — mirroring `merge_permission_allowlist`'s existing test conventions if a
  `test-claude-settings.py` pattern exists elsewhere for that function; if not, follow
  `unit_tests/test-*.py`'s in-memory/tempfile fixture convention (`plugins/mill/unit_tests/`, no
  real git/LLM).
- **#1138**: no automated test — prose/instruction-ordering change in a `SKILL.md`. Manual
  verification: confirm the reordered instructions read correctly and the "never a section template"
  rule is now structurally enforced (old file physically can't be open yet when drafting starts).
- **#1111**: no automated test — doc-only change in a `SKILL.md`. Manual verification: confirm the
  documented fallback matches what was already used ad hoc (`goimports -w` + `go vet ./...`).
- **#1112**: depends on investigation outcome. If the hook is located in-repo (Python/JSON), add a
  regression test covering both repro cases from the issue (a compliant `_client.get_task` call, and
  prose merely mentioning the junction name) passing cleanly. If the hook lives entirely outside
  this repo's filesystem, no automated test is possible from here — document the finding and the
  applied (or blocked) fix in the plan instead.

## Q&A log

- **Q:** Fix all 5 bugs in one task, or split them up? **A:** [auto-pick] Fix all 5 in this task. **Why:** brief already bundles them as one round-3 batch; zero shared files means no coordination cost either way, and splitting adds task overhead for no isolation benefit.
- **Q:** For #1113, is the exact double-escaping call site known, or does mill-plan need to investigate? **A:** [auto-pick] Plan includes a locate-and-fix investigation step, with a regression test using an apostrophe-containing source title. **Why:** `_yaml_writer.py` was checked and ruled out; the issue's repro is precise enough to locate the bug during implementation.
- **Q:** For #1112, is the guard hook's location known, or does mill-plan need to investigate? **A:** [auto-pick] Plan includes an investigation step; if genuinely unlocatable, document as blocked in the plan rather than dropping it. **Why:** the brief already flags "location unconfirmed" as a known constraint, and the issue's two repro cases are too concrete to discard.
- **Q:** For #1111, document a fallback vs. vendor/cache the linter binary? **A:** [auto-pick] Document the `goimports -w` + `go vet ./...` fallback, matching the issue's own suggestion. **Why:** already used ad hoc twice successfully; vendoring adds maintenance burden the doc fallback avoids.
- **Q:** For #1127, adopt the issue's proposed `RETIRED_DENY`/`DESTRUCTIVE_DENY`/`reconcile_destructive_denylist` shape as-is? **A:** [auto-pick] Yes, as proposed. **Why:** fully specified in the issue and matches `merge_permission_allowlist`'s existing conventions in the same file.
- **Q:** For #1138, adopt the issue's proposed draft-then-fact-check reorder in `handoff/SKILL.md`? **A:** [auto-pick] Yes, as proposed. **Why:** targets the actual cause (read-before-draft ordering) rather than restating the existing ban on the effect.
- **Q:** What's the testing approach across these five unrelated fixes? **A:** [auto-pick] Scoped unit tests for testable Python changes (#1127, #1113 once located), manual verification for skill/doc-only changes (#1138, #1111, and #1112 if it resolves to doc-only). **Why:** matches each bug's actual surface — no test framework applies to prose-only `SKILL.md` edits.
- **Q:** How should mill-plan structure the batches? **A:** [auto-pick] One batch per bug — 5 independent batches, no DAG dependencies. **Why:** zero file overlap between the five bugs; batching them together would only block independent work on each other for no reason.
