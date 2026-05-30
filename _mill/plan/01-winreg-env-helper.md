# Batch: winreg-env-helper

```yaml
task: "Replace powershell subprocess with winreg in mill-setup"
batch: "winreg-env-helper"
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-winenv.py
depends-on: []
```

## Batch Scope

This batch delivers the entire winreg migration in one cohesive unit: a new
`_winenv.py` helper that writes a user-level Windows environment variable via
`winreg` (with a best-effort `WM_SETTINGCHANGE` ctypes broadcast) plus its
mock-`winreg` unit test, and the rewrite of `mill-setup/SKILL.md` Phase 4.7 to
call that helper instead of shelling out to `powershell`. It is one batch
because card 2's SKILL.md edit directly depends on the `_winenv` helper from
card 1 existing, the two pieces share the same context, and the whole thing is
far under the batch size limits. Card order matters: card 1 creates the helper
and its test (TDD unit) before card 2 wires SKILL.md to it. The external
interface this batch establishes is `_winenv.set_user_env_var(name: str, value:
str) -> bool` plus the read counterpart `_winenv.get_user_env_var(name: str) ->
str | None`; no later batch consumes them (this is the only batch).

Batch-local decisions (beyond `## Shared Decisions`): the broadcast logic is
split into two functions -- a raw `_do_broadcast()` that performs the ctypes
call and may raise, and a `_broadcast_setting_change()` wrapper that calls it
and swallows every exception. This split gives the test a clean seam: patch
`_do_broadcast` to raise and assert `set_user_env_var` still returns normally.

## Cards

### Card 1: Create `_winenv.py` helper and its unit test

