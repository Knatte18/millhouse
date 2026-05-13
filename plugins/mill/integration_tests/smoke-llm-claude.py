"""Smoke test for _llm_claude.run_bulk + run_tool_use + session reuse.

Local-dev only. Requires `claude` in PATH. Exits 0 on success, 1 on failure.

Run from hub root:
    python plugins/mill/integration_tests/smoke-llm-claude.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SCRATCH = HUB / ".scratch"
sys.path.insert(0, str(SCRIPTS))

import _llm_claude  # noqa: E402
import _safe_rmtree  # noqa: E402


PROMPT_BULK = """You are a review assistant. Evaluate the file content below.
If the file is a valid Python function definition, return verdict APPROVE.
Otherwise return verdict REQUEST_CHANGES.

Respond ONLY with a short YAML frontmatter block and a one-line summary. Exact format:

---
verdict: APPROVE
---

Looks good.

Do NOT include anything else. Do NOT use any tools.

--- FILE CONTENT ---

def greet(name: str) -> str:
    return f"Hello, {name}!"

--- END FILE CONTENT ---
"""


PROMPT_TOOL = """You are a review assistant with Read/Grep/Glob tool access.
Read the file at the path below. If it contains a valid Python function
definition, return verdict APPROVE. Otherwise return REQUEST_CHANGES.

Respond ONLY with a short YAML frontmatter block and a one-line summary. Exact format:

---
verdict: APPROVE
---

Looks good.

File to review: {path}
"""


PROMPT_SESSION_SEED = """Remember this fact for the rest of our conversation:
the secret codeword is ORANGUTAN-47.

Reply with exactly the single word: READY
Do not say anything else. Do not use any tools.
"""


PROMPT_SESSION_RECALL = """What was the secret codeword I told you earlier?

Reply with just the codeword on a single line. Nothing else.
Do not use any tools.
"""


def test_bulk() -> int:
    print("=" * 60, file=sys.stderr)
    print("TEST 1: run_bulk with inline file content", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    try:
        text, sid = _llm_claude.run_bulk(
            PROMPT_BULK,
            model="claude-sonnet-4-5",
            timeout=120,
        )
    except Exception as exc:
        print(f"FAIL: run_bulk raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("--- run_bulk returned ---", file=sys.stderr)
    print(text, file=sys.stderr)
    print(f"--- session_id: {sid} ---", file=sys.stderr)
    print("--- end run_bulk output ---", file=sys.stderr)

    if "verdict:" not in text.lower():
        print("FAIL: no verdict: in response", file=sys.stderr)
        return 1
    if not sid:
        print("FAIL: run_bulk did not return a session_id", file=sys.stderr)
        return 1
    print("PASS: run_bulk returned text + session_id\n", file=sys.stderr)
    return 0


def test_tool_use() -> int:
    print("=" * 60, file=sys.stderr)
    print("TEST 2: run_tool_use reading a real file via Read tool", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    SCRATCH.mkdir(parents=True, exist_ok=True)
    tmp = SCRATCH / f"mill-smoke-llm-{uuid.uuid4().hex[:8]}"
    tmp.mkdir()
    failed = False
    try:
        test_file = tmp / "sample.py"
        test_file.write_text(
            "def greet(name: str) -> str:\n"
            "    return f'Hello, {name}!'\n",
            encoding="utf-8",
        )

        prompt = PROMPT_TOOL.format(path=test_file)
        try:
            text, sid = _llm_claude.run_tool_use(
                prompt,
                model="claude-sonnet-4-5",
                timeout=180,
            )
        except Exception as exc:
            print(f"FAIL: run_tool_use raised {type(exc).__name__}: {exc}", file=sys.stderr)
            failed = True
            return 1

        print("--- run_tool_use returned ---", file=sys.stderr)
        print(text, file=sys.stderr)
        print(f"--- session_id: {sid} ---", file=sys.stderr)
        print("--- end run_tool_use output ---", file=sys.stderr)

        if "verdict:" not in text.lower():
            print("FAIL: no verdict: in response", file=sys.stderr)
            failed = True
            return 1
        if not sid:
            print("FAIL: run_tool_use did not return a session_id", file=sys.stderr)
            failed = True
            return 1
        print("PASS: run_tool_use returned text + session_id\n", file=sys.stderr)
        return 0
    finally:
        if failed:
            print(f"Scratch dir preserved for inspection: {tmp}", file=sys.stderr)
        else:
            _safe_rmtree.safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)


def test_session_reuse() -> int:
    """Seed a fact in one call, resume the session, ask claude to recall it.

    This is the hard prerequisite for mill-go's warm-implementer pattern:
    context must carry across `claude -p --resume <id>` calls. If this
    breaks, mill-go's whole design needs rethinking.
    """
    print("=" * 60, file=sys.stderr)
    print("TEST 3: session reuse across two run_bulk calls (--session-id, then --resume)",
          file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Seed turn: caller-supplied session id so we know what to resume.
    my_sid = str(uuid.uuid4())
    try:
        seed_text, seed_sid = _llm_claude.run_bulk(
            PROMPT_SESSION_SEED,
            model="claude-sonnet-4-5",
            timeout=120,
            session_id=my_sid,
        )
    except Exception as exc:
        print(f"FAIL: seed run_bulk raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"--- seed returned (sid={seed_sid}) ---", file=sys.stderr)
    print(seed_text, file=sys.stderr)

    if seed_sid != my_sid:
        print(f"FAIL: server-assigned sid {seed_sid!r} != caller sid {my_sid!r}",
              file=sys.stderr)
        return 1

    # Recall turn: resume the same session, ask for the codeword.
    try:
        recall_text, recall_sid = _llm_claude.run_bulk(
            PROMPT_SESSION_RECALL,
            model="claude-sonnet-4-5",
            timeout=120,
            session_id=my_sid,
            resume=True,
        )
    except _llm_claude.LLMSessionError as exc:
        print(f"FAIL: LLMSessionError on resume: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: resume run_bulk raised {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1

    print(f"--- recall returned (sid={recall_sid}) ---", file=sys.stderr)
    print(recall_text, file=sys.stderr)
    print("--- end recall output ---", file=sys.stderr)

    if "ORANGUTAN-47" not in recall_text.upper():
        print("FAIL: recalled text does not contain the seeded codeword 'ORANGUTAN-47'",
              file=sys.stderr)
        print("     session context did not carry across --resume.", file=sys.stderr)
        return 1

    print("PASS: session reuse carried the codeword across --resume\n", file=sys.stderr)
    return 0


def main() -> int:
    rc = 0
    rc |= test_bulk()
    rc |= test_tool_use()
    rc |= test_session_reuse()
    if rc == 0:
        print("OK — all LLM smoke tests passed")
    else:
        print("FAIL — at least one LLM smoke test failed")
    return rc


if __name__ == "__main__":
    sys.exit(main())
