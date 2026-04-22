"""Bulk-mode reviewer using Claude Sonnet at max effort."""
from _llm_claude import run_bulk

MODE = "bulk"

def run(prompt_text: str) -> str:
    text, _ = run_bulk(prompt_text, model="claude-sonnet-4-6", effort="max")
    return text


if __name__ == "__main__":
    assert MODE == "bulk", f"Expected MODE='bulk', got {MODE!r}"
    assert callable(run), "run must be callable"
    print("PASS: MODE == 'bulk'")
    print("PASS: run is callable")
    print("All smoke tests passed.")
