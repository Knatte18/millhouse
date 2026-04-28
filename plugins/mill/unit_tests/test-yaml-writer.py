"""Unit tests for plugins/mill/scripts/_yaml_writer.py."""
from __future__ import annotations

import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import yaml  # noqa: E402

from _yaml_writer import quote_scalar  # noqa: E402

# Risky scalars that must survive a YAML round-trip when embedded in
# ``k: <value>`` context.  For each value v, we assert:
#   yaml.safe_load(f"k: {quote_scalar(v)}")["k"] == v
_RISKY_SCALARS = [
    "foo: bar",                    # colon
    "# heading",                   # leading hash
    "-leading-dash",               # leading dash
    "? leading-question",          # leading question mark
    "! leading-bang",              # leading bang
    "true",                        # YAML-reserved word
    "false",                       # YAML-reserved word
    "null",                        # YAML-reserved word
    "yes",                         # YAML 1.1 boolean alias
    "no",                          # YAML 1.1 boolean alias
    "1.0",                         # numeric-looking string
    "42",                          # integer-looking string
    "contains 'single' quotes",
    'contains "double" quotes',
    "",                            # empty string
    " leading space",
    "trailing space ",
    "2026-04-28T08:35:28Z",        # ISO-8601 timestamp — PyYAML quotes this
]

# Safe inputs that must round-trip AND must be byte-identical to the
# bare value (no quotes added by PyYAML).
_IDENTITY_CASES = [
    ("plain", "plain"),
    ("kebab-case-123", "kebab-case-123"),
    ("path/to/file", "path/to/file"),
    ("1 \u2014 par-A \u2014 YAML-quoting", "1 \u2014 par-A \u2014 YAML-quoting"),
]


def main() -> int:
    try:
        # --- round-trip tests for risky scalars ---
        for v in _RISKY_SCALARS:
            quoted = quote_scalar(v)
            parsed = yaml.safe_load(f"k: {quoted}")["k"]
            assert parsed == v, (
                f"round-trip FAIL for {v!r}: "
                f"quote_scalar returned {quoted!r}, "
                f"safe_load returned {parsed!r}"
            )
        print(f"PASS: {len(_RISKY_SCALARS)} risky scalars round-trip correctly")

        # --- identity-on-output tests for safe inputs ---
        for v, expected in _IDENTITY_CASES:
            result = quote_scalar(v)
            assert result == expected, (
                f"identity FAIL for {v!r}: expected {expected!r}, got {result!r}"
            )
        print(f"PASS: {len(_IDENTITY_CASES)} safe inputs are byte-identical")

        # --- rejection: non-str input raises TypeError ---
        try:
            quote_scalar(42)  # type: ignore[arg-type]
        except TypeError:
            print("PASS: quote_scalar(42) raises TypeError")
        else:
            raise AssertionError("expected TypeError for non-str input")

        # --- rejection: multi-line input raises ValueError ---
        try:
            quote_scalar("a\nb")
        except ValueError:
            print("PASS: quote_scalar('a\\nb') raises ValueError")
        else:
            raise AssertionError("expected ValueError for multi-line input")

        print("All _yaml_writer unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
