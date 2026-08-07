"""
Scraper for USTA tournament data.
"""
from datetime import datetime, timedelta
import logging
import time
import random
from typing import List, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_ENDPOINT = "https://prd-usta-kube.clubspark.pro/unified-search-api/api/Search/tournaments/Query?indexSchema=tournament"
DEFAULT_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
}
PAGE_SIZE = 100
DEFAULT_OPTIONS = {
    "size": PAGE_SIZE,
    "from": 0,
    "sortKey": "date",
    "latitude": 39.8283,  # Center of US
    "longitude": -98.5795,
}

logger = logging.getLogger(__name__)


def _search_params(page: int, page_size: int = PAGE_SIZE) -> Dict[str, Any]:
    """Build a fresh search payload for the given page."""
    today = datetime.now().date()
    return {
        "filters": [
            {
                "key": "distance",
                "items": [{"value": 5000}],  # Large value to get nationwide tournaments
            },
            {
                "key": "date-range",
                "items": [{
                    "minDate": today.strftime("%Y-%m-%d"),
                    "maxDate": (today + timedelta(days=365)).strftime("%Y-%m-%d"),
                }],
            },
        ],
        "options": {**DEFAULT_OPTIONS, "size": page_size, "from": page * page_size},
    }


def _session() -> requests.Session:
    """HTTP session with short retries on timeouts and 5xx responses."""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=(500, 502, 503, 504),
        allowed_methods=frozenset(["POST"]),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    return session


class USTAScraper:
    """Fetches tournament data from the USTA API with pagination and rate limiting."""

    def __init__(self):
        self.endpoint = API_ENDPOINT

    def fetch_tournaments(
        self, max_pages: int = 5, sleep_min: float = 2, sleep_max: float = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetch tournaments from the USTA API with pagination.

        Raises on request failure so callers do not persist a partial result set.
        """
        all_tournaments: List[Dict[str, Any]] = []
        logger.info("Starting USTA tournament fetch with max_pages=%s", max_pages)

        with _session() as session:
            for page in range(max_pages):
                params = _search_params(page)
                try:
                    response = session.post(self.endpoint, json=params, timeout=30)

                    if response.status_code == 204:
                        logger.info("No more tournaments found (204 No Content)")
                        break

                    response.raise_for_status()
                    data = response.json()

                    tournaments = [
                        result["item"]
                        for result in data.get("searchResults", [])
                        if result.get("item")
                    ]
                    all_tournaments.extend(tournaments)
                    logger.info("Page %s: Found %s tournaments", page + 1, len(tournaments))

                    if len(tournaments) < PAGE_SIZE:
                        logger.info("Reached end of results")
                        break

                    if page < max_pages - 1:
                        time.sleep(random.uniform(sleep_min, sleep_max))

                except requests.RequestException as e:
                    logger.error("Request error on page %s: %s", page + 1, e)
                    raise

        logger.info("Fetched %s total USTA tournaments", len(all_tournaments))
        return all_tournaments
