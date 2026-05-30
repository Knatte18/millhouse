# Discussion: Replace powershell subprocess with winreg in mill-setup

```yaml
task: Replace powershell subprocess with winreg in mill-setup
slug: mill-setup-winreg
status: discussing
parent: main
```

## Problem

`mill-setup` Phase 4.7 sets the user-level `PYTHONPATH` environment variable
by shelling out to `powershell -Command "[System.Environment]::SetEnvironmentVariable('PYTHONPATH', $scripts, 'User')"`.
On Windows 11 this spawns PowerShell 5 (PS5), which costs roughly 500 ms of
interpreter startup for a single registry write. Since `mill-setup` is re-run
on every plugin upgrade, that cost recurs needlessly.

The same effect — write the per-user environment variable and make new shells
pick it up — is achievable with the Python standard library (`winreg` for the
`HKCU\Environment` write, `ctypes` for the change broadcast), with no
subprocess and no PS5 startup. The operator has also asked, more strongly than
the raw timing motivates, to **eliminate PowerShell from this code path
entirely** — the migration is as much about removing the PS5 dependency as
about the milliseconds.

**Why now:** PS5 startup is a measurable, repeated tax on a frequently-run
bootstrap step, and the operator wants the PowerShell dependency gone from
mill-setup's environment-variable handling.

## Scope

**In:**

- A new helper module `plugins/mill/scripts/_winenv.py` exposing
  `set_user_env_var(name: str, value: str) -> bool` — writes the value to
  `HKCU\Environment` via `winreg` (idempotent: returns `False` and skips the
  write when the existing value already matches), then best-effort broadcasts
  `WM_SETTINGCHANGE` via `ctypes` so already-running shells/Explorer can refresh.
- Rewrite of `mill-setup/SKILL.md` **Phase 4.7**: replace the
  `powershell -Command "...SetEnvironmentVariable..."` block with a **separate**
  `python.exe -c` block (placed immediately after the existing PS1-wrappers
  python block) that computes the latest-cache `scripts` dir and calls
  `_winenv.set_user_env_var('PYTHONPATH', <scripts>)`.
- Unit test `plugins/mill/unit_tests/test-winenv.py` covering the helper with
  `winreg` mocked.

**Out:**

- Phase 4.8 (`MILL_PYTHON`) — already pure Python writing
  `~/.claude/settings.json`; **not** touched. It is **not** promoted to a real
  Windows env var; the settings.json design is deliberate and stays.
- The PS1 shortcut wrappers themselves (Phase 4.7's `_shortcuts.write_all`
  step). Those generate `.ps1` forwarder files — that is file generation, not a
  PowerShell subprocess invocation, and is unchanged.
- The unrelated PowerShell mention at SKILL.md line 103 (the `uv` install hint
  `irm https://astral.sh/uv/install.ps1 | iex`) — that is operator guidance
  text, not a subprocess mill-setup runs. Left as-is.
- `_setup.py` and all `_subprocess_util` git calls — they shell out to `git`,
  not PowerShell, and are out of scope.
- Any non-`User` (machine-level / `HKLM`) env-var support. Helper writes
  `HKCU\Environment` only.

## Decisions

### scope-only-phase-4.7

- Decision: Migrate only the Phase 4.7 `PYTHONPATH` PowerShell call. Phase 4.8
  stays on settings.json.
- Rationale: Phase 4.7 is the sole remaining PowerShell *subprocess* in
  mill-setup. Phase 4.8 was already migrated to settings.json in an earlier
  task; re-touching it would undo a deliberate design. The Home.md task blurb
  says "Phase 4.7/4.8 ×2" but that framing is stale — only one PowerShell call
  remains today.
- Rejected: Also promoting `MILL_PYTHON` to a real env var via winreg — changes
  the intentional settings.json design for no benefit.

### new-module-_winenv

- Decision: Put the logic in a new `_winenv.py` module exposing
  `set_user_env_var(name, value) -> bool`.
- Rationale: One helper per concern (matches the flat `_*.py` helper
  convention), reusable by any future Windows env-var need, and unit-testable in
  isolation with `winreg` mocked. SKILL.md calls it through the standard inline
  `python.exe -c` pattern used by other phases.
- Rejected: Extending `_setup.py` (mixes registry concern into junction/wiki
  helper); inlining winreg directly in the SKILL.md block (not unit-testable).

### winreg-plus-broadcast

- Decision: Write via `winreg`, then best-effort broadcast `WM_SETTINGCHANGE`
  via `ctypes` `SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0,
  "Environment", ...)`.
