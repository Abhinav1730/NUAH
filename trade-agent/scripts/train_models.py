from __future__ import annotations

import argparse
import logging
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings
from src.models.trainer import MLTrainer, TrainingConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train ML models for trade-agent.")
    parser.add_argument("--data-dir", type=str, help="Override data directory path.")
    parser.add_argument("--models-dir", type=str, help="Override models directory path.")
    return parser.parse_args()


def main() -> None:
    settings = get_settings()
    args = parse_args()
    data_dir = Path(args.data_dir) if args.data_dir else settings.data_dir
    models_dir = Path(args.models_dir) if args.models_dir else settings.models_dir
    trainer = MLTrainer(TrainingConfig(data_dir=data_dir, models_dir=models_dir))
    trainer.run()


if __name__ == "__main__":
    main()

