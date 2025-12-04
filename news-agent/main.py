from __future__ import annotations

import logging
from typing import List, Optional

import typer

from src.config import NewsAgentSettings, get_settings
from src.pipeline import NewsAgentPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

app = typer.Typer(add_completion=False)


@app.command("run")
def run(
    tokens: Optional[List[str]] = typer.Argument(
        None, help="Optional list of token mint addresses to analyze."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Skip OpenRouter calls and synthesize deterministic outputs.",
    ),
) -> None:
    settings = get_settings()
    if dry_run:
        settings = settings.model_copy(update={"dry_run": True})
    pipeline = NewsAgentPipeline(settings)
    pipeline.run(tokens)


if __name__ == "__main__":
    app()