- Rationale: Faithful parity with `[Environment]::SetEnvironmentVariable(...,
  'User')`, which both writes `HKCU\Environment` and broadcasts the change so
  running apps refresh. A pure registry write would silently drop the broadcast
  half.
- Rejected: winreg-only (drops the refresh-running-apps behaviour the .NET call
  provided).

### broadcast-best-effort

- Decision: The registry write is the source of truth and must succeed (errors
  propagate). The `WM_SETTINGCHANGE` broadcast is best-effort — any
  `ctypes`/OS error during broadcast is swallowed; the helper does **not** raise
  on broadcast failure.
- Rationale: The broadcast is a convenience for already-running processes; the
  existing "takes effect in NEW shell sessions" note already covers the
  fallback. Failing setup over a cosmetic refresh (e.g. headless/no message
  pump) would be wrong.
- Rejected: Raising on broadcast failure.

### reg-type-sz

- Decision: Write the value as `REG_SZ`.
- Rationale: The scripts path is fully literal with no `%VAR%` tokens. .NET's
  `SetEnvironmentVariable` writes `REG_SZ` for non-templated values; `REG_SZ` is
  what Windows expects here.
- Rejected: `REG_EXPAND_SZ` — unnecessary; only matters when the value embeds
  `%USERPROFILE%`-style tokens.

### idempotent-skip

- Decision: `set_user_env_var` reads the current value first; if it already
  equals `value`, skip the write and return `False`. Otherwise write and return
  `True`. (On a successful write the broadcast still fires; on a skip it need
  not.)
- Rationale: mill-setup is explicitly idempotent and re-run on every upgrade.
  Returning a changed-bool lets SKILL.md log "Set PYTHONPATH" vs "already
  correct", matching the existing Phase 4.8 `MILL_PYTHON already correct` /
  `MILL_PYTHON set` reporting style.
- Rejected: Always-write (loses the idempotent-skip signal and the no-op log
  path).

### separate-python-block

- Decision: In SKILL.md Phase 4.7, keep the PYTHONPATH-set as its own
  `python.exe -c` block placed immediately after the existing PS1-wrappers
  python block (rather than folding it into that block).
- Rationale: Mirrors today's structure (wrappers step, then PYTHONPATH step) and
  keeps each block single-purpose and independently readable. The block
  recomputes `latest_path`/`scripts` from the cache dir the same way the
  wrappers block does.
- Rejected: Folding into the wrappers block (one invocation, but couples two
  concerns into one block).

### no-powershell-anywhere

- Decision: The replacement uses **zero** PowerShell. The new block is a
  `python.exe -c` invocation under the standard
  `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
  "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` prefix used by every other
  python phase in the skill.
- Rationale: Operator's explicit, emphasized requirement — avoid PowerShell
  entirely in this path. (The line-103 `uv`-install hint is documentation text,
  not a subprocess, so it does not violate this.)
- Rejected: Any hybrid that keeps a `powershell` call.

## Technical context

- **Only remaining PowerShell subprocess in mill-setup** is `mill-setup/SKILL.md`
  Phase 4.7, lines ~338-348 — the `powershell -Command "... SetEnvironmentVariable
  ('PYTHONPATH', $scripts, 'User') ..."` block. That block is what this task
  replaces.
- **Phase 4.7 structure today:** (a) a `python.exe -c` block calling
  `_shortcuts.write_all(Path('.millhouse'), latest_path)` to generate `.ps1`
  wrappers, where `latest_path = max((p for p in cache.iterdir() if p.is_dir()),
  key=lambda p: p.name)` and `cache = USERPROFILE/.claude/plugins/cache/
  millhouse/mill`; then (b) the PowerShell block that sets `PYTHONPATH` to
  `latest_path/scripts`. The new python block reuses the exact same
  `cache`/`latest_path` derivation, then `scripts = latest_path / 'scripts'`.
- **Phase 4.8** (`MILL_PYTHON` → `~/.claude/settings.json`) is already pure
  Python (`json` + `pathlib`); it is the template for the
  already-correct/changed logging style the new block should mirror.
- **Helper conventions** (`plugins/mill/scripts/`): flat modules named `_*.py`;
  a module-level docstring with an `Exports`/Public-API section (see `_setup.py`,
  `_config.py`); ASCII-only `print()`/`_log()` output (Windows cp1252 — use
  ` -- ` not `—`, ` -> ` not `->`).
