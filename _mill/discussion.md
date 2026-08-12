# Discussion: CLAUDE_PLUGIN_ROOT environment variable not exported to Bash tool

```yaml
task: CLAUDE_PLUGIN_ROOT environment variable not exported to Bash tool
slug: claude-plugin-root-env-setup
status: discussing
parent: main
```

## Problem

Two field reports (GitHub issues #811 and #813, both 2026-08-10) describe the same symptom: in a
mill-plan/mill-go session, the very first `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` Bash
invocation failed with `ModuleNotFoundError: No module named '_paths'` because `$CLAUDE_PLUGIN_ROOT`
expanded to an empty string in the Bash tool's subshell for the whole session — even though
`$MILL_PYTHON`, set via the same `~/.claude/settings.json` `env` block, was populated correctly.
Both reporters worked around it by hardcoding the plugin cache path for the rest of the session,
exactly the "do NOT read or memorize its value" anti-pattern CLAUDE.md's Hard Constraints section
warns against.

This is already a partially-known failure mode: `plugins/mill/skills/cli/SKILL.md` (added
2026-05-07, commit `c767b395`) documents that `$CLAUDE_PLUGIN_ROOT` is a CC template token
substituted into SKILL.md text at load time, not a live Bash subshell variable — and specifically
flags it as empty in the Bash subshell **on Windows**. Re-verified live in this discussion session
(Linux, CC 2.1.221): the token *was* pre-substituted correctly in every SKILL.md-sourced command
shown during Phase: Explore, and `env | grep -i claude` confirmed `CLAUDE_PLUGIN_ROOT` present as a
real exported env var. So the harness-level behavior is environment/platform-dependent and outside
mill's control to "fix" directly — this task narrows to hardening the one place in the mill
codebase that doesn't defensively handle the documented failure mode.

**Why now:** two independent reports within the same window, both from autonomous
mill-plan/mill-go sessions, both self-consolidated into this single wiki task.

## Scope

**In:**
- Harden `mill-setup` Phase 4.8's plugin-root resolution (the `~/.claude/settings.json`
  `MILL_PYTHON` bootstrap write) so it no longer hard-fails via `os.environ['CLAUDE_PLUGIN_ROOT']`
  when that key is absent.
- Apply the same fix to the Phase 4.8 verify snippet at `mill-setup/SKILL.md:536`, which currently
  duplicates the same fragile `os.environ['CLAUDE_PLUGIN_ROOT']` read.
- Extract the resolution logic into a small reusable helper in `_config.py` (alongside the existing
  `resolve_plugin_template_path`), called from both sites.
- Unit test coverage for the new helper.
- Manual `/mill-setup` re-run in this repo to confirm the real inline-`-c` invocation still
  produces the correct `MILL_PYTHON` value end-to-end.

