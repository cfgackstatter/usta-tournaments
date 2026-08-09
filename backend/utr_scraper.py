"""
Scraper for UTR Sports tournament data (app.utrsports.net search API).
"""
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_ENDPOINT = "https://api.utrsports.net/v2/search/events"
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": "https://app.utrsports.net/",
    "Origin": "https://app.utrsports.net",
}
PAGE_SIZE = 200

logger = logging.getLogger(__name__)


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
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    return session


def _parse_utc(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, float):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_upcoming(source: Dict[str, Any], now: datetime) -> bool:
    """Keep events that have not ended yet (or have no end date)."""
    schedule = source.get("eventSchedule") or {}
    end = _parse_utc(schedule.get("eventEndUtc")) or _parse_utc(schedule.get("eventStartUtc"))
    if end is None:
        return True
    return end >= now


class UTRScraper:
    """Fetches tournament events from the UTR search API with pagination."""

    def __init__(self):
        self.endpoint = API_ENDPOINT

    def fetch_tournaments(
        self,
        max_pages: int = 20,
        sleep_min: float = 0.5,
        sleep_max: float = 1.5,
        page_size: int = PAGE_SIZE,
    ) -> List[Dict[str, Any]]:
        """
        Fetch UTR events with eventTypes=tournament only.

        Raises on request failure so callers do not persist a partial result set.
        """
        all_tournaments: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        now = datetime.now(timezone.utc)
        logger.info("Starting UTR tournament fetch with max_pages=%s", max_pages)

        with _session() as session:
            for page in range(max_pages):
                params = {
                    "eventTypes": "tournament",
                    "top": page_size,
                    "skip": page * page_size,
                }
                try:
                    response = session.get(self.endpoint, params=params, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    hits = data.get("hits") or []

                    page_count = 0
                    for hit in hits:
                        source = hit.get("source") or {}
                        event_id = str(source.get("id") or hit.get("id") or "")
                        if not event_id or event_id in seen_ids:
                            continue
                        if not _is_upcoming(source, now):
                            continue
                        seen_ids.add(event_id)
                        all_tournaments.append(source)
                        page_count += 1

                    total = data.get("total")
                    logger.info(
                        "Page %s: kept %s/%s tournaments (total index=%s, accumulated=%s)",
                        page + 1,
                        page_count,
                        len(hits),
                        total,
                        len(all_tournaments),
                    )

                    if len(hits) < page_size:
                        logger.info("Reached end of UTR results")
                        break

                    if page < max_pages - 1:
                        time.sleep(random.uniform(sleep_min, sleep_max))

                except requests.RequestException as e:
                    logger.error("Request error on page %s: %s", page + 1, e)
                    raise

        logger.info("Fetched %s total upcoming UTR tournaments", len(all_tournaments))
        return all_tournaments
