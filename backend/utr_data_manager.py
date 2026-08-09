"""
Data management for UTR tournament data using Parquet storage.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

DATA_DIR = Path(os.environ.get("APP_DATA_DIR", Path(__file__).parent.parent / "data"))
TOURNAMENTS_FILE = DATA_DIR / "utr_tournaments.parquet"

logger = logging.getLogger(__name__)


class UTRDataManager:
    """Manages UTR tournament data storage and retrieval using Parquet files."""

    def __init__(self):
        self.tournaments_file = Path(TOURNAMENTS_FILE)

    def save_tournaments(self, tournaments: List[Dict[str, Any]]) -> None:
        """Save UTR tournaments to Parquet file, replacing any existing data."""
        if not tournaments:
            logger.warning("No tournaments to save")
            return

        logger.info("Saving %s UTR tournaments", len(tournaments))

        now = datetime.now().isoformat()
        records = [
            {"id": str(t.get("id", "")), "data": json.dumps(t), "last_updated": now}
            for t in tournaments
        ]

        df = pd.DataFrame(records)
        self.tournaments_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.tournaments_file, engine="pyarrow", index=False)

        file_size_mb = self.tournaments_file.stat().st_size / (1024 * 1024)
        logger.info("Saved to %s (%.2f MB)", self.tournaments_file, file_size_mb)

    def get_freshness(self) -> Dict[str, Any]:
        """Return parquet file freshness (mtime-based)."""
        if not self.tournaments_file.exists():
            return {"available": False, "last_updated": None, "age_hours": None}
        mtime = self.tournaments_file.stat().st_mtime
        return {
            "available": True,
            "last_updated": datetime.fromtimestamp(mtime).isoformat(),
            "age_hours": round((datetime.now().timestamp() - mtime) / 3600, 2),
        }

    def get_tournaments(self) -> List[Dict[str, Any]]:
        """Load all UTR tournaments from Parquet file."""
        if not self.tournaments_file.exists():
            logger.warning("UTR tournaments file does not exist: %s", self.tournaments_file)
            return []

        file_age_hours = (
            datetime.now().timestamp() - self.tournaments_file.stat().st_mtime
        ) / 3600
        df = pd.read_parquet(self.tournaments_file)
        tournaments = [json.loads(row["data"]) for _, row in df.iterrows()]

        logger.info(
            "Loaded %s UTR tournaments from file (age: %.1f hours)",
            len(tournaments),
            file_age_hours,
        )
        return tournaments
