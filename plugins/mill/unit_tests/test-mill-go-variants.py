"""Unit tests for the mill-go variant contract.

Batch: thin-variants

Asserts that every skill listed in VARIANTS is a thin wrapper that binds its own
`VARIANT_LABEL`, declares both override-point sections (even when empty), loads
`mill-go-base` for all machinery, and carries none of that machinery itself. Also
locks the base's unbound-halt directive, the scoped no-hook-as-a-name rule for the
two override points, and the three-literal-family parameterization that keeps a
variant's own name out of the base's shell/notify/echo strings.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SKILLS = HUB / "plugins" / "mill" / "skills"

VARIANTS = ("mill-go", "mill-go2")
BASE = "mill-go-base"

VARIANT_LABEL_PATTERN = re.compile(r"^VARIANT_LABEL:\s*(\S+)\s*$", re.MULTILINE)

MACHINERY_LITERALS = (
    "## Agent-mode dispatch",
    "## Holistic code review",
    "## Execute",
    "You are the **Builder**",
)

MILL_GO_LITERALS = (
    'commit -m "mill-go: ',
    '_notify.notify("mill-go.',
    "[mill-go]",
)

VARIANT_LABEL_LITERALS = (
    'commit -m "<VARIANT_LABEL>: ',
    '_notify.notify("<VARIANT_LABEL>.',
    "[<VARIANT_LABEL>]",
)


def _variant_path(name: str) -> Path:
    """Build the SKILL.md path for a variant or the base, by directory name."""
    return SKILLS / name / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_label_binding() -> list[str]:
    """
    Each variant file must bind its own distinct VARIANT_LABEL.

    Exactly one `VARIANT_LABEL: <value>` line per variant file, and the captured
    value must equal the variant's own directory name. The two captured values
    must differ from each other.
    """
    failures: list[str] = []
    captured: dict[str, str] = {}

    for name in VARIANTS:
        path = _variant_path(name)
        text = _read(path)
        matches = VARIANT_LABEL_PATTERN.findall(text)
        if len(matches) != 1:
            failures.append(
                f"FAIL: {path}: expected exactly one 'VARIANT_LABEL: <value>' line, found {len(matches)}"
            )
            continue
        value = matches[0]
        if value != name:
            failures.append(
                f"FAIL: {path}: VARIANT_LABEL is bound to '{value}', expected '{name}'"
            )
        captured[name] = value

    if len(set(captured.values())) != len(captured):
        failures.append(
            f"FAIL: variant VARIANT_LABEL values are not distinct: {captured!r}"
        )

    return failures


def _check_override_sections_present() -> list[str]:
    """
    Each variant must declare both override-point sections and its binding section.

    A missing `## Dispatch overrides` or `## Driver preamble` header would leave
    the base consulting a section that does not exist.
    """
    failures: list[str] = []
    required_headers = ("## Dispatch overrides", "## Driver preamble", "## Variant binding")

    for name in VARIANTS:
        path = _variant_path(name)
        lines = _read(path).splitlines()
        for header in required_headers:
            if header not in lines:
                failures.append(f"FAIL: {path}: missing required header line '{header}'")

    return failures


def _check_base_loaded() -> list[str]:
    """Each variant file must load mill-go-base by its skill reference."""
    failures: list[str] = []

    for name in VARIANTS:
        path = _variant_path(name)
        text = _read(path)
        if "mill:mill-go-base" not in text:
            failures.append(f"FAIL: {path}: does not contain the literal 'mill:mill-go-base'")

    return failures


def _check_base_halts_unbound() -> list[str]:
    """The base must halt with its documented message when no variant bound VARIANT_LABEL."""
    failures: list[str] = []
    path = _variant_path(BASE)
    text = _read(path)
    expected = "[mill-go-base] HALT: mill-go-base is not invocable directly"
    if expected not in text:
        failures.append(f"FAIL: {path}: missing the literal '{expected}'")

    return failures


def _check_variants_carry_no_machinery() -> list[str]:
    """
    Variant files must be thin: under 4096 bytes and free of base machinery literals.

    This is the regression catch for someone re-inlining the base into a variant.
    """
    failures: list[str] = []

    for name in VARIANTS:
        path = _variant_path(name)
        raw = path.read_bytes()
        if len(raw) >= 4096:
            failures.append(f"FAIL: {path}: is {len(raw)} bytes, expected under 4096")
        text = raw.decode("utf-8")
        for literal in MACHINERY_LITERALS:
            if literal in text:
                failures.append(f"FAIL: {path}: contains machinery literal '{literal}'")

    return failures


def _check_override_points_are_not_hooks() -> list[str]:
    """
    Override points must be scoped, not named as global hooks.

    Neither variant file may contain a `## Dispatch hooks` or `## Driver hook`
    header, and neither of the base's two consulting directives -- the lines
    containing 'consult your variant's' or 'treat your variant's' -- may use the
    word 'hook' to describe the mechanism. The base is not searched globally for
    the word, since it legitimately inherits two incidental pre-existing
    occurrences of the English word unrelated to override points.
    """
    failures: list[str] = []
    banned_headers = ("## Dispatch hooks", "## Driver hook")

    for name in VARIANTS:
        path = _variant_path(name)
        lines = _read(path).splitlines()
        for header in banned_headers:
            if header in lines:
                failures.append(f"FAIL: {path}: contains banned header line '{header}'")

    base_path = _variant_path(BASE)
    base_lines = _read(base_path).splitlines()
    consulting_markers = ("consult your variant's", "treat your variant's")
    found_marker = False
    for line in base_lines:
        for marker in consulting_markers:
            if marker in line:
                found_marker = True
                if "hook" in line.lower():
                    failures.append(
                        f"FAIL: {base_path}: consulting directive line containing "
                        f"'{marker}' uses the word 'hook': {line!r}"
                    )

    if not found_marker:
        failures.append(
            f"FAIL: {base_path}: found no line containing either of {consulting_markers!r}"
        )

    return failures


def _check_parameterization_lock() -> list[str]:
    """
    The base must be fully parameterized on the three literal families, and no
    variant file may reintroduce a hardcoded 'mill-go' literal from those families.
    """
    failures: list[str] = []
    base_path = _variant_path(BASE)
    base_text = _read(base_path)

    for literal in MILL_GO_LITERALS:
        if literal in base_text:
            failures.append(f"FAIL: {base_path}: still contains unparameterized literal '{literal}'")

    for literal in VARIANT_LABEL_LITERALS:
        if literal not in base_text:
            failures.append(f"FAIL: {base_path}: missing parameterized literal '{literal}'")

    for name in VARIANTS:
        path = _variant_path(name)
        text = _read(path)
        for literal in MILL_GO_LITERALS:
            if literal in text:
                failures.append(f"FAIL: {path}: contains hardcoded literal '{literal}'")

    return failures


def main() -> int:
    """Run all seven variant-contract checks and print a PASS/FAIL summary line."""
    checks = (
        _check_label_binding,
        _check_override_sections_present,
        _check_base_loaded,
        _check_base_halts_unbound,
        _check_variants_carry_no_machinery,
        _check_override_points_are_not_hooks,
        _check_parameterization_lock,
    )

    all_failures: list[str] = []
    for check in checks:
        all_failures.extend(check())

    if all_failures:
        for msg in all_failures:
            print(msg, file=sys.stderr)
        print(f"FAIL: {len(all_failures)} variant-contract check(s) failed", file=sys.stderr)
        return 1

    print("PASS: mill-go variant contract holds for all variants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
