"""
Scraper for ITF Masters Tour tournament data.
"""
from __future__ import annotations

import calendar
import logging
import math
import random
import time
from datetime import date
from typing import Any, Callable, Optional
from urllib.parse import urlencode

import pycountry
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.itftennis.com"
API_URL = f"{BASE_URL}/tennis/api/TournamentApi/GetCalendar"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}
NOMINATIM_HEADERS = {"User-Agent": "itf-tournaments-app/1.0"}

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
CALENDAR_PAGE_SIZE = 100

CHANGE_FIELDS = ("tournamentName", "startDate", "endDate", "status")

# ITF hostNationCode values that are not ISO 3166-1 alpha-3
ITF_COUNTRY_TO_ISO = {
    "BRN": "BH",  # ITF Bahrain; ISO alpha-3 BRN is Brunei (BN), Bahrain is BHR
}

# Nominatim alpha-2 fallbacks after a failed geocode in the primary country
COUNTRY_CODE_FALLBACKS = {
    "IE": "GB",  # Northern Ireland filed under IRL but geocodes as GBR
    "TW": "CN",  # Chinese Taipei (TPE) fallback to China
    "HK": "CN",  # Hong Kong fallback to China
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_coord(v: Any) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def _retry(label: str, fn: Callable[[], Any], retries: int = MAX_RETRIES) -> Any:
    """Run fn() with exponential backoff when it returns None or raises."""
    for attempt in range(1, retries + 1):
        try:
            result = fn()
            if result is not None:
                if attempt > 1:
                    logger.info("%s succeeded on attempt %d", label, attempt)
                return result
        except Exception as exc:
            logger.warning("%s failed (attempt %d/%d): %s", label, attempt, retries, exc)

        if attempt < retries:
            sleep_s = RETRY_BACKOFF * attempt
            logger.debug("%s retrying after %.1fs", label, sleep_s)
            time.sleep(sleep_s)

    logger.error("%s: all %d attempts failed", label, retries)
    return None


def _block_resources(route) -> None:
    if route.request.resource_type in {"image", "media", "font"}:
        route.abort()
    else:
        route.continue_()


def _is_bot_block(text: str) -> bool:
    return "_Incapsula_Resource" in text or "SWUDNSAI" in text


def _open_browser(playwright):
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    context = browser.new_context(
        user_agent=HEADERS["User-Agent"],
        viewport={"width": 1280, "height": 800},
    )
    context.route("**/*", _block_resources)
    page = context.new_page()
    return browser, page


def _calendar_url(year: int, month: int, skip: int = 0, take: int = CALENDAR_PAGE_SIZE) -> str:
    last_day = calendar.monthrange(year, month)[1]
    params = {
        "circuitCode": "VT",
        "searchString": "",
        "skip": str(skip),
        "take": str(take),
        "dateFrom": f"{year}-{month:02d}-01",
        "dateTo": f"{year}-{month:02d}-{last_day}",
        "isOrderAscending": "true",
        "orderField": "startDate",
        "nationCodes": "",
        "zoneCodes": "",
        "indoorOutdoor": "",
        "categories": "",
        "surfaceCodes": "",
    }
    return f"{API_URL}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Calendar scraping
# ---------------------------------------------------------------------------


def _fetch_calendar_page(year: int, month: int, page, skip: int, take: int) -> list[dict]:
    """Fetch one calendar page. Raises if capture fails after retries."""
    label = f"calendar {year}-{month:02d} skip={skip}"
    url = _calendar_url(year, month, skip=skip, take=take)

    def _fetch():
        captured: dict[str, Any] = {}

        def on_response(resp):
            if "GetCalendar" in resp.url:
                try:
                    captured["data"] = resp.json()
                except Exception:
                    logger.debug("%s response JSON parse failed", label)

        page.on("response", on_response)
        try:
            page.goto(url, wait_until="commit", timeout=30000)
            page.wait_for_timeout(2000)
        finally:
            page.remove_listener("response", on_response)

        data = captured.get("data")
        if data is not None:
            return data.get("items", []) or []

        if _is_bot_block(page.content()):
            logger.warning("%s bot-block detected, will retry", label)
        else:
            logger.warning("%s no JSON captured, will retry", label)
        return None

    result = _retry(label, _fetch)
    if result is None:
        raise RuntimeError(f"{label}: failed to fetch calendar (bot-block or empty capture)")
    return result


def scrape_calendar_month(year: int, month: int, page) -> list[dict]:
    """Fetch one month of ITF tournaments via Playwright, paginating past take=100."""
    label = f"calendar {year}-{month:02d}"
    all_items: list[dict] = []
    skip = 0

    while True:
        batch = _fetch_calendar_page(year, month, page, skip=skip, take=CALENDAR_PAGE_SIZE)
        all_items.extend(batch)
        if len(batch) < CALENDAR_PAGE_SIZE:
            break
        skip += CALENDAR_PAGE_SIZE
        time.sleep(1.0)

    logger.info("%s fetched %d tournaments", label, len(all_items))
    return all_items


# ---------------------------------------------------------------------------
# Detail scraping
# ---------------------------------------------------------------------------


def scrape_tournament_detail(page, tournament_link: str) -> dict:
    """Scrape venue details (name + address) from a tournament page."""
    url = BASE_URL + tournament_link
    label = f"detail {tournament_link}"

    try:
        page.goto(url, wait_until="commit", timeout=60000)
        try:
            page.wait_for_selector(".tournament-info__details-item", timeout=8000)
        except Exception:
            page.wait_for_timeout(3000)
    except Exception as exc:
        logger.warning("%s page load failed: %s", label, exc)
        return {}

    soup = BeautifulSoup(page.content(), "html.parser")
    details: dict[str, str] = {}

    for item in soup.select(".tournament-info__details-item"):
        label_el = item.select_one(".tournament-info__label")
        value_el = item.select_one(".tournament-info__value")
        label_text = label_el.get_text(strip=True) if label_el else ""
        value = value_el.get_text(strip=True) if value_el else ""
        if "Venue Name:" in label_text:
            details["venueName"] = value
        elif "Venue Address:" in label_text:
            details["venueAddress"] = value

    if not details.get("venueName"):
        logger.info("%s no venue data found", label)

    return details


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------


def normalize_country_code(itf_code: str) -> Optional[str]:
    """Convert ITF nation code to Nominatim ISO alpha-2."""
    if not itf_code:
        return None
    code = itf_code.upper()
    if code in ITF_COUNTRY_TO_ISO:
        return ITF_COUNTRY_TO_ISO[code]
    country = pycountry.countries.get(alpha_3=code)
    return country.alpha_2 if country else None


class NominatimGeocoder:
    """Nominatim client with session reuse and per-run query cache.

    Progressive search tries distinct strings: ``venue, address`` then ``address``
    alone at each address truncation — not the same query twice.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(NOMINATIM_HEADERS)
        self._cache: dict[tuple[str, Optional[str]], Optional[tuple[float, float]]] = {}

    def close(self) -> None:
        self.session.close()

    def _try_geocode(
        self, query: str, country_code: Optional[str]
    ) -> Optional[tuple[float, float]]:
        if not query.strip():
            return None

        cache_key = (query, country_code)
        if cache_key in self._cache:
            return self._cache[cache_key]

        params: dict[str, Any] = {"q": query, "format": "json", "limit": 1}
        if country_code:
            params["countrycodes"] = country_code.lower()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                time.sleep(1.0)  # Nominatim: max 1 request/second
                resp = self.session.get(NOMINATIM_URL, params=params, timeout=10)
                if resp.status_code == 200:
                    results = resp.json()
                    coords = (
                        (float(results[0]["lat"]), float(results[0]["lon"]))
                        if results
                        else None
                    )
                    self._cache[cache_key] = coords
                    return coords  # empty result is definitive — do not retry
                logger.warning(
                    "Nominatim %d for '%s' (attempt %d)",
                    resp.status_code,
                    query[:40],
                    attempt,
                )
            except Exception as exc:
                logger.warning(
                    "Nominatim error for '%s' (attempt %d): %s",
                    query[:40],
                    attempt,
                    exc,
                )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)

        logger.warning("Nominatim failed after %d attempts: '%s'", MAX_RETRIES, query[:40])
        self._cache[cache_key] = None
        return None

    def geocode_venue(
        self,
        venue_name: str,
        venue_address: str,
        location: str,
        host_nation: str,
        country_code: Optional[str] = None,
    ) -> tuple[Optional[float], Optional[float]]:
        """Geocode: progressive address (with venue, then without) → location → country fallback."""
        if host_nation and venue_address:
            suffix = f", {host_nation}"
            if venue_address.endswith(suffix):
                venue_address = venue_address[: -len(suffix)]

        address_parts = (
            [p.strip() for p in venue_address.split(",") if p.strip()] if venue_address else []
        )

        # Distinct queries: "Venue, addr..." then "addr..." at each truncation level
        for drop in range(len(address_parts) + 1):
            remaining = ", ".join(address_parts[drop:])

            if venue_name and remaining:
                coords = self._try_geocode(f"{venue_name}, {remaining}", country_code)
                if coords:
                    logger.info("Geocoded [%s + addr-%d]: %s", venue_name[:25], drop, coords)
                    return coords

            if remaining:
                coords = self._try_geocode(remaining, country_code)
                if coords:
                    logger.info("Geocoded [addr-%d]: %s", drop, coords)
                    return coords

        if location:
            coords = self._try_geocode(location, country_code)
            if coords:
                logger.info("Geocoded [location '%s']: %s", location, coords)
                return coords

        fallback_cc = COUNTRY_CODE_FALLBACKS.get(country_code or "")
        if fallback_cc:
            logger.debug("Retrying with country fallback %s→%s", country_code, fallback_cc)
            return self.geocode_venue(
                venue_name, venue_address, location, host_nation, fallback_cc
            )

        logger.warning(
            "No geocoding match: venue=%s loc=%s nation=%s",
            venue_name[:30],
            location[:20],
            host_nation,
        )
        return None, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _needs_rescrape(t: dict, ex: Optional[dict]) -> bool:
    if not ex:
        return True
    has_coords = _valid_coord(ex.get("lat")) and _valid_coord(ex.get("lng"))
    if not (ex.get("venueName") and has_coords):
        return True
    return any(str(t.get(f)) != str(ex.get(f)) for f in CHANGE_FIELDS)


DETAIL_BATCH_SIZE = 10


def scrape_itf_months(
    year: int,
    months: list[int],
    sleep_min: float = 2.0,
    sleep_max: float = 5.0,
    fetch_details: bool = True,
    existing_df=None,
    data_manager=None,
    save_batch_size: int = DETAIL_BATCH_SIZE,
    max_details: Optional[int] = None,
) -> list[dict]:
    """Scrape ITF calendar for the given months, then detail/geocode in batches.

    1. Fetch all month calendars and dedupe by tournamentKey.
    2. Reuse existing venue/coords where still valid.
    3. Detail-scrape + geocode the rest, saving every ``save_batch_size`` tournaments.
    """
    from playwright.sync_api import sync_playwright

    today = date.today()
    logger.info(
        "ITF scrape started for year=%s months=%s (today=%s)",
        year,
        months,
        today.isoformat(),
    )

    existing_records = (
        existing_df.to_dict(orient="records")
        if existing_df is not None and not existing_df.empty
        else []
    )
    existing = {r["tournamentKey"]: r for r in existing_records}
    logger.info("Loaded %d existing ITF tournaments", len(existing))

    seen: dict[str, dict] = {}
    geocoder = NominatimGeocoder()

    def _persist(label: str) -> None:
        if not data_manager or not seen:
            return
        data_manager.save_tournaments(list(seen.values()))
        logger.info("%s: saved %d tournaments", label, len(seen))

    try:
        with sync_playwright() as p:
            browser, page = _open_browser(p)
            logger.info("Playwright browser launched")
            try:
                # Phase 1: full calendar list (deduped)
                for i, month in enumerate(months):
                    label_month = f"{year}-{month:02d}"
                    logger.info("ITF month %s: fetching calendar", label_month)

                    month_items = scrape_calendar_month(year, month, page)
                    logger.info(
                        "ITF month %s: %d items from calendar",
                        label_month,
                        len(month_items),
                    )

                    added = 0
                    for t in month_items:
                        try:
                            end_str = t.get("endDate", "")[:10]
                            if end_str and date.fromisoformat(end_str) < today:
                                continue
                        except ValueError:
                            pass
                        seen[t["tournamentKey"]] = t
                        added += 1

                    logger.info(
                        "ITF month %s: %d upcoming tournaments kept (total=%d)",
                        label_month,
                        added,
                        len(seen),
                    )

                    if i < len(months) - 1:
                        time.sleep(random.uniform(sleep_min, sleep_max))

                # Phase 2: reuse existing details; queue those that need a refresh
                needs_scrape: list[dict] = []
                for key, current in seen.items():
                    ex = existing.get(key)
                    if not ex:
                        needs_scrape.append(current)
                        continue

                    itf_cc = (current.get("hostNationCode") or "").upper()
                    # Non-ISO ITF codes (e.g. BRN=Bahrain) may have been geocoded as the
                    # ISO country (Brunei); clear coords so they are refreshed.
                    wrong_iso_geocode = itf_cc in ITF_COUNTRY_TO_ISO

                    if _needs_rescrape(current, ex) or wrong_iso_geocode:
                        if wrong_iso_geocode:
                            logger.info(
                                "Re-geocoding %s (ITF code %s → %s)",
                                key,
                                itf_cc,
                                ITF_COUNTRY_TO_ISO[itf_cc],
                            )
                        else:
                            logger.info("Re-scraping changed tournament %s", key)
                        needs_scrape.append(current)

                    current.update(
                        {
                            "venueName": ex.get("venueName"),
                            "venueAddress": ex.get("venueAddress"),
                            "lat": None if wrong_iso_geocode else ex.get("lat"),
                            "lng": None if wrong_iso_geocode else ex.get("lng"),
                        }
                    )

                queued = len(needs_scrape)
                if max_details is not None:
                    needs_scrape = needs_scrape[: max(0, max_details)]

                logger.info(
                    "ITF calendar complete: %d tournaments (%d detail-scrape now, %d queued, %d with existing details)",
                    len(seen),
                    len(needs_scrape),
                    queued,
                    len(seen) - queued,
                )
                _persist("ITF after calendar")

                # Phase 3: detail + geocode in batches
                if fetch_details and needs_scrape:
                    total_details = len(needs_scrape)
                    batch_size = max(1, save_batch_size)

                    for j, t in enumerate(needs_scrape, start=1):
                        name = t.get("tournamentName", t["tournamentKey"])
                        logger.info("ITF detail %d/%d: %s", j, total_details, name)

                        detail = scrape_tournament_detail(page, t["tournamentLink"])

                        venue_name = detail.get("venueName", "")
                        venue_address = detail.get("venueAddress", "")
                        location = (t.get("location") or "").strip()
                        host_nation = t.get("hostNation", "")
                        country_code = normalize_country_code(t.get("hostNationCode", ""))

                        lat, lng = geocoder.geocode_venue(
                            venue_name,
                            venue_address,
                            location,
                            host_nation,
                            country_code,
                        )

                        detail["lat"], detail["lng"] = lat, lng
                        t.update(detail)

                        if j % batch_size == 0 or j == total_details:
                            _persist(f"ITF detail batch {j}/{total_details}")

                        if j < total_details:
                            time.sleep(random.uniform(sleep_min, sleep_max))

                    logger.info(
                        "ITF detail scrape finished: %d scraped, %d total",
                        total_details,
                        len(seen),
                    )

            finally:
                browser.close()
                logger.info("Browser closed")
    finally:
        geocoder.close()

    logger.info(
        "ITF scrape finished: %d tournaments collected for year=%s months=%s",
        len(seen),
        year,
        months,
    )
    return list(seen.values())
