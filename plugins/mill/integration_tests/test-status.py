"""
Integration test for millpy-status.py.

Builds a hub+wiki fixture under .scratch/ with five slug scenarios and
verifies plain, --json, --sort phase, and main-worktree-guard runs.

Run from hub root:
    python plugins/mill/integration_tests/test-status.py

Exits 0 on PASS, 1 on any failure (scratch dir preserved for inspection).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"

sys.path.insert(0, str(SCRIPTS))
import _status


def _run(cmd: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _git_init(repo: Path) -> None:
    _run(["git", "init", "-b", "main", str(repo)], cwd=repo.parent)
    _run(["git", "-C", str(repo), "symbolic-ref", "HEAD", "refs/heads/main"],
         cwd=repo, check=False)
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "-C", str(repo), "config", "user.name", "Test"], cwd=repo)
    (repo / ".keep").write_text("", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", ".keep"], cwd=repo)
    _run(["git", "-C", str(repo), "commit", "-m", "init"], cwd=repo)


def _write_rendered_status(path: Path, slug: str, phase: str = "discussing") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = "2026-04-24T10:00:00Z"
    content = _status.render_initial(
        task_title=f"Task for {slug}",
        task_description=f"Description for {slug}.",
        timestamp=ts,
        parent_branch="main",
        slug=slug,
        branch=f"hanf/{slug}",
    )
    # Update phase if not discussing
    if phase != "discussing":
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        _status.append_phase(tmp_path, phase, "2026-04-24T11:00:00Z")
        content = tmp_path.read_text(encoding="utf-8")
        tmp_path.unlink()
    path.write_text(content, encoding="utf-8")


def _setup_fixture(container: Path) -> tuple[Path, Path]:
    container.mkdir(parents=True, exist_ok=True)
    wiki = container / "wiki"
    hub = container / "hub"
    worktrees_dir = container / "worktrees"
    worktrees_dir.mkdir()

    # Wiki repo (no bare; local only)
    wiki.mkdir()
    _git_init(wiki)

    # Hub repo
    hub.mkdir()
    _git_init(hub)

    # Five slugs:
    # 1. slug-alpha: [active] in Home.md + active-dir + worktree
    _write_rendered_status(wiki / "active" / "slug-alpha" / "status.md", "slug-alpha", "implementing")

    # 2. slug-beta: [done] in Home.md + active-dir + no worktree
    _write_rendered_status(wiki / "active" / "slug-beta" / "status.md", "slug-beta", "discussing")

    # 3. slug-gamma: [active] in Home.md + active-dir + no worktree → WT?
    _write_rendered_status(wiki / "active" / "slug-gamma" / "status.md", "slug-gamma", "discussing")

    # 4. slug-delta: active-dir + no Home.md entry + no worktree → HM?
    _write_rendered_status(wiki / "active" / "slug-delta" / "status.md", "slug-delta", "discussing")

    # 5. slug-echo: Home.md entry only, no phase bracket → unclaimed, no active-dir
    # (no status.md created)

    # Home.md
    home_md = (
        "# Tasks\n\n"
        "## Alpha task [slug-alpha] [active]\n\n"
        "## Beta task [slug-beta] [done]\n\n"
        "## Gamma task [slug-gamma] [active]\n\n"
        "## Echo task [slug-echo]\n\n"
    )
    (wiki / "Home.md").write_text(home_md, encoding="utf-8")

    _run(["git", "-C", str(wiki), "add", "."], cwd=wiki)
    _run(["git", "-C", str(wiki), "commit", "-m", "seed"], cwd=wiki)

    # Worktree for slug-alpha only
    _run(["git", "-C", str(hub), "worktree", "add", "-b", "impl/slug-alpha",
          str(worktrees_dir / "slug-alpha")], cwd=hub)

    # .millhouse config pointing to wiki
    millhouse = hub / ".millhouse"
    millhouse.mkdir(exist_ok=True)
    (millhouse / "config.local.yaml").write_text(
        f"paths:\n  wiki: {wiki.as_posix()}\n", encoding="utf-8"
    )

    return hub, wiki


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    container = SCRATCH / f"test-status-{ts}"
    failed = False

    try:
        hub, wiki = _setup_fixture(container)
        print(f"[test-status] container: {container}", file=sys.stderr)

        script = SCRIPTS / "millpy-status.py"

        # --- Assertion group 1: plain run ---
        r = _run([sys.executable, str(script), "--no-color"], cwd=hub, check=False)
        assert r.returncode == 0, f"plain run exit={r.returncode}\n{r.stderr}"
        for slug in ["slug-alpha", "slug-beta", "slug-gamma", "slug-delta", "slug-echo"]:
            assert slug in r.stdout, f"slug {slug} missing from plain output"
        assert "WT?" in r.stdout, "expected WT? flag in plain output"
        assert "HM?" in r.stdout, "expected HM? flag in plain output"
        # slug-alpha should show worktree path (not "-")
        lines = r.stdout.splitlines()
        alpha_line = next((l for l in lines if "slug-alpha" in l), None)
        assert alpha_line is not None, "slug-alpha row missing"
        # slug-echo phase column should show —
        echo_line = next((l for l in lines if "slug-echo" in l), None)
        assert echo_line is not None, "slug-echo row missing"
        assert "\u2014" in echo_line, f"expected — in slug-echo row: {echo_line!r}"
        print("PASS: plain run — all slugs present, WT?/HM? flags, slug-echo shows —")

        # --- Assertion group 2: --json run ---
        r = _run([sys.executable, str(script), "--json"], cwd=hub, check=False)
        assert r.returncode == 0, f"--json exit={r.returncode}\n{r.stderr}"
        rows = json.loads(r.stdout)
        by_slug = {row["slug"]: row for row in rows}
        for slug in ["slug-alpha", "slug-beta", "slug-gamma", "slug-delta", "slug-echo"]:
            assert slug in by_slug, f"slug {slug} missing from --json output"
        assert by_slug["slug-gamma"]["marker_flag"] == "WT?", (
            f"slug-gamma marker_flag: {by_slug['slug-gamma']['marker_flag']!r}"
        )
        assert by_slug["slug-delta"]["marker_flag"] == "HM?", (
            f"slug-delta marker_flag: {by_slug['slug-delta']['marker_flag']!r}"
        )
        echo = by_slug["slug-echo"]
        assert echo["phase"] is None, f"slug-echo phase should be null: {echo['phase']!r}"
        assert echo["marker_flag"] == "", f"slug-echo marker_flag: {echo['marker_flag']!r}"
        assert echo["marker"] == "unclaimed", f"slug-echo marker: {echo['marker']!r}"
        alpha = by_slug["slug-alpha"]
        assert alpha["worktree_path"] not in ("-", None), (
            f"slug-alpha worktree_path should be set: {alpha['worktree_path']!r}"
        )
        assert alpha["last_timeline_entry"] is not None, (
            "slug-alpha last_timeline_entry should be non-null (render_initial writes Timeline)"
        )
        print("PASS: --json run — slugs/marker_flags/phase/worktree/timeline assertions")

        # --- Assertion group 3: --sort phase ---
        r = _run([sys.executable, str(script), "--no-color", "--sort", "phase"],
                 cwd=hub, check=False)
        assert r.returncode == 0, f"--sort phase exit={r.returncode}\n{r.stderr}"
        assert r.stdout.strip(), "--sort phase produced empty output"
        print("PASS: --sort phase — exit 0, non-empty output")

        # --- Assertion group 4: main worktree guard ---
        r = _run([sys.executable, str(script), "--json"], cwd=hub, check=False)
        rows = json.loads(r.stdout)
        slugs = [row["slug"] for row in rows]
        assert "main" not in slugs, f"'main' slug must not appear in --json output: {slugs}"
        print("PASS: main worktree guard — no 'main' slug in --json output")

        print("All test-status assertions passed.")
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        failed = True

    if not failed:
        shutil.rmtree(container, ignore_errors=True)
    else:
        print(f"Fixture preserved at: {container}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