**Out:**
- No attempt to change Claude Code harness behavior itself (how/when it exports
  `CLAUDE_PLUGIN_ROOT` into the Bash tool's subshell) — confirmed outside this repo's control.
- No changes to `_preflight.check_helpers` or `_config.resolve_plugin_template_path` — both already
  handle a missing `CLAUDE_PLUGIN_ROOT` correctly (`.get()` + fallback to `Path(__file__)`-derived
  paths) and are not the reported failure site.
- No changes to the `cli/SKILL.md` guidance text itself (the "use the resolved path verbatim, never
  reconstruct `${CLAUDE_PLUGIN_ROOT}` as a shell variable" rule) — it already correctly describes
  the mitigation for SKILL.md-sourced commands; this task's gap is specifically the Python-runtime
  `os.environ` read inside Phase 4.8, a different failure surface than what that rule covers.
- No changes to the two GitHub issues beyond what's already done (both are closed, consolidated
  into this wiki task).

## Decisions

### Resolve plugin root via `sys.path[0]`, not `os.environ`

- Decision: Phase 4.8's inline `-c` script (and its verify snippet) derive the plugin root as
  `Path(sys.path[0]).parent` instead of `Path(os.environ['CLAUDE_PLUGIN_ROOT'])`.
- Rationale: Phase 4.8's own command line already carries `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"`
  as a prefix — a value CC has already substituted textually into the SKILL.md content *before* the
  Bash tool ever executes it (confirmed this session: the literal token never survives to the Bash
  subshell in SKILL.md-sourced text). Because `-c` scripts run with the `PYTHONPATH` entry prepended
  to `sys.path`, `sys.path[0]` reliably equals `<plugin-root>/scripts` regardless of whether the
  subprocess separately inherits a real `CLAUDE_PLUGIN_ROOT` env var — sidestepping the actual
  failure mode instead of adding a fallback for a case that can still occur.
- Rejected: Keep `os.environ.get('CLAUDE_PLUGIN_ROOT')` with a fallback (mirroring
  `_config.resolve_plugin_template_path`'s `Path(__file__)`-based fallback) — rejected because
  Phase 4.8 has no `__file__` to fall back to (it's inline `-c` code, not a `.py` module on disk),
  and the `sys.path[0]` approach avoids depending on the unreliable env var at all rather than
  merely tolerating its absence.

### New helper: `_config.resolve_plugin_root_from_syspath()`

- Decision: Add a small function to `_config.py`:
  `resolve_plugin_root_from_syspath(sys_path_0: str) -> Path`. It takes `sys.path[0]` as an
  explicit argument (not read internally — keeps the function pure and testable per CLAUDE.md's
  "Helpers with path args must not consult cwd/ambient state for config" spirit), validates the
  directory's name is `scripts` (guard below), and returns its parent.
- Rationale: `_config.py` already owns the analogous `resolve_plugin_template_path` fallback logic
  for the same env var, so this keeps plugin-root resolution logic in one module. A pure function
  taking an explicit string argument is unit-testable without mocking `sys.path` or `os.environ`, and
  both Phase 4.8 and its verify snippet call the same function — eliminating the class of bug where
  the two drift out of sync (the exact class CLAUDE.md already flags for mill-config.yaml/template).
- Rejected: Keep the two-line resolution inline and duplicated in both SKILL.md snippets — rejected
  because Phase 4.8 is the bootstrap-critical, hardest-to-debug-when-broken path in the whole
  skill (no `$MILL_PYTHON` yet to fall back to), which outweighs the usual YAGNI-favors-inline
  default for a two-line snippet.

### Guard against a malformed `sys.path[0]`

- Decision: `resolve_plugin_root_from_syspath` raises `SystemExit` with an actionable message
  (e.g. "expected sys.path[0] to be a .../scripts directory from PYTHONPATH -- run this via the
  documented mill-setup invocation, not standalone") when `Path(sys_path_0).name != "scripts"`,
  rather than silently returning a wrong plugin root.
- Rationale: mill-setup is the one skill an operator might hand-run a step of while debugging a
  broken bootstrap (per its own "Note: re-run /mill-setup..." guidance). A silently-wrong plugin
  root here would produce a `MILL_PYTHON` pointing at the wrong venv, which is a confusing failure
  mode two steps removed from its cause.
- Rejected: No guard, trust the invocation contract — rejected because Phase 4.8's whole reason for
  existing is to be robust at the one point in the lifecycle where nothing else is guaranteed set
  up yet.

## Technical context

- `plugins/mill/skills/mill-setup/SKILL.md` Phase 4.8 (~line 399-433): writes `MILL_PYTHON` into
  `~/.claude/settings.json`'s `env` block. Currently:
  ```python
  import sys; sys.path.insert(0, os.environ['CLAUDE_PLUGIN_ROOT'] + '/scripts'); import _claude_settings
  venv = Path(os.environ['CLAUDE_PLUGIN_ROOT']) / '.venv'
  ```
  Note the `sys.path.insert(0, ...)` call is itself redundant with the outer
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` prefix already on the command line — `sys.path[0]`
  is already that directory before this line runs. The fix removes the `os.environ` reads and the
  now-unnecessary `sys.path.insert` line, using `sys.path[0]` directly.
- The verify snippet lives in the same file at `mill-setup/SKILL.md:536`, inside the "Phase 4.8"
  section's verification block — same `os.environ['CLAUDE_PLUGIN_ROOT']` pattern, same fix.
- `plugins/mill/scripts/_config.py:128-147` (`resolve_plugin_template_path`) is the existing sibling
  pattern to follow for module placement and docstring style — new helper goes in this file,
  adjacent to it.
- `plugins/mill/scripts/_preflight.py:43-77` (`check_helpers`) is the other existing sibling pattern
  (`.get()` + fallback) — not touched by this task, but establishes the precedent that
  `CLAUDE_PLUGIN_ROOT`-optional resolution is already the norm elsewhere in this codebase; Phase
  4.8 was the outlier.
- `plugins/mill/skills/cli/SKILL.md:38-40` is the existing doc describing the template-token
  behavior — read for context, not modified by this task (see Scope: Out).
- `plugins/mill/unit_tests/test-config.py` already has an env-var-mocking pattern for
  `CLAUDE_PLUGIN_ROOT` at line ~636 (`resolve_plugin_template_path` tests) — follow this file's
  existing fixture/mocking conventions for the new helper's tests, though the new function takes
  `sys_path_0` as a direct argument so no env mocking should be needed.

## Testing

- Unit test `resolve_plugin_root_from_syspath` in `plugins/mill/unit_tests/test-config.py`
  (co-located with `resolve_plugin_template_path`'s tests): TDD candidates —
  (1) valid `.../mill/2.0.0/scripts` input returns `.../mill/2.0.0`;
  (2) input whose basename isn't `scripts` raises `SystemExit` with an actionable message;
  (3) trailing-slash / relative-path input still resolves correctly (`Path` normalization).
- After the SKILL.md edits, manually re-run `/mill-setup` in this repo (idempotent per its own
  docs) and confirm: (a) the Phase 4.8 output line reports the correct `MILL_PYTHON` path, (b) the
  Phase 4.8 verify snippet at SKILL.md:536 passes with `OK: MILL_PYTHON=...`, (c) no `KeyError` or
  other traceback.
- Run the full `unit_tests/run-all.py` suite to confirm no regression in `test-config.py`'s existing
  `resolve_plugin_template_path` cases (shared module, shared env-var subject matter).

## Q&A log

- **Q:** What should the fix's scope be? **A:** [auto-pick] Harden the mill-side code that reads
  `CLAUDE_PLUGIN_ROOT` from `os.environ` at Python-subprocess runtime (bring `mill-setup` Phase 4.8
  in line with `_preflight`/`_config`'s existing fallback pattern); no attempt to fix the Claude
  Code harness itself. **Why:** whether the harness exports the var is outside mill's control and
  confirmed inconsistent (works in this session, didn't for the two issue reporters) — but Phase
  4.8's lack of a fallback, unlike its two siblings, is a concrete in-repo gap regardless of root
  cause.
- **Q:** How should discussion.md characterize the underlying problem? **A:** [auto-pick]
  `CLAUDE_PLUGIN_ROOT` is reliably available only as literal template-substituted text inside
  SKILL.md-sourced Bash command strings — not reliably available as a real inherited OS env var to
  Python subprocesses. **Why:** this session directly demonstrated the substitution (Phase: Select's
  bash block showed an already-resolved absolute path) and the live env var was present too — so
  "unreliable everywhere" overstates it.
- **Q:** How should Phase 4.8 resolve the plugin root instead of `os.environ['CLAUDE_PLUGIN_ROOT']`?
  **A:** [auto-pick] Derive it from `sys.path[0]` (`Path(sys.path[0]).parent`), since
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` on the same command line is already textually
  substituted by CC and therefore unconditionally reliable. **Why:** sidesteps the actual failure
  mode instead of adding a fallback for a case that can still occur.
- **Q:** Apply the same fix to the verify snippet at SKILL.md:536? **A:** [auto-pick] Yes. **Why:**
  CLAUDE.md already flags "stay in sync" as a general hazard class in this repo; a verify step using
  a different resolution path than the thing it verifies is a latent bug.
- **Q:** Extract the resolution logic into a reusable helper, or keep it inline? **A:** [auto-pick]
  Add a small helper in `_config.py` (alongside `resolve_plugin_template_path`), used by both Phase
  4.8 and its verify snippet. **Why:** keeps the two call sites in sync by construction, and makes
  the logic unit-testable, matching the existing `unit_tests/` convention — outweighs the "just 2
  lines" YAGNI objection since it's the literal bootstrap-critical path.
- **Q:** Edge case — what if `sys.path[0]` doesn't look like a `.../scripts` dir (e.g. someone runs
  the snippet by hand)? **A:** [auto-pick] Guard with a clear `SystemExit` message telling the
  operator to use the documented invocation, rather than silently computing a wrong root. **Why:**
  this is the one skill operators might hand-run mid-bootstrap-debugging; a silent wrong path here
  is hard to diagnose.
- **Q:** Testing approach? **A:** [auto-pick] Unit test the new helper in `unit_tests/` (pure
  function, matches existing fixture style) plus a manual `/mill-setup` re-run in this repo to
  confirm the real inline-`-c` invocation still works end-to-end. **Why:** the unit test covers
  logic; only a live re-run exercises CC's actual template substitution, which a unit test can't
  simulate.
