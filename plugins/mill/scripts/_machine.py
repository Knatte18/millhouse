"""
_machine — machine-level config helper for mill entrypoints.

Exports
-------
MISSING : str
    Status constant returned by ``probe`` when the config file does not exist.

PRESENT : str
    Status constant returned by ``probe`` when the config file parses successfully.

MALFORMED : str
    Status constant returned by ``probe`` when the config file fails YAML parsing.

machine_config_path(home_dir) -> Path
    Return the canonical path to ``~/.millhouse/config.machine.yaml``.

load_layer(home_dir) -> dict
    Load the machine config file, returning ``{}`` if absent or empty.

probe(home_dir) -> tuple[str, object]
    Inspect the machine config file and return a ``(status, detail)`` tuple.
"""
from __future__ import annotations

from pathlib import Path

MISSING = "missing"
PRESENT = "present"
MALFORMED = "malformed"

__all__ = [
    "MISSING",
    "PRESENT",
    "MALFORMED",
    "machine_config_path",
    "load_layer",
    "probe",
]


def machine_config_path(home_dir: Path | None = None) -> Path:
    """Return the canonical path to the machine-level config file.

    Args:
        home_dir: Override for the home directory. Pass ``None`` (or omit) to
            use ``Path.home()``. Intended for test injection only.

    Returns:
        ``<home_dir>/.millhouse/config.machine.yaml``
    """
    base = home_dir if home_dir is not None else Path.home()
    return base / ".millhouse" / "config.machine.yaml"


def load_layer(home_dir: Path | None = None) -> dict:
    """Load the machine-level config file and return it as a dict.

    Returns ``{}`` when the file does not exist or is empty. Lets
    ``yaml.YAMLError`` propagate uncaught — use ``probe`` for soft-fail
    behaviour on malformed files.

    Args:
        home_dir: Override for the home directory. Pass ``None`` (or omit) to
            use ``Path.home()``. Intended for test injection only.

    Returns:
        Parsed config dict, or ``{}`` if the file is absent or empty.

    Raises:
        yaml.YAMLError: If the file exists but cannot be parsed as YAML.
    """
    import yaml

    path = machine_config_path(home_dir)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def probe(home_dir: Path | None = None) -> tuple[str, object]:
    """Inspect the machine-level config file and return a status tuple.

    Args:
        home_dir: Override for the home directory. Pass ``None`` (or omit) to
            use ``Path.home()``. Intended for test injection only.

    Returns:
        A ``(status, detail)`` tuple where ``status`` is one of ``MISSING``,
        ``PRESENT``, or ``MALFORMED``:

        - ``(MISSING, None)`` — file does not exist.
        - ``(PRESENT, parsed)`` — file exists and parses; ``parsed`` is the
          resulting dict (``{}`` substituted for an empty file).
        - ``(MALFORMED, error_string)`` — file exists but ``yaml.YAMLError``
          was raised; ``error_string`` is ``str(error)``.
    """
    import yaml

    path = machine_config_path(home_dir)
    if not path.exists():
        return (MISSING, None)
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return (PRESENT, parsed)
    except yaml.YAMLError as exc:
        return (MALFORMED, str(exc))
