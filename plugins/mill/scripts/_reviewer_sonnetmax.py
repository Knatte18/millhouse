"""Bulk-mode reviewer using Claude Sonnet at max effort."""
from _llm_claude import run_bulk

MODE = "bulk"

def run(prompt_text: str) -> str:
    text, _ = run_bulk(prompt_text, model="claude-sonnet-4-6", effort="max")
    return text
