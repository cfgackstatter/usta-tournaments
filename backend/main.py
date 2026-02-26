"""
Main module for Tournament Map application.
"""
import argparse
import logging
import sys
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from backend.usta_scraper import USTAScraper
from backend.usta_data_manager import USTADataManager
from backend.itf_scraper import scrape_itf_months
from backend.itf_data_manager import ITFDataManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def update_usta_tournaments(max_pages: int = 10, sleep_min: float = 2, sleep_max: float = 5) -> bool:
    """Fetch and save USTA tournament data. Returns True on success."""
    logger.info(f"Starting USTA tournament update at {datetime.now()}")

    try:
        scraper = USTAScraper()
        data_manager = USTADataManager()

        # Log existing tournament count before update
        existing = data_manager.get_tournaments()
        logger.info(f"BEFORE UPDATE: {len(existing)} USTA tournaments in storage")

        tournaments = scraper.fetch_tournaments(max_pages, sleep_min, sleep_max)

        if not tournaments:
            logger.error("No USTA tournaments fetched")
            return False
        data_manager.save_tournaments(tournaments)
        logger.info(f"AFTER UPDATE: {len(tournaments)} USTA tournaments saved")
        return True

    except Exception as e:
        logger.error(f"USTA update failed: {e}", exc_info=True)
        return False
    

def update_itf_tournaments(months_back: int = 0, months_ahead: int = 3, sleep_min: float = 2, sleep_max: float = 5) -> bool:
    """Scrape and save ITF Masters Tour data. Returns True on success."""
    logger.info(f"Starting ITF tournament update at {datetime.now()}")
    try:
        today = date.today()
        months = []
        for delta in range(-months_back, months_ahead + 1):
            d = today + relativedelta(months=delta)
            months.append((d.year, d.month))

        data_manager = ITFDataManager()
        existing = data_manager.get_tournaments()
        logger.info(f"BEFORE UPDATE: {len(existing)} ITF tournaments in storage")

        # Load existing df for smart scrape skipping
        existing_df = data_manager.load_tournaments()

        # Group months by year and scrape each year's months together
        from itertools import groupby
        all_tournaments = []
        months.sort()
        for year, year_months in groupby(months, key=lambda x: x[0]):
            month_nums = [m for _, m in year_months]
            logger.info(f"Scraping ITF calendar for {year}, months: {month_nums}")
            all_tournaments.extend(
                scrape_itf_months(
                    year,
                    month_nums,
                    sleep_min=sleep_min,
                    sleep_max=sleep_max,
                    existing_df=existing_df,
                    data_manager=data_manager,
                )
            )

        if not all_tournaments:
            logger.error("No ITF tournaments fetched")
            return False

        logger.info(f"AFTER UPDATE: {len(all_tournaments)} ITF tournaments saved")
        return True
    except Exception as e:
        logger.error(f"ITF update failed: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(description="Tournament Map data updater")
    parser.add_argument("--update", action="store_true", help="Update both USTA and ITF tournament data")
    parser.add_argument("--update-usta", action="store_true", help="Update USTA tournament data only")
    parser.add_argument("--update-itf", action="store_true", help="Update ITF Masters Tour data only")
    parser.add_argument("--max-pages", type=int, default=5, help="Max pages for USTA fetch")
    parser.add_argument("--sleep-min", type=float, default=2, help="Min sleep between requests")
    parser.add_argument("--sleep-max", type=float, default=5, help="Max sleep between requests")
    parser.add_argument("--months-back", type=int, default=0, help="ITF: months back from today to scrape")
    parser.add_argument("--months-ahead", type=int, default=3, help="ITF: months ahead from today to scrape")

    args = parser.parse_args()

    if not any([args.update, args.update_usta, args.update_itf]):
        parser.print_help()
        return

    success = True

    if args.update or args.update_usta:
        ok = update_usta_tournaments(args.max_pages, args.sleep_min, args.sleep_max)
        if not ok:
            logger.error("USTA update failed")
            success = False

    if args.update or args.update_itf:
        ok = update_itf_tournaments(args.months_back, args.months_ahead, args.sleep_min, args.sleep_max)
        if not ok:
            logger.error("ITF update failed")
            success = False

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()