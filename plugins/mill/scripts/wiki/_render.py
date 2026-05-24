from __future__ import annotations


def render(tasks: list[dict]) -> dict[str, str]:
    result: dict[str, str] = {}

    home_lines: list[str] = ["# Tasks", ""]
    sidebar_groups: list[list[str]] = []

    tasks_by_group: dict[str | None, list[dict]] = {}
    for task in tasks:
        group = task.get("group")
        if group not in tasks_by_group:
            tasks_by_group[group] = []
        tasks_by_group[group].append(task)

    # Sort groups: A-Z alphabetically first, then None last; skip empty groups
    group_order = sorted([g for g in tasks_by_group.keys() if g is not None]) + ([None] if None in tasks_by_group else [])

    for group in group_order:
        group_tasks = tasks_by_group[group]
        # Sort tasks within group by id ascending for deterministic output
        group_tasks = sorted(group_tasks, key=lambda t: t.get("id", 0))

        if group is not None:
            home_lines.append(f"# Layer {group}")
            home_lines.append("")

        group_sidebar: list[str] = []
        for task in group_tasks:
            title = task.get("title", "")
            slug = task.get("slug", "")
            brief = task.get("brief", "")
            status = task.get("status")
            body = task.get("body", "")

            # Drop [s] status - treat as None
            if status == "s":
                status = None

            home_lines.append(f"## {title}")

            slug_line = f"[{slug}]"
            if status in ("active", "done", "pr-pending", "ready-to-merge", "abandoned"):
                slug_line += f" [{status}]"
            home_lines.append(slug_line)

            if brief:
                home_lines.append("")
                home_lines.append(brief)

            home_lines.append("")

            if body:
                group_sidebar.append(f"[[{title}]](proposal-{slug}.md)")
                result[f"proposal-{slug}.md"] = body
            else:
                group_sidebar.append(title)

        sidebar_groups.append(group_sidebar)

    home_content = "\n".join(home_lines)
    result["Home.md"] = home_content

    sidebar_lines: list[str] = []
    for i, group_sidebar in enumerate(sidebar_groups):
        sidebar_lines.extend(group_sidebar)
        if i < len(sidebar_groups) - 1:
            sidebar_lines.append("")

    sidebar_content = "\n".join(sidebar_lines)
    result["_Sidebar.md"] = sidebar_content

    return result
