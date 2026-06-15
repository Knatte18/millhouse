# Discussion: Fix millpy-implement.py finalize to accept (or not require) --session-id/--start-sha

```yaml
task: Fix millpy-implement.py finalize to accept (or not require) --session-id/--start-sha
slug: implement-finalize-session-id
status: discussing
parent: main
```

## Problem

In agent-mode dispatch, `mill-go` SKILL.md tells the Builder to thread prepare-envelope
fields into the finalize call: "for fix and implementer CLIs, pass `--session-id <session_id>`
and `--start-sha <start_sha>`" (mill-go SKILL.md, Agent-mode dispatch, step 5, lines 127–129).
The Builder therefore runs, at the implement finalize point:

```
millpy-implement.py <batch> --stage finalize --agent-output <brief>.out.md --session-id <uuid>
```

But `millpy-implement.py`'s argparse declares only `batch_name`, `--stage`, and `--agent-output`.
argparse rejects the unknown flag and exits 2:

```
millpy-implement.py: error: unrecognized arguments: --session-id <uuid>
```

**Why now:** psmux/subprocess dispatch are not functional today — agent-mode dispatch is the
only live path. So this is not an edge case: it fires on **every** implement batch finalize on
the documented happy path. The bug has been reported ~13 times (#457, #459, #460, #461, #463,
#468, #472, #473, #474, #476, #477, #479, #481), all duplicates of the same root cause.

Note: `--start-sha` is **not** the failing flag in practice. mill-go threads `--start-sha` only
"when start_sha is not null in the envelope" (line 129), and `millpy-implement.py`'s prepare stage
omits `start_sha` from its envelope entirely (it calls `emit_prepare(...)` without `start_sha` at
`millpy-implement.py:262`, so the default `None` is used and the field is dropped per
`_implementer_common.emit_prepare` line 125). Therefore the only flag actually passed to implement
finalize — and the only one that triggers the error today — is `--session-id`.

## Scope

**In:**

- Add `--session-id` and `--start-sha` to `millpy-implement.py`'s argparse as **accepted-but-ignored**
  flags (CLI-shape parity with `millpy-fix.py`). The finalize stage continues to read the
  authoritative `start_sha` and `implementer_session` values from `status.md`, exactly as it does
  today; the new CLI args are accepted so the generic agent-dispatch loop stops erroring, but they
  do not change finalize behavior.
- A code comment on the two new arguments documenting that they exist for CLI-shape parity with
  `millpy-fix.py` and the generic dispatch loop, and that `status.md` remains the source of truth
  for implement's finalize.
- A unit test asserting that `millpy-implement.py <batch> --stage finalize --agent-output <f>
  --session-id <X> --start-sha <Y>` parses without error and that finalize still uses the
  `status.md` values (not the CLI args).

**Out:**

- No change to `millpy-fix.py` (already accepts and uses both flags).
- No change to `mill-go` SKILL.md line 129 — the documented dispatch instruction stays as-is; the
  fix is to make the implement CLI conform to it.
- No change to the prepare stage of `millpy-implement.py` — it continues to omit `start_sha` from
  its envelope and to persist `start_sha`/`implementer_session` in `status.md`. We are not making
  implement's finalize *use* the CLI args (rejected alternative — see Decisions).
- No refactor of the `session_id` mechanism. `session_id` is meaningful only in subprocess/psmux
  mode (where `_llm_claude` invokes the claude CLI with `--session-id`/`--resume`, see
  `_llm_claude.py` lines 144–148). Those modes are dead today, and agent-mode finalize only echoes
  the value into the inferred-success fallback envelope. The observation that `session_id` is
  vestigial under agent-mode dispatch is **noted but explicitly not acted on** in this task — it is
  not a live problem (agent mode simply ignores it) and warrants no follow-up issue.

## Decisions

### accept-but-ignore (vs. use-the-args vs. narrow-the-SKILL)

- Decision: Add `--session-id` and `--start-sha` to `millpy-implement.py` argparse as accepted
  flags that finalize ignores; finalize keeps reading `start_sha` and `implementer_session` from
  `status.md`.
- Rationale: `millpy-implement.py` persists both values in `status.md` at prepare time
  (`_status.set_batch_fields(..., {"state": "running", "start_sha": ..., "implementer_session": ...})`
  at `millpy-implement.py:202`) and reads them back at finalize (`millpy-implement.py:174,177`).
  `status.md` therefore cannot drift from what the SKILL would pass on the CLI — the values are
  identical (the SKILL got `session_id` from the same prepare envelope that wrote `status.md`).
  Reading from `status.md` is robust and unchanged; the new flags exist purely so the generic
  agent-dispatch loop (which uniformly passes them to both fix and implementer CLIs) does not error.
- Rejected — *use the CLI args (full fix.py parity)*: would require also making prepare emit
  `start_sha` in its envelope and switching finalize to prefer the CLI arg. More moving parts, more
  surface area, and zero behavioral benefit because the CLI value and the `status.md` value are
  identical. `status.md` persistence is strictly more robust than re-threading through the SKILL.
- Rejected — *narrow mill-go SKILL.md line 129 to exclude the implement CLI*: leaves fix and
  implement asymmetric and turns the dispatch instruction into a per-CLI conditional, which is
  fiddly and error-prone. Making the CLI conform to the uniform contract is cleaner.

### accept both flags, not just --session-id

- Decision: Accept both `--session-id` and `--start-sha`, even though only `--session-id` is passed
  to implement finalize today.
- Rationale: Matches `millpy-fix.py`'s CLI shape and the task title; harmless (both ignored); and
  future-proof if implement's prepare is ever changed to emit `start_sha`. Avoids a second
  rejection bug if the SKILL's "when start_sha is not null" condition ever becomes true for implement.
- Rejected — *accept only `--session-id`*: minimal but leaves a latent rejection bug and diverges
  from fix.py's shape for no benefit.

## Technical context

- `millpy-implement.py:67–85` — `main()` argparse block. The two new `parser.add_argument` calls go
  here, mirroring `millpy-fix.py:95–104` (`--start-sha`, `--session-id`, each `default=None`).
- `millpy-implement.py:164–184` — the `--stage finalize` branch. It reads `start_sha =
  batch_status.get("start_sha")` and `session_id = batch_status.get("implementer_session")` from
  `status.md` and passes them to `finalize_from_output(...)`. **This branch is not modified** —
  it keeps reading from `status.md`, ignoring `args.session_id`/`args.start_sha`.
- `millpy-fix.py:95–104` — reference for the exact argparse shape and help text to mirror.
- `millpy-fix.py:192–204` — fix's finalize branch, which *does* use `args.start_sha`/`args.session_id`.
  This is the deliberate asymmetry: fix threads via CLI, implement persists via `status.md`. Both
  end up echoing the same value into the inferred-success fallback, so the *effect* is identical.
- `_implementer_common.finalize_from_output` / `_forward_output` (`_implementer_common.py:169–318`)
  — `session_id` is used only in the inferred-success fallback envelope
  (`{"status":"success", ..., "session_id": session_id or "unknown", "inferred": True}` at lines
  289, 298, 309). In the normal path (sub-agent emitted parseable JSON, lines 238–252) `session_id`
  is unused. No change needed here.
- `_llm_claude.py:144–148` — where `session_id` is genuinely consumed (`--session-id`/`--resume` to
  the claude CLI), i.e. subprocess/psmux mode only. Confirms `session_id` plays no functional role
  in agent-mode finalize beyond the fallback echo.
- Existing tests: `plugins/mill/unit_tests/test-millpy-implement.py` (implement CLI behavior),
  `plugins/mill/unit_tests/test-fix-finalize.py` (the pattern to mirror — it drives
  `--stage finalize --start-sha ... --session-id ...` and asserts passthrough). Run the suite via
  `plugins/mill/unit_tests/run-all.py`.

## Constraints

- Python script style (project CLAUDE.md): `print()`/`_log()` output is ASCII only; the comment on
  the new args must avoid non-ASCII (`->`, em-dash) per the cp1252 stdout constraint — but since
  this is a code comment + help string, keep help text plain ASCII regardless.
- Operational mill calls use the cache (`${CLAUDE_PLUGIN_ROOT}`); tests are the only path that runs
  scripts from the source repo. The unit test must run via the repo test harness
  (`uv run --project plugins/mill` per project conventions), not the cache.
- The fix is a pure CLI-surface addition: no behavior change to the finalize path, so it cannot
  regress existing batch finalize semantics.

## Testing

- **TDD candidate — argparse acceptance:** Add a test (in `test-millpy-implement.py`, or a small new
  `test-implement-finalize.py` mirroring `test-fix-finalize.py`) that invokes the implement CLI with
  `--stage finalize --agent-output <tmp> --session-id <X> --start-sha <Y>` and asserts:
  1. argparse does not exit 2 (the flags are accepted).
  2. `finalize_from_output` is called with `start_sha`/`session_id` taken from `status.md`
     (the batch's `start_sha`/`implementer_session`), **not** from the CLI args `<X>`/`<Y>`. Use a
     `status.md` fixture whose batch values differ from the CLI args, and patch/inspect
     `finalize_from_output` (or `_forward_output`) to capture the kwargs — mirrors the
     `call_args[1].get("start_sha")` assertion style in `test-fix-finalize.py:159–172`.
- **Regression guard:** Confirm the existing implement finalize tests still pass unchanged (the
  finalize branch is untouched).
- No new integration test required — this is a CLI-surface change covered fully at the unit level.

## Q&A log

- **Q:** Which of the three fix options (accept-but-ignore / full fix.py parity / narrow the SKILL)? **A:** Accept-but-ignore: add the flags to implement argparse, finalize keeps reading from `status.md`. **Why:** `status.md` is the persisted source of truth and can't drift from the SKILL-passed value; minimal, robust, no behavior change.
- **Q:** Should this task also address the broader "session_id is vestigial under the Agent tool" concern? **A:** No — scope it out. **Why:** session_id/resume is consumed only in subprocess/psmux mode (`_llm_claude` `--session-id`/`--resume`), which is dead today; agent-mode finalize only echoes it into the inferred-success fallback, reading from `status.md` regardless, so accept-but-ignore loses nothing real.
- **Q:** What exactly produces the error? **A:** mill-go SKILL.md Agent-mode dispatch step 5 (lines 127–129) threads `--session-id` into the implement finalize call; implement's argparse doesn't declare it → exit 2. `--start-sha` is not threaded to implement (its prepare envelope omits `start_sha`), so `--session-id` is the sole failing flag.
- **Q:** Since agent mode is the only live dispatch path and psmux is dead, is this rare? **A:** No — it fires on every implement batch finalize on the happy path; that's why it was reported ~13 times.
- **Q:** File a follow-up for the vestigial-session_id observation? **A:** No, skip it. **Why:** it isn't a live problem (agent mode ignores it; the psmux path that would use it is dead) — one terse out-of-scope line in this file suffices.
- **Q:** Accept only `--session-id`, or both flags? **A:** Both. **Why:** parity with `millpy-fix.py` and the task title; harmless since both are ignored; avoids a latent second rejection bug if implement's prepare ever emits `start_sha`.
