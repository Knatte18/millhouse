from __future__ import annotations

import re


def parse_home_md(content: str) -> list[dict]:
    tasks: list[dict] = []

    lines = content.split("\n")
    current_group: str | None = None
    i = 0

    while i < len(lines):
        line = lines[i]

        layer_match = re.match(r"^# Layer ([A-Z])$", line)
        if layer_match:
            current_group = layer_match.group(1)
            i += 1
            continue

        if re.match(r"^# ", line):
            current_group = None
            i += 1
            continue

        task_heading_match = re.match(r"^## (.+)$", line)
        if task_heading_match:
            title = task_heading_match.group(1)
            i += 1

            if i >= len(lines):
                break

            slug_line = lines[i]
            slug_match = re.match(
                r"^\[(?P<slug>[a-z][a-z0-9-]*)\]( \[(?P<status>s|active|ready-to-merge|pr-pending|done|abandoned)\])?",
                slug_line,
            )
            if not slug_match:
                i += 1
                continue

            slug = slug_match.group("slug")
            status = slug_match.group("status")
            if status in ("s", "abandoned"):
                status = None

            i += 1

            brief = ""
            brief_lines: list[str] = []
            in_brief = False

            while i < len(lines):
                current_line = lines[i]

                if re.match(r"^## ", current_line) or re.match(r"^# ", current_line):
                    break

                if current_line.strip():
                    if not in_brief:
                        in_brief = True
                    brief_lines.append(current_line)
                else:
                    if in_brief:
                        break
                    i += 1
                    continue

                i += 1

            if brief_lines:
                brief = " ".join(line.strip() for line in brief_lines)

            tasks.append(
                {
                    "slug": slug,
                    "title": title,
                    "group": current_group,
                    "brief": brief,
                    "status": status,
                }
            )
            continue

        i += 1

    return tasks
