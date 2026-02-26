"""
Scraper for ITF Masters Tour tournament data.
"""
from __future__ import annotations

import calendar
import logging
import random
import time
from datetime import date
from typing import Any, Callable, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.itftennis.com"
API_URL = f"{BASE_URL}/tennis/api/TournamentApi/GetCalendar"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0

CHANGE_FIELDS = ("tournamentName", "startDate", "endDate", "status")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
            logger.warning(
                "%s failed (attempt %d/%d): %s",
                label,
                attempt,
                retries,
                exc,
            )

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
            "--single-process",
        ],
    )
    context = browser.new_context(
        user_agent=HEADERS["User-Agent"],
        viewport={"width": 1280, "height": 800},
    )
    context.route("**/*", _block_resources)
    page = context.new_page()
    return browser, page


def _calendar_url(year: int, month: int) -> str:
    last_day = calendar.monthrange(year, month)[1]
    params = {
        "circuitCode": "VT",
        "searchString": "",
        "skip": "0",
        "take": "100",
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
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{API_URL}?{qs}"


# ---------------------------------------------------------------------------
# Calendar scraping
# ---------------------------------------------------------------------------


def scrape_calendar_month(year: int, month: int, page) -> list[dict]:
    """Fetch one month of ITF tournaments via Playwright."""
    label = f"calendar {year}-{month:02d}"
    url = _calendar_url(year, month)

    def _fetch():
        captured: dict[str, Any] = {}

        def on_response(resp):
            if "GetCalendar" in resp.url:
                try:
                    captured["data"] = resp.json()
                except Exception:
                    logger.debug("%s response JSON parse failed", label)

        page.on("response", on_response)
        page.goto(url, wait_until="commit", timeout=30000)
        page.wait_for_timeout(2000)
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
    items: list[dict] = result if isinstance(result, list) else []
    logger.info("%s fetched %d tournaments", label, len(items))
    return items


# ---------------------------------------------------------------------------
# Detail scraping
# ---------------------------------------------------------------------------


def scrape_tournament_detail(page, tournament_link: str) -> dict:
    """Scrape venue details (name + address) from a tournament page."""
    url = BASE_URL + tournament_link
    label = f"detail {tournament_link}"

    page.goto(url, wait_until="commit", timeout=60000)
    try:
        page.wait_for_selector(".tournament-info__details-item", timeout=8000)
    except Exception:
        page.wait_for_timeout(3000)

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


def geocode_address(
    address: str,
    fallback: Optional[str] = None,
    country_code: Optional[str] = None,
) -> tuple[Optional[float], Optional[float]]:
    """Geocode via Nominatim, falling back once to a coarser location."""

    def _nominatim(q: str) -> Optional[tuple[float, float]]:
        if not q:
            return None

        params: dict[str, Any] = {"q": q, "format": "json", "limit": 1}
        if country_code:
            params["countrycodes"] = country_code

        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers={"User-Agent": "itf-tournaments-app/1.0"},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json()
            if not results:
                logger.debug("Nominatim no results for '%s'", q)
                return None
            return float(results[0]["lat"]), float(results[0]["lon"])
        except Exception as exc:
            logger.warning("Nominatim request failed for '%s': %s", q, exc)
            return None

    coords = _nominatim(address)
    if coords is not None:
        return coords

    if fallback:
        logger.info("Geocode empty for '%s', trying fallback '%s'", address, fallback)
        coords = _nominatim(fallback)
        if coords is not None:
            return coords

    return None, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _needs_rescrape(t: dict, ex: Optional[dict]) -> bool:
    if not ex:
        return True
    has_coords = ex.get("lat") is not None and ex.get("lng") is not None
    if not (ex.get("venueName") and has_coords):
        return True
    return any(str(t.get(f)) != str(ex.get(f)) for f in CHANGE_FIELDS)


def scrape_itf_months(
    year: int,
    months: list[int],
    sleep_min: float = 2.0,
    sleep_max: float = 5.0,
    fetch_details: bool = True,
    existing_df=None,
    data_manager=None,
) -> list[dict]:
    """Scrape ITF calendar for the given months and return upcoming tournaments."""
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

    with sync_playwright() as p:
        browser, page = _open_browser(p)
        logger.info("Playwright browser launched")
        try:
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
                        start = t.get("startDate", "")[:10]
                        if start and date.fromisoformat(start) < today:
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

                if fetch_details and month_items:
                    month_needs_scrape: list[dict] = []

                    for t in month_items:
                        key = t["tournamentKey"]
                        current = seen.get(key)
                        if not current:
                            continue

                        ex = existing.get(key)

                        if not ex:
                            month_needs_scrape.append(current)
                            continue

                        if _needs_rescrape(current, ex):
                            logger.info("Re-scraping changed tournament %s", key)
                            month_needs_scrape.append(current)
                            continue

                        current.update(
                            {
                                "venueName": ex.get("venueName"),
                                "venueAddress": ex.get("venueAddress"),
                                "lat": ex.get("lat"),
                                "lng": ex.get("lng"),
                            }
                        )

                    total_details = len(month_needs_scrape)
                    for j, t in enumerate(month_needs_scrape, start=1):
                        name = t.get("tournamentName", t["tournamentKey"])
                        logger.info(
                            "ITF detail %d/%d [%s]: %s",
                            j,
                            total_details,
                            label_month,
                            name,
                        )

                        detail = scrape_tournament_detail(page, t["tournamentLink"])

                        country_code = t.get("hostNationCode", "")
                        location = (t.get("location") or "").strip()
                        venue_address = detail.get("venueAddress", "") or ""

                        host_nation = t.get("hostNation", "")
                        suffix = f", {host_nation}" if host_nation else ""
                        if suffix and venue_address.endswith(suffix):
                            venue_address = venue_address[: -len(suffix)]

                        if venue_address:
                            lat, lng = geocode_address(
                                venue_address,
                                fallback=location,
                                country_code=country_code,
                            )
                            detail["lat"], detail["lng"] = lat, lng
                        elif not detail.get("venueName") and location:
                            lat, lng = geocode_address(
                                location,
                                country_code=country_code,
                            )
                            detail["lat"], detail["lng"] = lat, lng

                        t.update(detail)

                        if j < total_details:
                            time.sleep(random.uniform(sleep_min, sleep_max))

                    logger.info(
                        "ITF month %s: detail scrape finished (%d scraped, %d reused, total=%d)",
                        label_month,
                        total_details,
                        len(month_items) - total_details,
                        len(seen),
                    )

                    if data_manager:
                        data_manager.save_tournaments(list(seen.values()))
                        logger.info("ITF month %s: tournaments saved", label_month)

                if i < len(months) - 1:
                    time.sleep(random.uniform(sleep_min, sleep_max))

        finally:
            browser.close()
            logger.info("Browser closed")

    logger.info(
        "ITF scrape finished: %d tournaments collected for year=%s months=%s",
        len(seen),
        year,
        months,
    )
    return list(seen.values())