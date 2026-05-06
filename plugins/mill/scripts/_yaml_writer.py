"""
YAML scalar quoting helper.

Wraps PyYAML's SafeDumper to produce correctly-quoted scalar strings for
direct interpolation into ``key: <value>`` YAML lines.  Every callers that
writes a single-line YAML value should route the value through
:func:`quote_scalar` before f-string composition or token substitution.

Public API:
    quote_scalar(value: str) -> str
        Return the YAML-safe scalar form of ``value``.
"""
from __future__ import annotations

import yaml


def quote_scalar(value: str) -> str:
    """Return the YAML-safe scalar representation of ``value``.

    Delegates to ``yaml.safe_dump`` so PyYAML handles every quoting edge
    case — colons, leading dashes, reserved words (``null``, ``true``,
    ``false``), YAML 1.1 boolean aliases (``yes``, ``no``), numeric-looking
    strings, timestamps, and more.

    The implementation dumps ``{"_": value}`` and slices off the ``_: ``
    prefix and trailing newline.  ``maxsplit=1`` in the slice means a value
    that itself contains ``": "`` is handled correctly.

    ``allow_unicode=True`` ensures that safe inputs (em-dashes, accented
    characters, Norwegian text) are returned as bare scalars rather than
    ASCII-escaped sequences, keeping on-disk YAML files stable across writes.

    Args:
        value: The string to encode as a YAML scalar.

    Returns:
        A YAML-safe scalar string suitable for embedding after ``key: ``.
        Safe inputs (no special characters) are returned byte-identical to
        the input.  Inputs that require quoting are wrapped in single quotes
        by PyYAML.

    Raises:
        TypeError: ``value`` is not a ``str``.
        ValueError: ``value`` contains a newline character.  Multi-line
            values must use the literal-block ``|`` form, which is the
            caller's responsibility.
    """
    if not isinstance(value, str):
        raise TypeError(f"quote_scalar requires str, got {type(value).__name__!r}")
    if "\n" in value:
        raise ValueError(
            "quote_scalar does not support multi-line values; "
            "use a literal-block scalar (|) at the call site"
        )
    dumped = yaml.safe_dump(
        {"_": value},
        default_flow_style=False,
        allow_unicode=True,
        width=float("inf"),
    )
    # dumped is "_: <scalar>\n"; split on first ": " only (maxsplit=1) so
    # values that contain ": " are not truncated.
    return dumped.split(": ", 1)[1].rstrip("\n")
