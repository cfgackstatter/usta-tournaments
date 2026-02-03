"""
Main module for USTA Tournament Map application.
"""
import argparse
import logging
from datetime import datetime

from tournament_scraper import TournamentScraper
from data_manager import DataManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("usta_tournaments.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def update_tournaments(max_pages: int = 10, sleep_min: float = 2, sleep_max: float = 5) -> None:
    """Fetch and save tournament data from USTA API."""
    logger.info(f"Starting tournament update at {datetime.now()}")

    scraper = TournamentScraper()
    data_manager = DataManager()

    tournaments = scraper.fetch_tournaments(max_pages, sleep_min, sleep_max)

    if tournaments:
        data_manager.save_tournaments(tournaments)
        logger.info(f"Saved {len(tournaments)} tournaments")
    else:
        logger.warning("No tournaments fetched")

    logger.info(f"Update completed at {datetime.now()}")


def main():
    parser = argparse.ArgumentParser(description='USTA Tournament Map')
    parser.add_argument('--update', action='store_true', help='Update tournament data')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum pages to fetch')
    parser.add_argument('--sleep-min', type=float, default=2, help='Min sleep between requests')
    parser.add_argument('--sleep-max', type=float, default=5, help='Max sleep between requests')

    args = parser.parse_args()

    if args.update:
        update_tournaments(args.max_pages, args.sleep_min, args.sleep_max)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()