# Batch: phase-wait-foundation

```yaml
task: Blocking phase-wait gate for mill-plan/mill-go chaining
batch: phase-wait-foundation
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-phase-wait.py
depends-on: []
```

## Batch Scope

Introduces the shared, unit-tested building blocks the next two batches
wire into mill-go's and mill-plan's entry-gates: a new `_phase_wait.py`
helper module (pure string-building, no I/O), its unit test, and the two
new `pipeline.*` config keys that gate and size the feature. Nothing in
this batch touches either SKILL.md — the helper and config keys are
inert until batches 2/3 reference them. This is one batch because all
three cards are small, mechanically independent edits to the same
"new capability's foundation" surface, sharing no card-to-card ordering
dependency beyond "helper exists before its test imports it."

## Cards

### Card 1: Add `_phase_wait.py` shared helper

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_yaml_writer.py`
  - `plugins/mill/scripts/_builder_lock.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_phase_wait.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Create `plugins/mill/scripts/_phase_wait.py` as a flat, dependency-light
  helper module (style/layout reference: `plugins/mill/scripts/_builder_lock.py`
  — `from __future__ import annotations`, stdlib-only imports, full type
  hints, module-level docstring). It exposes exactly two pure functions,
  `build_wait_command` and `matches_wait_trigger`. Neither function performs
  any file I/O, network access, or subprocess call — both only build and
  return values from their arguments.

  **`build_wait_command(status_path: Path, ready_phase: str, poll_interval_s: int, giveup_s: int) -> str`**

  Returns a bash script (as a single string, safe to pass verbatim as the
  `command` argument to the harness `Monitor` tool) that polls
  `status_path`'s `phase:` line until it equals `ready_phase`, detects the
  terminal `blocked` phase and fails fast with the reason, or gives up
  after `giveup_s` seconds. The returned string's shape, substituting the
  four arguments, must be exactly:

  ```bash
  elapsed=0
  while true; do
    if tr -d '\r' < "<status_path>" | grep -q "^phase: <ready_phase>$"; then
      echo "READY"
      exit 0
    fi
    if tr -d '\r' < "<status_path>" | grep -q "^phase: blocked$"; then
      reason_line=$(tr -d '\r' < "<status_path>" | grep "^blocked_reason:" | head -1)
      reason=${reason_line#blocked_reason: }
      reason=${reason#\'}
      reason=${reason%\'}
      echo "BLOCKED: ${reason}"
      exit 1
    fi
    if [ "$elapsed" -ge <giveup_s> ]; then
      echo "TIMEOUT after ${elapsed}s waiting for phase: <ready_phase>"
      exit 2
    fi
    sleep <poll_interval_s>
    elapsed=$((elapsed + <poll_interval_s>))
  done
  ```

  Exact requirements on this shape:
  - `<ready_phase>` is substituted verbatim (no quoting/escaping applied to
    it — it is always one of the two literal single-word values
    `planned` / `discussed` in this codebase, never attacker- or
    user-supplied).
  - `<status_path>` is substituted as `str(status_path)` and appears
    wrapped in double quotes exactly as shown, in all three places it is
    used (each `tr -d '\r' < "<status_path>"` redirect) — this is what
    keeps a status path containing spaces safe.
  - Every read of `<status_path>` is piped through `tr -d '\r'` before
    `grep` ever sees it, exactly as shown (`tr -d '\r' < "<status_path>" |
    grep ...`), never a bare `grep ... "<status_path>"`. `_status.py`
    (`update_field`/`append_phase`/`set_blocked`) writes `status.md` via
    `Path.write_text` with no `newline=` override, so on a Windows-authored
    file the platform-default newline translation leaves CRLF line
    endings; GNU/POSIX `grep`'s trailing `$` anchor does not match
    immediately before a `\r`, so an un-piped `grep -q "^phase: ...$"`
    would silently never see `READY`/`blocked` on such a file and the wait
    would always run out the full `giveup_s` clock. Stripping `\r` first
    makes the trailing-`$` anchor safe regardless of which platform wrote
    `status.md`. This is a localized fix inside `_phase_wait.py` only —
    `_status.py`'s own writers are unchanged and out of scope for this
    task.
  - Both `grep -q "^phase: ..."` patterns (the `ready_phase` check and the
    `blocked` check) are anchored with a trailing `$` exactly as shown —
    this is deliberate defensive future-proofing against a hypothetical
    future phase value that string-prefix-extends an existing target
    (e.g. a future `planned-v2` falsely matching `grep "^phase: planned"`
    without the trailing anchor), now combined with the CRLF-stripping
    pipe above so the anchor is reliable on any platform's line endings.
  - The `blocked_reason` extraction uses only `grep`, `head`, and bash
    parameter expansion (`${var#prefix}` / `${var%suffix}`) — never `sed`
    (CLAUDE.md project rule). It strips the literal `blocked_reason: `
    key-label prefix first, then strips one optional leading and one
    optional trailing single-quote character (`_yaml_writer.quote_scalar`,
    which every `blocked_reason` value passes through when written by
    `_status.py`'s `set_blocked`, wraps escaping-needed values in single
    quotes via `yaml.safe_dump`). This is a deliberate partial unescape
    sufficient for a human-facing halt message only; it does not handle a
    doubled-single-quote escape sequence for a reason string that itself
    contains a literal `'` — not worth the complexity for a display string
    a human reads once.
  - `<giveup_s>` and `<poll_interval_s>` are substituted as plain integers
    (via `str(int)` / an f-string — no unit suffix, no conversion applied
    inside this function). This function never reads or knows about
    `pipeline.entry_wait_timeout_minutes` — the minutes-to-seconds
    conversion is the caller's job (see the overview's "unit conversion"
    Shared Decision).
  - Exactly one of the three `echo` lines (`READY`, `BLOCKED: ...`,
    `TIMEOUT after ...`) is ever printed by a single run of the returned
    script, with three distinct exit codes: `0` for `READY`, `1` for
    `BLOCKED`, `2` for `TIMEOUT`.
  - All `echo`'d literal text is ASCII-only (CLAUDE.md convention).

  **`matches_wait_trigger(phase: str, exact: set[str], regex_patterns: list[str]) -> bool`**

  Returns `True` if `phase` is a member of `exact`, or if `phase`
  full-matches (via `re.fullmatch`, not `str.startswith`) any pattern in
  `regex_patterns`; `False` otherwise. The parameter is named
  `regex_patterns`, not `prefix_patterns` — the values it holds in this
  codebase's actual usage (`^plan-review-r\d+$`, `^plan-fix-r\d+$`) are
  fully-anchored full-match regexes, not string prefixes, and the name
  must not mislead a future reader into reaching for
  `str.startswith()`.

