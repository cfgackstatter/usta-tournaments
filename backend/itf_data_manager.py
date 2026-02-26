"""
Data management for ITF Masters Tour tournament data using Parquet storage.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import os


DATA_DIR = Path(os.environ.get("APP_DATA_DIR", Path(__file__).parent.parent / "data"))
ITF_FILE = DATA_DIR / "itf_tournaments.parquet"

logger = logging.getLogger(__name__)


class ITFDataManager:
    """Manages ITF Masters Tour tournament data using Parquet storage."""

    def __init__(self):
        self.tournaments_file = Path(ITF_FILE)

    def save_tournaments(self, tournaments: List[Dict[str, Any]]) -> None:
        """Upsert tournaments by tournamentKey, dropping any that have already ended."""
        if not tournaments:
            logger.warning("No ITF tournaments to save")
            return

        today = date.today().isoformat()
        now = datetime.now().isoformat()
        
        filtered = [t for t in tournaments if t.get("endDate", "9999") >= today]
        if not filtered:
            logger.warning("No ITF tournaments to save after filtering")
            return
        
        new_df = pd.DataFrame({**t, "last_updated": now} for t in filtered)

        if self.tournaments_file.exists():
            existing_df = pd.read_parquet(self.tournaments_file)
            existing_df = existing_df[
                (existing_df["endDate"] >= today) &
                (~existing_df["tournamentKey"].isin(new_df["tournamentKey"]))
            ]
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        self.tournaments_file.parent.mkdir(parents=True, exist_ok=True)
        combined_df.to_parquet(self.tournaments_file, engine="pyarrow", index=False)
        size_mb = self.tournaments_file.stat().st_size / (1024 * 1024)
        logger.info(f"Saved {len(new_df)} ITF tournaments ({len(combined_df)} total) to {self.tournaments_file} ({size_mb:.2f} MB)")

    def get_tournaments(self) -> List[Dict[str, Any]]:
        if not self.tournaments_file.exists():
            logger.warning(f"ITF tournaments file does not exist: {self.tournaments_file}")
            return []
        df = pd.read_parquet(self.tournaments_file)
        file_age_hours = (datetime.now().timestamp() - self.tournaments_file.stat().st_mtime) / 3600
        logger.info(f"Loaded {len(df)} ITF tournaments (age: {file_age_hours:.1f} hours)")
        return df.where(pd.notna(df), other=None).to_dict(orient="records")
    
    def load_tournaments(self) -> pd.DataFrame:
        """Load existing tournaments as a DataFrame for incremental scraping."""
        if not self.tournaments_file.exists():
            return pd.DataFrame()
        return pd.read_parquet(self.tournaments_file)