- **Context:**
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-setup-hub-links.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_winenv.py`
  - `plugins/mill/unit_tests/test-winenv.py`
- **Deletes:** none
- **Requirements:**
  - Create `plugins/mill/scripts/_winenv.py` with a module-level docstring whose
    `Exports` section documents both `set_user_env_var` and `get_user_env_var`,
    following the docstring style of `_setup.py` / `_config.py`. `import winreg`
    at module top.
  - Define `set_user_env_var(name: str, value: str) -> bool`: open
    `HKEY_CURRENT_USER\Environment` with
    `winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, "Environment", 0,
    winreg.KEY_READ | winreg.KEY_WRITE)` (NOT `OpenKey` -- `CreateKeyEx` is
    open-or-create so a pristine profile without the `Environment` subkey does
    not raise). Read the current value with `winreg.QueryValueEx(key, name)`,
    catching `FileNotFoundError` to mean "no current value". If the current
    value already equals `value`, return `False` without writing (idempotent
    skip). Otherwise write with `winreg.SetValueEx(key, name, 0, winreg.REG_SZ,
    value)`, then call `_broadcast_setting_change()`, then return `True`. Always
    `winreg.CloseKey(key)` (use try/finally). Do not broadcast on the
    idempotent-skip path.
  - Define `_do_broadcast() -> None`: import `ctypes` locally; set `result =
    ctypes.c_ulong(0)` and call
    `ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE,
    0, "Environment", SMTO_ABORTIFHUNG, 500, ctypes.byref(result))`
    with `HWND_BROADCAST = 0xFFFF`, `WM_SETTINGCHANGE = 0x001A`,
    `SMTO_ABORTIFHUNG = 0x0002`, and timeout `500` (milliseconds). This function
    may raise.
  - Define `_broadcast_setting_change() -> None`: call `_do_broadcast()` inside
    `try/except Exception: pass` so broadcast failures never propagate.
  - Define `get_user_env_var(name: str) -> str | None`: open
    `HKEY_CURRENT_USER\Environment` with `winreg.CreateKeyEx(...,
    winreg.KEY_READ)` (read-only access flag; still open-or-create so a pristine
    profile does not raise), read `winreg.QueryValueEx(key, name)[0]` and return
    it; return `None` when `QueryValueEx` raises `FileNotFoundError` (value
    absent). Always `winreg.CloseKey(key)` via try/finally. This is the read
    counterpart to `set_user_env_var`, consumed by SKILL.md Phase 8's PYTHONPATH
    verification (card 2) so that check uses no PowerShell.
  - All output/comments ASCII-only.
  - Create `plugins/mill/unit_tests/test-winenv.py` using the
    `sys.path.insert(0, <scripts-dir>)` + `unittest.mock.patch` pattern from
    `test-setup-hub-links.py`. Import `_winenv`. EVERY scenario below
    (scenarios 1-6, including the broadcast scenarios) MUST mock the
    `_winenv.winreg` functions (`CreateKeyEx`, `QueryValueEx`, `SetValueEx`,
    `CloseKey`) so that NO scenario can perform a real `CreateKeyEx`/`SetValueEx`
    against the developer's actual `HKCU\Environment` -- the winreg mock is
    unconditional, not per-scenario. Cover these scenarios, each also patching
    the broadcast seam as noted:
    (1) write-when-absent -- `QueryValueEx` raises `FileNotFoundError` ->
    `SetValueEx` called once with `REG_SZ` and `value`; returns `True`;
    (2) write-when-different -- existing value differs -> `SetValueEx` called
    with new value and `REG_SZ`; returns `True`;
    (3) idempotent-skip -- existing value equals `value` -> `SetValueEx` NOT
    called; returns `False`;
    (4) correct-key/args -- `CreateKeyEx` called with `HKEY_CURRENT_USER` and
    `"Environment"`; value name passed through; value type is `winreg.REG_SZ`;
    (5) broadcast-best-effort -- with the `winreg` functions mocked (per the
    unconditional rule above, so the write hits the mock not the real registry),
    additionally patch `_winenv._do_broadcast` to raise; assert
    `set_user_env_var` still returns `True` (no propagation) on a write;
    (6) broadcast-invoked-on-write / not-on-skip -- patch
    `_winenv._broadcast_setting_change` and assert it is called on a write and
    NOT called on the idempotent-skip path;
    (7) get_user_env_var-present / absent -- with `winreg` mocked: when
    `QueryValueEx` returns a value tuple, `get_user_env_var` returns the string;
    when `QueryValueEx` raises `FileNotFoundError`, it returns `None`.
  - The test must be runnable via `run-all.py --only test-winenv.py`.
- **Commit:** `feat(setup): add _winenv helper to set user env vars via winreg`

### Card 2: Rewrite mill-setup SKILL.md Phase 4.7 to call `_winenv`

- **Context:**
  - `plugins/mill/scripts/_winenv.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `plugins/mill/skills/mill-setup/SKILL.md` Phase 4.7, replace the existing
    PowerShell PYTHONPATH block -- the prose sentence beginning "Then set the
    `PYTHONPATH` Windows user environment variable ... Use `powershell` (PS5
    ...)" through the closing of the ```bash powershell -Command "..."``` fenced
    block and its following `Log:` line (the contiguous region containing
    `[System.Environment]::SetEnvironmentVariable('PYTHONPATH', $scripts,
    'User')`). Keep it as its OWN separate Python block placed immediately after
    the existing PS1/CMD-wrappers Python block (do not fold into that block).
  - The replacement intro prose states the PYTHONPATH User env var is set via
    Python `winreg` (no PowerShell).
  - The replacement fenced ```bash block invokes the helper under the standard
    prefix:
    `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
    "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."` whose body:
    imports `os`, `_winenv`, and `pathlib.Path`; computes `cache =
    Path(os.environ['USERPROFILE']) / '.claude' / 'plugins' / 'cache' /
    'millhouse' / 'mill'` and `latest_path = max((p for p in cache.iterdir() if
    p.is_dir()), key=lambda p: p.name)` (same derivation as the wrappers block);
    sets `scripts = str(latest_path / 'scripts')`; calls `changed =
    _winenv.set_user_env_var('PYTHONPATH', scripts)`; and `print`s
    `f'Set PYTHONPATH (User) = {scripts}'` when `changed` else
    `f'PYTHONPATH (User) already correct: {scripts}'` (ASCII only).
  - Update the trailing `Log:` instruction to reflect the changed/already-correct
    wording and keep the existing "takes effect in NEW shell sessions; current
    mill-setup session must keep using the inline PYTHONPATH prefix" note.
  - In Phase 8 (Verify + report), replace the single PYTHONPATH invariant-check
    line that currently reads the value via
    `[System.Environment]::GetEnvironmentVariable('PYTHONPATH', 'User')` with a
    Python `winreg` read using `_winenv.get_user_env_var('PYTHONPATH')` under the
    standard `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"
    "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."` prefix; the check
    still asserts the returned value contains `<CLAUDE_PLUGIN_ROOT>/scripts`.
    This removes the last PowerShell spawn from the `/mill-setup` run path,
    satisfying the `no-powershell-anywhere` decision. Touch ONLY that one
    invariant line in Phase 8 -- leave every other Phase 8 check unchanged.
  - Do NOT touch: Phase 4.8, the `_shortcuts.write_all` wrappers block, the
    line-103 `uv`-install PowerShell hint, the line-352 update note, or any
    Phase 8 check other than the single PYTHONPATH invariant line above.
  - No `verify:` for this card -- it is a Markdown skill-doc edit with no
    runnable surface (see `## Batch Tests`).
- **Commit:** `refactor(setup): replace Phase 4.7 powershell PYTHONPATH write with winreg`

## Batch Tests

The frontmatter `verify:` runs `test-winenv.py` only (via `run-all.py --only`),
scoped to exactly this batch's new code -- it covers Card 1 (`_winenv.py`): the
write/skip/broadcast behaviour of `set_user_env_var`, with `winreg` and the
broadcast fully mocked so no real registry write occurs. Per-batch scoping is
correct here; the batch touches no cross-cutting helper, so the full suite is
not needed.

Card 2 (the SKILL.md Phase 4.7 rewrite) has no runnable test surface -- it is a
skill-doc Markdown edit executed by an operator running `/mill-setup`. It is
verified manually by re-running `/mill-setup` on a hub and confirming the
PYTHONPATH User env var is set with no PowerShell process spawned. This is
intentionally outside the automated `verify:`.
