from __future__ import annotations

import re


def parse_home_md(content: str) -> list[dict]:
    tasks: list[dict] = []

    lines = content.split("\n")
    current_group: str | None = None
    i = 0

    while i < len(lines):
        line = lines[i]

        # Layer header with optional parenthetical suffix: # Layer D (isolated -- run alone)
        layer_match = re.match(r"^# Layer ([A-Z])(?:\s+.*)?$", line)
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
            title_raw = task_heading_match.group(1)
            i += 1

            if i >= len(lines):
                break

            slug_line = lines[i]

            # Check for valid slug line (either [slug] or [[slug]](proposal-slug.md))
            slug_match = re.match(
                r"^\[(?P<slug>[a-z][a-z0-9-]*)\]( \[(?P<status>s|active|ready-to-merge|pr-pending|done|blocked|abandoned)\])?",
                slug_line,
            )
            # Also check for proposal link format
            proposal_match = re.match(
                r"^\[\[(?P<slug>[a-z][a-z0-9-]*)\]\]\(proposal-[a-z][a-z0-9-]*\.md\)",
                slug_line,
            )

            if not slug_match and not proposal_match:
                # This is an info-only ## heading, skip it
                i += 1
                continue

            if slug_match:
                slug = slug_match.group("slug")
                status = slug_match.group("status")
            else:
                slug = proposal_match.group("slug")
                status = None

            # Parse [s] as None, [abandoned] as "abandoned", others as-is
            if status == "s":
                status = None
            elif status == "abandoned":
                status = "abandoned"

            i += 1

            # Capture brief across multiple paragraphs
            brief_paragraphs: list[str] = []
            current_paragraph: list[str] = []

            while i < len(lines):
                current_line = lines[i]

                if re.match(r"^## ", current_line) or re.match(r"^# ", current_line):
                    break

                if current_line.strip():
                    current_paragraph.append(current_line.strip())
                else:
                    # Blank line - end current paragraph
                    if current_paragraph:
                        brief_paragraphs.append(" ".join(current_paragraph))
                        current_paragraph = []

                i += 1

            # Add any remaining paragraph
            if current_paragraph:
                brief_paragraphs.append(" ".join(current_paragraph))

            # Collapse all paragraphs to one space-joined string
            brief = " ".join(brief_paragraphs)

            # Strip numeric prefix and group code from title
            # e.g., "30 (D) -- Foo" -> "Foo" or "30 -- Foo" -> "Foo"
            title = title_raw
            title = re.sub(r"^\d+\s+", "", title)  # Remove numeric prefix
            title = re.sub(r"^\([A-Z]\)\s+", "", title)  # Remove group code
            title = re.sub(r"^\([A-Z]\)\s*--\s*", "", title)  # Remove (D) -- pattern
            title = re.sub(r"^--\s+", "", title)  # Remove leading --

            tasks.append(
                {
                    "slug": slug,
                    "title": title,
                    "group": current_group,
                    "brief": brief,
                    "status": status,
                    "has_proposal": bool(proposal_match),
                }
            )
            continue

        i += 1

    return tasks
