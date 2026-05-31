from __future__ import annotations


def compute_layers(tasks: list[dict]) -> dict[str, str]:
    task_map = {t["slug"]: t for t in tasks}
    result: dict[str, str] = {}

    for task in tasks:
        slug = task["slug"]
        status = task.get("status")
        deferred = task.get("deferred", False)
        isolated = task.get("isolated", False)

        if status == "done":
            result[slug] = "__done__"
        elif deferred:
            result[slug] = "__deferred__"
        elif isolated:
            result[slug] = "Z"
        else:
            result[slug] = None

    if None not in result.values():
        return result

    color = {slug: "white" for slug in task_map}

    def visit(slug: str, path: list[str]) -> None:
        if color[slug] == "black":
            return
        if color[slug] == "gray":
            raise ValueError(f"cycle detected: {' -> '.join(path)}")

        color[slug] = "gray"
        path_with_current = path + [slug]
        task = task_map[slug]
        depends_on = task.get("depends_on", [])
        for dep_slug in depends_on:
            if dep_slug not in task_map:
                continue
            dep_task = task_map[dep_slug]
            if dep_task.get("status") == "done":
                continue
            visit(dep_slug, path_with_current)
        color[slug] = "black"

    for slug in task_map:
        if color[slug] == "white" and result[slug] is None:
            visit(slug, [])

    def get_topo_level(slug: str, memo: dict[str, int]) -> int:
        if slug in memo:
            return memo[slug]
        task = task_map[slug]
        depends_on = task.get("depends_on", [])
        effective_deps = [
            d for d in depends_on
            if d in task_map and task_map[d].get("status") != "done"
        ]
        if not effective_deps:
            level = 0
        else:
            level = 1 + max(get_topo_level(d, memo) for d in effective_deps)
        memo[slug] = level
        return level

    memo: dict[str, int] = {}
    for task in tasks:
        slug = task["slug"]
        if result[slug] is None:
            level = get_topo_level(slug, memo)
            if level >= 25:
                raise ValueError("layer depth exceeds A..Y cap")
            result[slug] = chr(ord("A") + level)

    return result


def extended_title(task: dict) -> str:
    title = task.get("title", "")
    if task.get("status") == "done" or task.get("deferred", False):
        return title
    layer = task.get("layer")
    if layer and layer not in ("__deferred__", "__done__"):
        return f"{title} [{layer}]"
    return title


def render_order(tasks: list[dict]) -> list[dict]:
    layers = compute_layers(tasks)
    for task in tasks:
        task["layer"] = layers[task["slug"]]

    letter_order = "ABCDEFGHIJKLMNOPQRSTUVWXY"
    bucket_order = list(letter_order) + ["Z", "__deferred__", "__done__"]

    def sort_key(task: dict) -> tuple:
        layer = task.get("layer", "")
        try:
            bucket_index = bucket_order.index(layer)
        except ValueError:
            bucket_index = len(bucket_order)
        task_id = task.get("id", 0)
        return (bucket_index, task_id)

    return sorted(tasks, key=sort_key)


def render(tasks: list[dict]) -> dict[str, str]:
    result: dict[str, str] = {}

    home_lines: list[str] = ["# Tasks", ""]
    sidebar_groups: list[list[str]] = []

    # Bucket tasks: done tasks go to a separate "done" pseudo-group regardless of
    # their original layer; everything else is bucketed by `group` (None = unspecified).
    tasks_by_bucket: dict[str | None, list[dict]] = {}
    for task in tasks:
        bucket = "__done__" if task.get("status") == "done" else task.get("group")
        if bucket not in tasks_by_bucket:
            tasks_by_bucket[bucket] = []
        tasks_by_bucket[bucket].append(task)

    # Render order: letter layers (A-Z) first, then Unspecified, then Done.
    letter_buckets = sorted(
        b for b in tasks_by_bucket if b is not None and b != "__done__"
    )
    bucket_order: list[str | None] = list(letter_buckets)
    if None in tasks_by_bucket:
        bucket_order.append(None)
    if "__done__" in tasks_by_bucket:
        bucket_order.append("__done__")

    for bucket in bucket_order:
        bucket_tasks = tasks_by_bucket[bucket]
        # Sort tasks within bucket by id ascending for deterministic output
        bucket_tasks = sorted(bucket_tasks, key=lambda t: t.get("id", 0))

        if bucket == "__done__":
            home_lines.append("# Done")
            home_lines.append("")
        elif bucket is None:
            home_lines.append("# Unspecified")
            home_lines.append("")
        else:
            home_lines.append(f"# Layer {bucket}")
            home_lines.append("")

        group_sidebar: list[str] = []
        for task in bucket_tasks:
            title = task.get("title", "")
            slug = task.get("slug", "")
            brief = task.get("brief", "")
            status = task.get("status")
            body = task.get("body", "")
            task_id = task.get("id")
            task_group = task.get("group")

            # Drop [s] status - treat as None
            if status == "s":
                status = None

            # Format: "**#<zero-padded-id>:** <title> [<group>]". Group uses the
            # task's own group, not the bucket, so done-tasks keep their origin marker.
            id_prefix = f"**#{task_id:03d}:**" if task_id is not None else ""
            group_suffix = f"[{task_group}]" if task_group is not None else ""
            display_title = " ".join(p for p in (id_prefix, title, group_suffix) if p)

            home_lines.append(f"## {display_title}")

            if body:
                slug_line = f"[{slug}](proposal-{slug}.md)"
            else:
                slug_line = f"[{slug}]"
            if status in ("active", "done", "pr-pending", "ready-to-merge", "abandoned"):
                slug_line += f" [{status}]"
            home_lines.append(slug_line)

            if brief:
                home_lines.append("")
                home_lines.append(brief)

            home_lines.append("")

            if body:
                group_sidebar.append(f"- [{display_title}](proposal-{slug}.md)")
                result[f"proposal-{slug}.md"] = body
            else:
                group_sidebar.append(f"- {display_title}")

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
