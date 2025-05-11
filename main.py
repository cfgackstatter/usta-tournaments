"""
Main module for USTA Tournament Map application.

This module provides command-line functionality for updating tournament data
and launching the web application.
"""
import os
import argparse
import logging
from typing import Optional
from datetime import datetime

from scraper.tournament_scraper import TournamentScraper
from data.data_manager import DataManager
from webapp.app import TournamentApp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("usta_tournaments.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def update_tournaments(max_pages: int = 5, sleep_min: float = 2, sleep_max: float = 5) -> None:
    """
    Update tournament data from the USTA API.
    
    Fetches tournament data from the USTA API and saves it to the data store.
    
    Args:
        max_pages: Maximum number of pages to fetch
        sleep_min: Minimum sleep time between requests (seconds)
        sleep_max: Maximum sleep time between requests (seconds)
    
    Returns:
        None
    """
    logger.info(f"Starting tournament update at {datetime.now()}")
    
    # Initialize scraper and data manager
    scraper = TournamentScraper()
    data_manager = DataManager()
    
    # Fetch tournaments
    tournaments = scraper.fetch_tournaments(max_pages, sleep_min, sleep_max)
    
    # Save tournaments to Parquet file
    if tournaments:
        data_manager.save_tournaments(tournaments)
        logger.info(f"Saved {len(tournaments)} tournaments to Parquet file")
    else:
        logger.warning("No tournaments fetched")
    
    logger.info(f"Tournament update completed at {datetime.now()}")

def run_webapp() -> None:
    """
    Run the Streamlit web application.
    
    Initializes and launches the Streamlit web interface for browsing tournaments.
    
    Returns:
        None
    """
    logger.info("Starting web application")
    app = TournamentApp()
    app.run()

def main() -> None:
    """
    Main entry point for the application.
    
    Parses command-line arguments and executes the appropriate functionality.
    
    Returns:
        None
    """
    parser = argparse.ArgumentParser(description='USTA Tournament Map')
    parser.add_argument('--update', action='store_true', help='Update tournament data')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum number of pages to fetch')
    parser.add_argument('--sleep-min', type=float, default=2, help='Minimum sleep time between requests')
    parser.add_argument('--sleep-max', type=float, default=5, help='Maximum sleep time between requests')
    parser.add_argument('--webapp', action='store_true', help='Run the web application')
    
    args = parser.parse_args()
    
    if args.update:
        update_tournaments(args.max_pages, args.sleep_min, args.sleep_max)
    
    if args.webapp:
        run_webapp()
    
    # If no arguments provided, show help
    if not (args.update or args.webapp):
        parser.print_help()

if __name__ == "__main__":
    main()