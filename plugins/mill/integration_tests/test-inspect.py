"""
Integration test for millpy-inspect.py.

Builds a hub+wiki fixture under .scratch/ with two active slugs and verifies
default output, single-slug filter, unknown-slug error, --json schema,
--since filter, no-active case, and [WARN] home-marker detection.

Run from hub root:
    python plugins/mill/integration_tests/test-inspect.py

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
    _run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "-C", str(repo), "config", "user.name", "Test"], cwd=repo)
    (repo / ".keep").write_text("", encoding="utf-8")
    _run(["git", "-C", str(repo), "add", ".keep"], cwd=repo)
    _run(["git", "-C", str(repo), "commit", "-m", "init"], cwd=repo)


def _write_status(path: Path, slug: str, phase: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = "2026-04-24T10:00:00Z"
    content = _status.render_initial(
        task_title=f"Task {slug}",
        task_description=f"Desc for {slug}.",
        timestamp=ts,
        parent_branch="main",
        slug=slug,
        branch=f"hanf/{slug}",
    )
    path.write_text(content, encoding="utf-8")
    if phase != "discussing":
        _status.append_phase(path, phase, "2026-04-24T11:00:00Z")


def _setup_fixture(container: Path) -> tuple[Path, Path]:
    container.mkdir(parents=True, exist_ok=True)
    wiki = container / "wiki"
    hub = container / "hub"
    wiki.mkdir()
    _git_init(wiki)
    hub.mkdir()
    _git_init(hub)

    # slug-alpha: implementing
    _write_status(wiki / "active" / "slug-alpha" / "status.md", "slug-alpha", "implementing")
    # slug-beta: discussing
    _write_status(wiki / "active" / "slug-beta" / "status.md", "slug-beta", "discussing")

    home_md = (
        "# Tasks\n\n"
        "## Alpha task [slug-alpha] [active]\n\n"
        "## Beta task [slug-beta] [active]\n\n"
    )
    (wiki / "Home.md").write_text(home_md, encoding="utf-8")

    _run(["git", "-C", str(wiki), "add", "."], cwd=wiki)
    _run(["git", "-C", str(wiki), "commit", "-m", "seed"], cwd=wiki)

    (hub / ".millhouse").mkdir(exist_ok=True)
    (hub / ".millhouse" / "config.local.yaml").write_text(
        f"paths:\n  wiki: {wiki.as_posix()}\n", encoding="utf-8"
    )
    return hub, wiki


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    container = SCRATCH / f"test-inspect-{ts}"
    failed = False
    script = SCRIPTS / "millpy-inspect.py"

    try:
        hub, wiki = _setup_fixture(container)
        print(f"[test-inspect] container: {container}", file=sys.stderr)

        # --- all slugs ---
        r = _run([sys.executable, str(script)], cwd=hub, check=False)
        assert r.returncode == 0, f"all-slugs exit={r.returncode}\n{r.stderr}"
        assert "## slug-alpha" in r.stdout, "slug-alpha heading missing"
        assert "## slug-beta" in r.stdout, "slug-beta heading missing"
        assert "implementing" in r.stdout, "phase 'implementing' missing"
        assert "discussing" in r.stdout, "phase 'discussing' missing"
        assert "Timeline:" in r.stdout, "Timeline section missing"
        print("PASS: all-slugs — both headings + phases + Timeline present")

        # --- single slug ---
        r = _run([sys.executable, str(script), "slug-alpha"], cwd=hub, check=False)
        assert r.returncode == 0, f"single-slug exit={r.returncode}\n{r.stderr}"
        assert "## slug-alpha" in r.stdout, "slug-alpha heading missing in single-slug run"
        assert "## slug-beta" not in r.stdout, "slug-beta should be absent in single-slug run"
        print("PASS: single-slug — only slug-alpha in output")

        # --- unknown slug ---
        r = _run([sys.executable, str(script), "no-such-slug"], cwd=hub, check=False)
        assert r.returncode == 1, f"unknown-slug should exit 1, got {r.returncode}"
        print("PASS: unknown-slug — exit code 1")

        # --- --json schema ---
        r = _run([sys.executable, str(script), "--json"], cwd=hub, check=False)
        assert r.returncode == 0, f"--json exit={r.returncode}\n{r.stderr}"
        data = json.loads(r.stdout)
        for slug in ("slug-alpha", "slug-beta"):
            assert slug in data, f"{slug} missing from --json output"
            entry = data[slug]
            assert "status" in entry, f"{slug}: 'status' key missing"
            assert "timeline" in entry, f"{slug}: 'timeline' key missing"
            assert "worktree" in entry, f"{slug}: 'worktree' key missing"
            assert "home_marker" in entry, f"{slug}: 'home_marker' key missing"
            assert isinstance(entry["status"], dict), f"{slug}: status should be dict"
            assert isinstance(entry["timeline"], list), f"{slug}: timeline should be list"
        assert data["slug-alpha"]["status"]["phase"] == "implementing", (
            f"slug-alpha phase: {data['slug-alpha']['status']['phase']!r}"
        )
        assert data["slug-alpha"]["home_marker"] == "active", (
            f"slug-alpha home_marker: {data['slug-alpha']['home_marker']!r}"
        )
        print("PASS: --json — schema shape, phase, home_marker correct")

        # --- --since filter ---
        r = _run([sys.executable, str(script), "--since", "planned"], cwd=hub, check=False)
        assert r.returncode == 0, f"--since exit={r.returncode}\n{r.stderr}"
        assert "## slug-alpha" in r.stdout, "slug-alpha should pass --since planned"
        assert "## slug-beta" not in r.stdout, "slug-beta (discussing) should be filtered by --since planned"
        print("PASS: --since planned — implementing passes, discussing filtered")

        # --- no active tasks ---
        shutil.rmtree(str(wiki / "active"), ignore_errors=True)
        (wiki / "active").mkdir()
        r = _run([sys.executable, str(script)], cwd=hub, check=False)
        assert r.returncode == 0, f"no-active exit={r.returncode}\n{r.stderr}"
        assert "(no active tasks)" in r.stdout, f"expected '(no active tasks)', got: {r.stdout!r}"
        print("PASS: no-active — exit 0, '(no active tasks)' printed")

        # --- [WARN] home_marker ---
        # Restore slug-alpha with a done marker in Home.md
        _write_status(wiki / "active" / "slug-alpha" / "status.md", "slug-alpha", "implementing")
        warn_home = (
            "# Tasks\n\n"
            "## Alpha task [slug-alpha] [done]\n\n"
        )
        (wiki / "Home.md").write_text(warn_home, encoding="utf-8")
        r = _run([sys.executable, str(script)], cwd=hub, check=False)
        assert r.returncode == 0, f"warn-marker exit={r.returncode}\n{r.stderr}"
        assert "[WARN]" in r.stdout, f"[WARN] not found in output: {r.stdout!r}"
        assert "done" in r.stdout, f"marker value 'done' not in output: {r.stdout!r}"
        print("PASS: [WARN] home_marker — drift detected and flagged")

        print("All test-inspect assertions passed.")
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
