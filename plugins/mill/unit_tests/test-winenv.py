"""Unit tests for plugins/mill/scripts/_winenv.py.

Tests cover set_user_env_var write/skip behavior, broadcast best-effort,
and get_user_env_var read behavior. All winreg functions are mocked
unconditionally so no real registry operations occur.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _winenv  # noqa: E402


def test_write_when_absent() -> None:
    """QueryValueEx raises FileNotFoundError -> SetValueEx called, returns True."""
    with patch.object(_winenv, "winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value = mock_key
        mock_winreg.QueryValueEx.side_effect = FileNotFoundError
        mock_winreg.REG_SZ = "REG_SZ"

        result = _winenv.set_user_env_var("TEST_VAR", "test_value")

        assert result is True, "Should return True on write"
        mock_winreg.SetValueEx.assert_called_once()
        mock_winreg.CloseKey.assert_called_once_with(mock_key)

    print("PASS: write-when-absent")


def test_write_when_different() -> None:
    """Existing value differs -> SetValueEx called, returns True."""
    with patch.object(_winenv, "winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("old_value", 1)
        mock_winreg.REG_SZ = "REG_SZ"

        result = _winenv.set_user_env_var("TEST_VAR", "new_value")

        assert result is True, "Should return True on write"
        mock_winreg.SetValueEx.assert_called_once()
        mock_winreg.CloseKey.assert_called_once_with(mock_key)

    print("PASS: write-when-different")


def test_idempotent_skip() -> None:
    """Existing value equals target -> SetValueEx NOT called, returns False."""
    with patch.object(_winenv, "winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("same_value", 1)

        result = _winenv.set_user_env_var("TEST_VAR", "same_value")

        assert result is False, "Should return False on idempotent skip"
        mock_winreg.SetValueEx.assert_not_called()
        mock_winreg.CloseKey.assert_called_once_with(mock_key)

    print("PASS: idempotent-skip")


def test_correct_key_and_args() -> None:
    """CreateKeyEx called with correct args; SetValueEx called with REG_SZ."""
    with patch.object(_winenv, "winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value = mock_key
        mock_winreg.QueryValueEx.side_effect = FileNotFoundError
        mock_winreg.REG_SZ = "REG_SZ"
        mock_winreg.HKEY_CURRENT_USER = 0x80000001
        mock_winreg.KEY_READ = 0x20019
        mock_winreg.KEY_WRITE = 0x20006

        _winenv.set_user_env_var("MY_VAR", "my_value")

        # Verify CreateKeyEx called with correct args
        mock_winreg.CreateKeyEx.assert_called_once_with(
            0x80000001,
            "Environment",
            0,
            0x20019 | 0x20006,
        )

        # Verify SetValueEx called with var name, value, and REG_SZ type
        call_args = mock_winreg.SetValueEx.call_args
        assert call_args[0][1] == "MY_VAR", "Var name should be passed through"
        assert call_args[0][3] == "REG_SZ", "Type should be REG_SZ"
        assert call_args[0][4] == "my_value", "Value should be passed through"

    print("PASS: correct-key/args")


def test_broadcast_best_effort() -> None:
    """_do_broadcast raises -> set_user_env_var still returns True."""
    with patch.object(_winenv, "winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value = mock_key
        mock_winreg.QueryValueEx.side_effect = FileNotFoundError
        mock_winreg.REG_SZ = "REG_SZ"

        with patch.object(_winenv, "_do_broadcast") as mock_broadcast:
            mock_broadcast.side_effect = Exception("Broadcast failed")
            result = _winenv.set_user_env_var("TEST_VAR", "test_value")

        assert result is True, "Should return True even if broadcast fails"
        mock_winreg.SetValueEx.assert_called_once()

    print("PASS: broadcast-best-effort")


def test_broadcast_invoked_on_write_not_on_skip() -> None:
    """_broadcast_setting_change called on write, not on idempotent skip."""
    with patch.object(_winenv, "winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value = mock_key

        with patch.object(
            _winenv, "_broadcast_setting_change"
        ) as mock_broadcast:
            # Test 1: broadcast called on write
            mock_winreg.QueryValueEx.side_effect = FileNotFoundError
            mock_winreg.REG_SZ = "REG_SZ"
            _winenv.set_user_env_var("TEST_VAR", "value1")
            assert (
                mock_broadcast.call_count == 1
            ), "Should call broadcast on write"

            # Test 2: broadcast not called on skip
            mock_broadcast.reset_mock()
            mock_winreg.QueryValueEx.side_effect = None
            mock_winreg.QueryValueEx.return_value = ("value2", 1)
            _winenv.set_user_env_var("TEST_VAR", "value2")
            assert (
                mock_broadcast.call_count == 0
            ), "Should not call broadcast on skip"

    print("PASS: broadcast-invoked-on-write / not-on-skip")


def test_get_user_env_var_present() -> None:
    """QueryValueEx returns value -> get_user_env_var returns string."""
    with patch.object(_winenv, "winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("my_value", 1)

        result = _winenv.get_user_env_var("MY_VAR")

        assert result == "my_value", "Should return the value string"
        mock_winreg.CloseKey.assert_called_once_with(mock_key)

    print("PASS: get_user_env_var-present")


def test_get_user_env_var_absent() -> None:
    """QueryValueEx raises FileNotFoundError -> get_user_env_var returns None."""
    with patch.object(_winenv, "winreg") as mock_winreg:
        mock_key = MagicMock()
        mock_winreg.CreateKeyEx.return_value = mock_key
        mock_winreg.QueryValueEx.side_effect = FileNotFoundError

        result = _winenv.get_user_env_var("MISSING_VAR")

        assert result is None, "Should return None when var absent"
        mock_winreg.CloseKey.assert_called_once_with(mock_key)

    print("PASS: get_user_env_var-absent")