- **Commit:** `feat(mill): add _phase_wait shared helper (build_wait_command, matches_wait_trigger)`

### Card 2: Add unit test for `_phase_wait.py`

- **Context:**
  - `plugins/mill/unit_tests/test-builder-lock.py`
  - `plugins/mill/scripts/_phase_wait.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-phase-wait.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Create `plugins/mill/unit_tests/test-phase-wait.py` following the exact
  structure of `plugins/mill/unit_tests/test-builder-lock.py` (module
  docstring, `from __future__ import annotations`, the same `HUB`-constant
  `sys.path.insert` boilerplate (`HUB = Path(__file__).resolve().parent.parent.parent.parent`,
  then `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`), a `main() ->
  int` function using bare `assert` plus `print("PASS: ...")` /
  `print(f"FAIL: {exc}", file=sys.stderr)` on `AssertionError`, `if
  __name__ == "__main__": sys.exit(main())`). No pytest, no git/LLM
  fixtures. Test cases 1-12 below are pure in-memory/string assertions
  with no filesystem I/O beyond constructing a `Path` object purely for
  string interpolation (`build_wait_command`/`matches_wait_trigger`
  themselves never read the path from disk). Case 13 is the one
  exception: it writes a real temp file and runs the generated command
  via `subprocess.run` (with a bounded `timeout=10`) to prove the CRLF fix
  end-to-end — import `subprocess` and `tempfile` for that case alone.

  Import `build_wait_command` and `matches_wait_trigger` from
  `_phase_wait`. Cover, at minimum, each of the following as a distinct
  assertion with its own `PASS:` print:

  1. `build_wait_command(Path("/tmp/status.md"), "planned", 10, 7200)`
     contains the substring
     `tr -d '\r' < "/tmp/status.md" | grep -q "^phase: planned$"`.
  2. The same call's returned string contains the substring
     `tr -d '\r' < "/tmp/status.md" | grep -q "^phase: blocked$"`, and
     contains no bare (un-piped-through-`tr`) `grep ... "/tmp/status.md"`
     invocation anywhere — every `grep` reading `status_path` content is
     preceded by a `tr -d '\r' < "<status_path>" |` pipe (confirming the
     CRLF-safety fix from card 1's Requirements is actually present, not
     just the plain unpiped anchors).
  3. The same call's returned string contains the substring
     `if [ "$elapsed" -ge 7200 ]; then`.
  4. The same call's returned string contains the substring
     `sleep 10` and the substring `elapsed=$((elapsed + 10))`.
  5. The returned string contains exactly one occurrence each of
     `echo "READY"`, `echo "BLOCKED: ${reason}"` (or the equivalent
     literal produced by the implementation — assert the substring
     `BLOCKED: ` appears immediately before a use of the extracted
     `reason` variable), and a `TIMEOUT after` echo; and contains
     `exit 0`, `exit 1`, `exit 2` each exactly once.
  6. Calling `build_wait_command` with a status path containing a space
     (e.g. `Path("/tmp/my status/status.md")`) produces a string in which
     every occurrence of that path is wrapped in double quotes (assert
     `'"/tmp/my status/status.md"'` appears in the output; assert the bare
     unquoted path does not appear standalone outside those quotes).
  7. Both `grep` patterns in the output end with `$"` immediately before
     the closing quote (confirming the trailing anchor from card 1's
     Requirements is present) — e.g. assert
     `'grep -q "^phase: planned$"'` and `'grep -q "^phase: blocked$"'`
     both appear verbatim.
  8. `matches_wait_trigger("discussed", {"discussed", "discussing",
     "planning"}, [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"])` is `True`.
  9. `matches_wait_trigger("plan-review-r1", {"discussed", "discussing",
     "planning"}, [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"])` is `True`,
     and so is `matches_wait_trigger("plan-fix-r12", ...)` with the same
     exact/regex sets.
  10. `matches_wait_trigger("planned", {"discussed", "discussing",
      "planning"}, [r"^plan-review-r\d+$", r"^plan-fix-r\d+$"])` is
      `False`, and so is `matches_wait_trigger("implementing", ...)` with
      the same sets.
  11. `matches_wait_trigger("discussing", {"discussing"}, [])` is `True`.
  12. `matches_wait_trigger("planned", {"discussing"}, [])` is `False`,
      and so is `matches_wait_trigger("discussion-fix-r1", {"discussing"},
      [])` — this confirms mill-plan's narrower trigger set (no regex
      widening) does not accidentally match mill-start's mid-loop phase
      value.
  13. **CRLF end-to-end execution test (regression for the Windows
      grep-anchor bug caught in plan review round 1).** Using
      `tempfile.TemporaryDirectory()`, write a real file with
      `open(path, "wb").write(b"phase: planned\r\n")` (raw bytes, bypassing
      Python's own newline translation, so the on-disk file is
      byte-for-byte CRLF-terminated regardless of the host platform). Call
      `build_wait_command(Path(path), "planned", 1, 5)`, then run the
      returned string via `subprocess.run(["bash", "-c", cmd],
      capture_output=True, text=True, timeout=10)` wrapped in a
      `try`/`except FileNotFoundError` — this is the first test file in
      `plugins/mill/unit_tests/` to shell out to a `bash` binary (every
      existing file, e.g. `test-builder-lock.py`, is pure in-memory
      Python with no subprocess dependency), so a machine with no `bash`
      on `PATH` must produce a clean `print("SKIP: bash not found on
      PATH, cannot exercise CRLF end-to-end case")` and continue past
      this case, not an uncaught exception that aborts the whole file
      before its final `PASS`/`FAIL` summary — matching the rest of the
      suite's uniform assertion-based failure contract. When `bash` IS
      found, assert the process exits with code `0` and its stdout,
      stripped, equals exactly `"READY"`. This proves the `tr -d '\r'`
      pipe actually makes the trailing-`$` anchor match a CRLF-terminated
      line end-to-end, not just that the generated string contains the
      right substrings.

  Print a final `"All _phase_wait unit tests passed."` line and return 0
  on success, mirroring `test-builder-lock.py`'s ending.