- **`winreg`** is Python stdlib, Windows-only. Key path: `HKEY_CURRENT_USER\
  Environment`. Open with `winreg.OpenKey(winreg.HKEY_CURRENT_USER,
  "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)` (or read then write);
  read via `winreg.QueryValueEx(key, name)` (raises `FileNotFoundError` when the
  value is absent — treat as "no current value"); write via
  `winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)`.
- **Broadcast:** `ctypes.windll.user32.SendMessageTimeoutW` with
  `HWND_BROADCAST = 0xFFFF`, `WM_SETTINGCHANGE = 0x001A`, `lParam = "Environment"`,
  a flag like `SMTO_ABORTIFHUNG = 0x0002`, and a short timeout. Wrap in
  try/except and swallow failures.
- **Test conventions** (`plugins/mill/unit_tests/`): files named
  `test-<name>.py`, run via `run-all.py`; in-memory / mock fixtures, **no real
  git/LLM** and (here) **no real registry**. `test-setup-hub-links.py` shows the
  `sys.path.insert(0, HUB/'plugins'/'mill'/'scripts')` import pattern and
  `unittest.mock.patch` usage.

## Constraints

- **No PowerShell** anywhere in the replaced code path (operator hard
  requirement).
- **ASCII-only stdout** — any log strings the helper or SKILL.md block prints
  must avoid non-ASCII (cp1252 crash risk).
- **Idempotent** — mill-setup re-runs on every upgrade; the helper must no-op
  cleanly when the value is already correct.
- **Windows-only** — `winreg`/`ctypes.windll` exist only on Windows; this code
  path is Windows-specific by nature (mill-setup's env-var step). The unit test
  must not depend on a real Windows registry (mock `winreg`), so it can run
  anywhere `run-all.py` runs.
- **Registry write must succeed or raise**; broadcast must never raise.
- No `CONSTRAINTS.md` exists at the hub root (checked) — no additional repo-wide
  constraints to enumerate.

## Testing

`plugins/mill/unit_tests/test-winenv.py` — TDD candidate, `winreg` mocked
(monkeypatch the `winreg` module / its functions; do not touch the real
registry). `ctypes` broadcast also mocked/stubbed.

Scenarios to cover:

- **Write-when-absent:** no existing value (`QueryValueEx` raises
  `FileNotFoundError`) → `SetValueEx` called once with `REG_SZ` and the given
  value; returns `True`.
- **Write-when-different:** existing value differs → `SetValueEx` called with
  the new value and `REG_SZ`; returns `True`.
- **Idempotent skip:** existing value already equals `value` → `SetValueEx`
  **not** called; returns `False`.
- **Correct key/args:** opens `HKEY_CURRENT_USER\Environment`; value name passed
  through; value type is `REG_SZ` (assert the type constant).
- **Broadcast best-effort:** broadcast invoked after a real write; when the
  broadcast stub raises, `set_user_env_var` still returns normally (does not
  propagate) and the registry write result is unaffected.
- **Broadcast not required on skip:** acceptable for the idempotent-skip path to
  skip the broadcast (assert chosen behaviour explicitly so it's pinned).

No integration test against the real registry (operator picked the
mock-winreg-only approach). SKILL.md Phase 4.7 itself is exercised manually by
re-running `/mill-setup`; not unit-covered.

## Q&A log

- **Q:** Which PowerShell calls are in scope? **A:** Only Phase 4.7's
  `PYTHONPATH` write. Phase 4.8 (`MILL_PYTHON`) is already settings.json-based
  and stays. The Home.md "4.7/4.8 ×2" blurb is stale — only one PS call remains.
- **Q:** winreg-only or also broadcast `WM_SETTINGCHANGE`? **A:** winreg +
  `WM_SETTINGCHANGE` broadcast, for parity with `[Environment]::
  SetEnvironmentVariable(..., 'User')`.
- **Q:** Where should the logic live? **A:** New `_winenv.py` module with
  `set_user_env_var(name, value) -> bool`.
- **Q:** How to test? **A:** Mock `winreg`, unit test only — no real registry
  touch (repo's no-real-IO unit-test rule).
- **Q:** If the broadcast fails? **A:** Best-effort — swallow, never raise. The
  registry write is the source of truth.
- **Q:** REG value type? **A:** `REG_SZ` (path is literal, no `%VAR%` tokens).
- **Q:** Fold the PYTHONPATH call into the existing wrappers python block or keep
  separate? **A:** Separate `python.exe -c` block right after the wrappers block.
- **Q:** Anything broader on PowerShell? **A:** Avoid PowerShell **entirely** in
  this path — operator's emphasized requirement. The replacement is 100% Python.
