from __future__ import annotations

import logging

import typer

from src.config import RulesAgentSettings, get_settings
from src.pipeline import RulesAgentPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

app = typer.Typer(add_completion=False)


@app.command("run")
def run(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    settings = get_settings()
    if dry_run:
        settings = settings.model_copy(update={"dry_run": True})
    pipeline = RulesAgentPipeline(settings)
    pipeline.run()


if __name__ == "__main__":
    app()