- **Commit:** `test(mill): add unit tests for _phase_wait.build_wait_command and matches_wait_trigger`

### Card 3: Add `pipeline.entry_wait` / `pipeline.entry_wait_timeout_minutes` config keys

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/mill-config.yaml`
  - `mill-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  In `plugins/mill/templates/mill-config.yaml`, inside the existing
  `pipeline:` block, immediately after the `rename_detect_pct: 30` line
  (currently the block's last key before the blank line separating it
  from the `# Reviewer roles` section), add two new keys in the same
  `key: value  # trailing comment` style already used by every other key
  in that block:

  ```yaml
  entry_wait: true  # master on/off switch for the mill-go/mill-plan entry-gate blocking wait; see _phase_wait.py
  entry_wait_timeout_minutes: 120  # give-up timeout (minutes) for the entry-gate wait before halting
  ```

  In `mill-config.yaml` (the hub root config, not the template), inside
  its own existing `pipeline:` block, immediately after its own
  `rename_detect_pct: 30` line, add the identical two lines verbatim
  (same keys, same default values, same trailing comments) — CLAUDE.md
  requires the hub file and the plugin template to stay in sync.

  **Bootstrap justification (for the `wiki-config-mutation` plan-validator
  check, which will flag this card's edit to `mill-config.yaml` since that
  file's own repo-relative path is the literal token the check matches
  against):** both new keys are purely additive, with safe defaults
  (`entry_wait: true` is the desired always-on default; `120` minutes is
  generous). No existing key is renamed, removed, or has its meaning
  changed. `_config.load_config` deep-merges `mill-config.yaml` fresh on
  every skill invocation (it is never cached across sessions), so a
  concurrently-running mill-go/mill-plan session in another thread simply
  keeps using its already-loaded config for the remainder of its own run
  and picks up these two new keys automatically the next time any mill
  skill starts — there is no migration step, no schema version bump, and
  no risk of a running session crashing on an unrecognized key it never
  reads. This satisfies condition (a) of the `wiki-config-mutation` fix-table
  row (a bootstrap card explaining why the change is safe mid-flight).

  **Where this justification actually gets applied (two distinct call
  sites, precision corrected after plan review round 1's NIT):**
  `mill-plan/SKILL.md`'s Phase: Plan self-validate step calls
  `_plan_validate.run(...)` directly with `skip_checks=frozenset()`
  hardcoded — that SKILL.md text has no documented override for this
  specific call site. Passing `skip_checks=frozenset({"wiki-config-mutation"})`
  there once this justification paragraph is present in the plan is an
  interpretive application of this fix-table row's intent to that direct
  self-run, not something `mill-plan/SKILL.md`'s text explicitly
  pre-authorizes today — record it as such rather than asserting it is
  already a documented mechanism. Separately, the CLI-driven review gate
  (`millpy-review-plan.py`'s own Step 1.5 validator pass, and any
  resulting halt inside Phase: Plan Review) DOES natively support
  `--skip-check wiki-config-mutation` as a first-class flag — that path
  needs no interpretive judgment call, only the flag.

- **Commit:** `config: add pipeline.entry_wait / entry_wait_timeout_minutes to template and hub config`

## Batch Tests

`verify:` runs the new unit test file directly
(`plugins/mill/unit_tests/test-phase-wait.py`), which is the only
runnable surface this batch introduces — `_phase_wait.py` is a new,
self-contained module with no existing caller yet (batches 2/3 add the
only callers), so no other existing test file can regress from this
batch's changes. The two config-file edits (card 3) need no additional
verify command: `_config.py` does have a template-vs-actual key check
(`walk_unknown_keys`/`warn_unknown_keys`), but it is warning-only (never
load-blocking) and fires only on divergence between the hub config and
the template — card 3 adds the identical two keys to both files, so no
divergence exists and no warning fires. Beyond that, the only remaining
risk is the config loader implicitly parsing the file as valid YAML,
which the unit test run does not independently exercise but which a
full-file YAML syntax error would immediately break every other mill
skill and unit test that loads config — an easy, highly-visible failure
mode that does not need a dedicated regression test.
