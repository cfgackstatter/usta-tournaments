"""
Data management for USTA tournament data using Parquet storage.
"""
import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import pandas as pd
import os


DATA_DIR = Path(os.environ.get("APP_DATA_DIR", Path(__file__).parent.parent / "data"))
TOURNAMENTS_FILE = DATA_DIR / "usta_tournaments.parquet"

logger = logging.getLogger(__name__)


class USTADataManager:
    """Manages USTA tournament data storage and retrieval using Parquet files."""


    def __init__(self):
        self.tournaments_file = Path(TOURNAMENTS_FILE)


    def save_tournaments(self, tournaments: List[Dict[str, Any]]) -> None:
        """
        Save USTA tournaments to Parquet file, replacing any existing data.

        Args:
            tournaments: List of tournament dictionaries from the API
        """
        if not tournaments:
            logger.warning("No tournaments to save")
            return

        logger.info(f"Saving {len(tournaments)} USTA tournaments")

        # Store full API data as JSON string along with timestamp
        now = datetime.now().isoformat()
        records = [
            {"id": t.get("id", ""), "data": json.dumps(t), "last_updated": now}
            for t in tournaments
        ]

        df = pd.DataFrame(records)
        self.tournaments_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.tournaments_file, engine='pyarrow', index=False)

        file_size_mb = self.tournaments_file.stat().st_size / (1024 * 1024)
        logger.info(f"Saved to {self.tournaments_file} ({file_size_mb:.2f} MB)")


    def get_tournaments(self) -> List[Dict[str, Any]]:
        """
        Load all USTA tournaments from Parquet file.

        Returns:
            List of USTA tournament dictionaries
        """
        if not self.tournaments_file.exists():
            logger.warning(f"USTA tournaments file does not exist: {self.tournaments_file}")
            return []

        file_age_hours = (datetime.now().timestamp() - self.tournaments_file.stat().st_mtime) / 3600
        df = pd.read_parquet(self.tournaments_file)
        tournaments = [json.loads(row['data']) for _, row in df.iterrows()]

        logger.info(f"Loaded {len(tournaments)} USTA tournaments from file (age: {file_age_hours:.1f} hours)")
        return tournaments
