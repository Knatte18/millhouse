"""
Windows registry utilities for environment variable operations.

Exports
-------
set_user_env_var(name: str, value: str) -> bool
    Set a user-level Windows environment variable via winreg. Returns True
    if the value was written, False if it was already correct (idempotent skip).

get_user_env_var(name: str) -> str | None
    Read a user-level Windows environment variable via winreg. Returns the
    value string, or None if the variable is not set.
"""
from __future__ import annotations

import winreg


def set_user_env_var(name: str, value: str) -> bool:
    r"""Set a user-level environment variable via Windows registry.

    Opens HKEY_CURRENT_USER\Environment, checks if the value already equals
    the target; if so, returns False (idempotent skip). Otherwise writes the
    new value with winreg.REG_SZ type and broadcasts a WM_SETTINGCHANGE
    message, returning True.

    Always closes the registry key via try/finally, even on error.

    Args:
        name: Environment variable name.
        value: Value to set.

    Returns:
        True if the value was written; False if it was already correct.
    """
    key = winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        "Environment",
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    )
    try:
        try:
            current, _ = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            current = None

        if current == value:
            return False

        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        _broadcast_setting_change()
        return True
    finally:
        winreg.CloseKey(key)


def _do_broadcast() -> None:
    """Broadcast WM_SETTINGCHANGE message via ctypes.

    Sends a message to all windows notifying them that the user environment
    has changed. May raise on failure; caller is responsible for error handling.
    """
    import ctypes

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002

    result = ctypes.c_ulong(0)
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "Environment",
        SMTO_ABORTIFHUNG,
        500,
        ctypes.byref(result),
    )


def _broadcast_setting_change() -> None:
    """Best-effort broadcast of WM_SETTINGCHANGE.

    Calls _do_broadcast() and silently swallows any exception; broadcast
    failures never propagate.
    """
    try:
        _do_broadcast()
    except Exception:
        pass


def get_user_env_var(name: str) -> str | None:
    r"""Read a user-level environment variable via Windows registry.

    Opens HKEY_CURRENT_USER\Environment read-only, retrieves the value,
    and returns it. Returns None if the variable is not set (FileNotFoundError).

    Always closes the registry key via try/finally, even on error.

    Args:
        name: Environment variable name.

    Returns:
        The value string, or None if not set.
    """
    key = winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        "Environment",
        0,
        winreg.KEY_READ,
    )
    try:
        try:
            value, _ = winreg.QueryValueEx(key, name)
            return value
        except FileNotFoundError:
            return None
    finally:
        winreg.CloseKey(key)
