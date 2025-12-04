from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class SnapshotRecord:
    user_id: int
    payload: Dict[str, Any]
    source: Path


class SnapshotLoader:
    """
    Loads JSON or TOON snapshots produced by fetch-data-agent.
    Currently JSON is implemented; TOON is stubbed for future use.
    """

    def __init__(self, snapshot_dir: Path):
        self.snapshot_dir = Path(snapshot_dir)

    def _json_path(self, user_id: int) -> Path:
        return self.snapshot_dir / f"user_{user_id}.json"

    def _toon_path(self, user_id: int) -> Path:
        return self.snapshot_dir / f"user_{user_id}.toon"

    def load_json_snapshot(self, user_id: int) -> Optional[SnapshotRecord]:
        path = self._json_path(user_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
        return SnapshotRecord(user_id=user_id, payload=payload, source=path)

    def load_toon_snapshot(self, user_id: int) -> Optional[SnapshotRecord]:
        """
        Placeholder for TOON decoding.
        """
        path = self._toon_path(user_id)
        if not path.exists():
            return None

        raise NotImplementedError(
            "TOON decoding not implemented yet. Convert the binary file to JSON or implement decoder."
        )

