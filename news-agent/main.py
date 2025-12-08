from __future__ import annotations

import logging
from typing import List, Optional

import typer

from src.config import get_settings
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
) -> None:
    settings = get_settings()
    pipeline = NewsAgentPipeline(settings)
    signals = pipeline.run(tokens)
    logging.info("Completed run; signals generated: %d", len(signals))


if __name__ == "__main__":
    app()

