"""Unit tests for the mill-go variant contract.

Batch: thin-variants

Asserts that every skill listed in VARIANTS is a thin wrapper that binds its own
`VARIANT_LABEL`, declares both override-point sections (even when empty), loads
`mill-go-base` for all machinery, and carries none of that machinery itself. Also
locks the base's unbound-halt directive, the scoped no-hook-as-a-name rule for the
two override points, and the three-literal-family parameterization that keeps a
variant's own name out of the base's shell/notify/echo strings. Also locks each
variant's declared fixer-dispatch override.
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
    '"mill-go: ',
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


def _dispatch_overrides_body(text: str) -> str | None:
    """
    Extract the body of the ``## Dispatch overrides`` section from a variant file.

    Returns ``None`` when the header line is absent.
    Otherwise walks the lines after the header and stops at whichever comes first: a line
    beginning ``"## "``, a line beginning ``"Load the `mill:mill-go-base` skill"``, or end of
    file.
    The second stop condition is not optional detail: ``## Dispatch overrides`` is the last
    ``##`` header in both variant files, and the shared closing paragraph that loads the base
    sits directly beneath it with no separating header, so a naive run-to-EOF rule would
    swallow that boilerplate into the body and make the ``mill-go``-is-exactly-``(none)``
    assertion fail on an unedited file.

    Returns:
        The joined, ``.strip()``ped section body, or ``None`` if the header is missing.
    """
    lines = text.splitlines()
    header_idx: int | None = None
    for i, line in enumerate(lines):
        if line.rstrip() == "## Dispatch overrides":
            header_idx = i
            break
    if header_idx is None:
        return None

    body_lines: list[str] = []
    for line in lines[header_idx + 1 :]:
        if line.startswith("## "):
            break
        if line.startswith("Load the `mill:mill-go-base` skill"):
            break
        body_lines.append(line)
    return "\n".join(body_lines).strip()


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


def _check_fork_override() -> list[str]:
    """
    Lock the mill-go2 fixer fork override in place and confirm mill-go stays unedited.

    Five scenarios this check exists to catch, each with its own distinguishable ``FAIL:``
    string: the override added to the wrong variant, the placeholder ``(none)`` left in place
    alongside the override, a section filled with prose that never names ``fork``, mill-go's
    ``(none)`` deleted during a sibling-task merge resolution, and the extraction rule
    regressing to running to EOF.
    """
    failures: list[str] = []

    mill_go2_path = _variant_path("mill-go2")
    mill_go2_body = _dispatch_overrides_body(_read(mill_go2_path))

    if mill_go2_body is None:
        failures.append(f"FAIL: {mill_go2_path}: no '## Dispatch overrides' section found")
    else:
        if mill_go2_body == "(none)":
            failures.append(
                f"FAIL: {mill_go2_path}: '## Dispatch overrides' body is still the '(none)' "
                "placeholder -- fixer fork override missing"
            )
        if "fixer" not in mill_go2_body:
            failures.append(
                f"FAIL: {mill_go2_path}: '## Dispatch overrides' body does not contain the "
                "literal 'fixer'"
            )
        if 'subagent_type: "fork"' not in mill_go2_body:
            failures.append(
                f"FAIL: {mill_go2_path}: '## Dispatch overrides' body does not contain the "
                'literal \'subagent_type: "fork"\''
            )
        # Checked per line, not against the whole body: an override appended below a leftover
        # placeholder line makes the body no longer equal "(none)" while still carrying both
        # required literals above, so every other assertion here would pass and the stale
        # placeholder would ship undetected.
        for line in mill_go2_body.splitlines():
            if line.strip() == "(none)":
                failures.append(
                    f"FAIL: {mill_go2_path}: '## Dispatch overrides' body still contains a "
                    "stray '(none)' placeholder line alongside the override"
                )
                break

    mill_go_path = _variant_path("mill-go")
    mill_go_body = _dispatch_overrides_body(_read(mill_go_path))

    if mill_go_body is None:
        failures.append(f"FAIL: {mill_go_path}: no '## Dispatch overrides' section found")
    # Written as an equality, never a "(none)" in body containment check -- the equality is
    # what fails loudly if the extraction rule ever regresses to running to EOF and starts
    # swallowing the shared base-loading paragraph.
    elif mill_go_body != "(none)":
        failures.append(
            f"FAIL: {mill_go_path}: '## Dispatch overrides' body is {mill_go_body!r}, "
            "expected exactly '(none)' -- mill-go must stay unedited by this experiment"
        )

    return failures


def main() -> int:
    """Run all eight variant-contract checks and print a PASS/FAIL summary line."""
    checks = (
        _check_label_binding,
        _check_override_sections_present,
        _check_base_loaded,
        _check_base_halts_unbound,
        _check_variants_carry_no_machinery,
        _check_override_points_are_not_hooks,
        _check_parameterization_lock,
        _check_fork_override,
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
