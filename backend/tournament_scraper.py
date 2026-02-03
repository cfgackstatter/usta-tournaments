"""
Tournament scraper for fetching USTA tournament data.
"""
from datetime import datetime, timedelta
import logging
import time
import random
from typing import List, Dict, Any
import requests

API_ENDPOINT = "https://prd-usta-kube.clubspark.pro/unified-search-api/api/Search/tournaments/Query?indexSchema=tournament"
DEFAULT_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}
DEFAULT_SEARCH_PARAMS = {
    "filters": [
        {
            "key": "distance",
            "items": [{"value": 5000}]  # Large value to get nationwide tournaments
        },
        {
            "key": "date-range",
            "items": [{
                "minDate": datetime.now().strftime("%Y-%m-%d"),
                "maxDate": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
            }]
        }
    ],
    "options": {
        "size": 100,
        "from": 0,
        "sortKey": "date",
        "latitude": 39.8283,  # Center of US
        "longitude": -98.5795
    }
}

logger = logging.getLogger(__name__)

class TournamentScraper:
    """Fetches tournament data from the USTA API with pagination and rate limiting."""

    def __init__(self):
        self.endpoint = API_ENDPOINT
        self.headers = DEFAULT_HEADERS
        self.default_params = DEFAULT_SEARCH_PARAMS

    def fetch_tournaments(self, max_pages: int = 5, sleep_min: float = 2, sleep_max: float = 5) -> List[Dict[str, Any]]:
        """
        Fetch tournaments from the USTA API with pagination.

        Args:
            max_pages: Maximum number of pages to fetch
            sleep_min: Minimum sleep time between requests (seconds)
            sleep_max: Maximum sleep time between requests (seconds)

        Returns:
            List of tournament dictionaries
        """
        all_tournaments = []
        page_size = self.default_params['options']['size']

        logger.info(f"Starting tournament fetch with max_pages={max_pages}")

        for page in range(max_pages):
            params = self.default_params.copy()
            params['options']['from'] = page * page_size

            try:
                response = requests.post(self.endpoint, json=params, headers=self.headers, timeout=30)

                if response.status_code == 204:
                    logger.info("No more tournaments found (204 No Content)")
                    break

                response.raise_for_status()
                data = response.json()

                # Extract tournament items from search results
                tournaments = [result['item'] for result in data.get('searchResults', []) if result.get('item')]
                all_tournaments.extend(tournaments)

                logger.info(f"Page {page + 1}: Found {len(tournaments)} tournaments")

                # Stop if we received fewer items than page size
                if len(tournaments) < page_size:
                    logger.info("Reached end of results")
                    break

                # Rate limiting
                if page < max_pages - 1:  # Don't sleep after last page
                    time.sleep(random.uniform(sleep_min, sleep_max))

            except requests.RequestException as e:
                logger.error(f"Request error on page {page + 1}: {e}")
                break

        logger.info(f"Fetched {len(all_tournaments)} total tournaments")
        return all_tournaments