from __future__ import annotations


def render(tasks: list[dict]) -> dict[str, str]:
    """
    Render task dicts to Home.md, _Sidebar.md, and proposal-<slug>.md files.

    Returns a dict mapping rel_path -> content.
    """
    result: dict[str, str] = {}

    home_lines: list[str] = ["# Tasks", ""]
    sidebar_lines: list[str] = []

    tasks_by_group: dict[str | None, list[dict]] = {}
    for task in tasks:
        group = task.get("group")
        if group not in tasks_by_group:
            tasks_by_group[group] = []
        tasks_by_group[group].append(task)

    group_order = [None, "A", "B", "C", "D", "Z"]

    for group in group_order:
        if group not in tasks_by_group:
            continue

        group_tasks = tasks_by_group[group]

        if group is not None:
            home_lines.append(f"# Layer {group}")
            home_lines.append("")

        for task in group_tasks:
            title = task.get("title", "")
            slug = task.get("slug", "")
            brief = task.get("brief", "")
            status = task.get("status")
            body = task.get("body", "")

            home_lines.append(f"## {title}")

            slug_line = f"[{slug}]"
            if status in ("active", "done", "pr-pending", "ready-to-merge"):
                slug_line += f" [{status}]"
            home_lines.append(slug_line)

            if brief:
                home_lines.append("")
                home_lines.append(brief)

            home_lines.append("")

            if body:
                sidebar_lines.append(f"[[{title}]](proposal-{slug}.md)")
                result[f"proposal-{slug}.md"] = body
            else:
                sidebar_lines.append(title)

        if group is not None:
            sidebar_lines.append("")

    home_content = "\n".join(home_lines)
    result["Home.md"] = home_content

    sidebar_content = "\n".join(sidebar_lines)
    result["_Sidebar.md"] = sidebar_content

    return result
