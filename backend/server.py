"""
FastAPI server for tournament data.
"""
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.usta_data_manager import USTADataManager
from backend.itf_data_manager import ITFDataManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Tournament API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

usta_data_manager = USTADataManager()
itf_data_manager = ITFDataManager()


# Canonical filter codes shared by USTA + ITF (frontend label maps use these keys)
_SURFACE_ALIASES = {
    "hard": "hard",
    "grass": "grass",
    "clay": "clay",
    "carpet": "carpet",
    "greenclay": "greenClay",
    "redclay": "redClay",
    "claygreen": "greenClay",
    "clayred": "redClay",
}
_COURT_ALIASES = {
    "indoor": "indoor",
    "outdoor": "outdoor",
}


def _norm_key(value: Any) -> str:
    return "".join(str(value).strip().lower().split()).replace("_", "").replace("-", "")


def normalize_surface(value: Any) -> str | None:
    """Map source-specific surface strings to a shared filter code."""
    if value is None or isinstance(value, float):
        return None
    text = str(value).strip()
    if not text or text.lower() == "unknown":
        return None
    return _SURFACE_ALIASES.get(_norm_key(text), text)


def normalize_court_location(value: Any) -> str | None:
    """Map Indoor/Outdoor variants to indoor/outdoor."""
    if value is None or isinstance(value, float):
        return None
    text = str(value).strip()
    if not text or text.lower() == "unknown":
        return None
    return _COURT_ALIASES.get(_norm_key(text), text.lower())


# ---------- USTA Helpers ----------

def get_tournament_categories(tournament: Dict[str, Any]) -> List[str]:
    """
    Return list of category names from levelCategories, title‑cased.

    Example input:
      "levelCategories": [{"name": "junior"}, {"name": "adult"}]
    Output:
      ["Junior", "Adult"]
    """
    level_categories = tournament.get("levelCategories", []) or []
    categories: List[str] = []

    for item in level_categories:
        if isinstance(item, dict):
            name = (item.get("name") or "").strip()
        else:
            name = str(item).strip()

        if name:
            categories.append(name.title())

    return categories


def extract_event_details(tournament: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract event-level details from the "events" array.

    For each event, extracts:
      - surface (e.g. "Hard")
      - courtLocation (e.g. "Indoor")
      - gender (from division.gender, e.g. "Boys", "Girls", "Coed")
      - eventType (from division.eventType, e.g. "Singles", "Doubles")
      - todsCode (from division.ageCategory.todsCode)

    Returns:
      List of event dicts with extracted fields.
    """
    events = tournament.get("events", []) or []
    event_details: List[Dict[str, Any]] = []

    for event in events:
        if not isinstance(event, dict):
            continue

        division = event.get("division", {}) or {}
        age_category = division.get("ageCategory", {}) or {}

        detail = {
            "surface": normalize_surface(event.get("surface")),
            "courtLocation": normalize_court_location(event.get("courtLocation")),
            "gender": (division.get("gender") or "").strip().lower() or None,
            "eventType": (division.get("eventType") or "").strip().lower() or None,
            "todsCode": (age_category.get("todsCode") or "").strip() or None,
        }

        event_details.append(detail)

    return event_details


def get_location_details(tournament: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract detailed location info: name, city, state.
    - location.name: venue (e.g. "Griffith-Riverside Tennis")
    - primaryLocation.town: city    (e.g. "Los Angeles")
    - primaryLocation.county: state (e.g. "CA")
    """
    location = tournament.get("location", {}) or {}
    primary_location = tournament.get("primaryLocation", {}) or {}

    name = (location.get("name") or "").strip()
    city = (primary_location.get("town") or "").strip()
    state = (primary_location.get("county") or "").strip()

    parts = [p for p in (name, city, state) if p]
    full = ", ".join(parts)

    return {
        "name": name,
        "city": city,
        "state": state,
        "full": full,
    }


def build_usta_url(tournament: Dict[str, Any]) -> str | None:
    """Construct full USTA competition URL from org slug + path."""
    url_path = (tournament.get("url") or "").strip()
    org = tournament.get("organization", {}) or {}
    org_slug = (org.get("urlSegment") or "").strip()

    if not (url_path and org_slug):
        return None

    return f"https://playtennis.usta.com/Competitions/{org_slug}{url_path}"


def parse_utc(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime into an aware UTC datetime."""
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


def to_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def tournament_local_date(utc_dt: Optional[datetime], tz_name: Optional[str]) -> Optional[str]:
    """Calendar date (YYYY-MM-DD) in the tournament's timezone."""
    if utc_dt is None:
        return None
    if tz_name:
        try:
            return utc_dt.astimezone(ZoneInfo(tz_name)).date().isoformat()
        except Exception:
            pass
    return utc_dt.date().isoformat()


def serialize_usta_tournament(t: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw USTA tournament dict into the map payload.

    USTA's timeZoneStart/EndDateTime values have unreliable offsets; use
    startDateTime/endDateTime (UTC) plus timeZone for correctness.
    """
    geo = (t.get("location") or {}).get("geo", {}) or {}
    lat = geo.get("latitude")
    lng = geo.get("longitude")
    if lat is None or lng is None:
        return {}

    location_info = get_location_details(t)
    registration = t.get("registrationRestrictions", {}) or {}
    tz_name = (t.get("timeZone") or "").strip() or None

    start_utc = parse_utc(t.get("startDateTime"))
    end_utc = parse_utc(t.get("endDateTime"))
    close_utc = parse_utc(registration.get("entriesCloseDateTime"))

    return {
        "id":                    t.get("id"),
        "name":                  t.get("name"),
        "latitude":              lat,
        "longitude":             lng,
        # Calendar dates in tournament-local TZ (filters + date-only display)
        "startDate":             tournament_local_date(start_utc, tz_name),
        "endDate":               tournament_local_date(end_utc, tz_name),
        # Absolute instants (status + timed display)
        "startDateTime":         to_utc_iso(start_utc),
        "endDateTime":           to_utc_iso(end_utc),
        "entriesCloseDateTime":  to_utc_iso(close_utc),
        "timeZone":              tz_name,
        "location":              location_info["full"],
        "city":                  location_info["city"],
        "state":                 location_info["state"],
        "venueName":             location_info["name"],
        "categories":            get_tournament_categories(t),
        "url":                   build_usta_url(t),
        "level":                 (t.get("level") or {}).get("name", ""),
        "events":                extract_event_details(t),
        "source":                "USTA",
    }


# ---------- ITF Helpers ----------

def serialize_itf_tournament(t: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw ITF tournament dict into the map payload."""
    lat = t.get("lat")
    lng = t.get("lng")
    if lat is None or lng is None:
        return {}
    
    def _val(v, default="Unknown"):
        """Return default if value is None or a NaN float."""
        return default if (v is None or isinstance(v, float)) else v

    start_date = t.get("startDate", "")
    entries_close = f"{start_date}T00:00:00Z" if start_date else None

    promotional = t.get("promotionalName", "")
    regular = t.get("tournamentName", "")
    if isinstance(promotional, float): promotional = None
    if isinstance(regular, float): regular = ""
    name = f"{promotional} ({regular})" if promotional else regular

    location_parts = [
        str(p) for p in [t.get("venueName"), t.get("location"), t.get("hostNation")]
        if p is not None and not isinstance(p, float)
    ]

    tournament_link = t.get("tournamentLink", "")
    url = f"https://www.itftennis.com{tournament_link}" if tournament_link else None

    return {
        "id":                    t.get("tournamentKey"),
        "name":                  name,
        "latitude":              lat,
        "longitude":             lng,
        "startDate":             t.get("startDate"),
        "endDate":               t.get("endDate"),
        "entriesCloseDateTime":  entries_close,
        "location":              ", ".join(location_parts),
        "hostNation":            t.get("hostNation"),
        "countryCode":           t.get("hostNationCode"),
        "category":              t.get("category"),
        "surfaceDesc":           t.get("surfaceDesc"),
        "indoorOrOutdoor":       t.get("indoorOrOutDoor"),
        "promotionalName":       t.get("promotionalName"),
        "venueName":             t.get("venueName"),
        "venueAddress":          t.get("venueAddress"),
        "url":                   url,
        "source":                "ITF",
        "categories":            ["Adult"],
        "level":                 f"ITF {t.get('category', '')}".strip(),
        "events":                [{
            "surface":       normalize_surface(t.get("surfaceDesc")),
            "courtLocation": normalize_court_location(t.get("indoorOrOutDoor")),
            "gender":        "coed",
            "eventType":     "singles",
            "todsCode":      "30O",
        }],
    }


# ---------- USTA Routes ----------

@app.get("/api/usta-tournaments")
async def get_usta_tournaments() -> List[Dict[str, Any]]:
    try:
        tournaments = usta_data_manager.get_tournaments()
        map_data = [s for t in tournaments if (s := serialize_usta_tournament(t))]
        logger.info("Returning %d USTA tournaments", len(map_data))
        return map_data
    except Exception as exc:
        logger.error("Error fetching USTA tournaments: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/usta-tournaments/{tournament_id}")
async def get_usta_tournament_detail(tournament_id: str) -> Dict[str, Any]:
    try:
        tournaments = usta_data_manager.get_tournaments()
        tournament = next((t for t in tournaments if str(t.get("id")) == tournament_id), None)
        if not tournament:
            raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
        return tournament
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching USTA tournament detail: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    

# ---------- ITF Routes ----------

@app.get("/api/itf-tournaments")
async def get_itf_tournaments() -> List[Dict[str, Any]]:
    try:
        tournaments = itf_data_manager.get_tournaments()
        map_data = [s for t in tournaments if (s := serialize_itf_tournament(t))]
        logger.info("Returning %d ITF tournaments", len(map_data))
        return map_data
    except Exception as exc:
        logger.error("Error fetching ITF tournaments: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/itf-tournaments/{itf_id}")
async def get_itf_tournament_detail(itf_id: str) -> Dict[str, Any]:
    try:
        tournaments = itf_data_manager.get_tournaments()
        tournament = next((t for t in tournaments if t.get("tournamentKey") == itf_id), None)
        if not tournament:
            raise HTTPException(status_code=404, detail=f"ITF Tournament {itf_id} not found")
        return tournament
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching ITF tournament detail: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    

# ---------- Health / freshness ----------

@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/freshness")
async def data_freshness() -> Dict[str, Any]:
    """Return last-updated age for USTA and ITF parquet files."""
    return {
        "usta": usta_data_manager.get_freshness(),
        "itf": itf_data_manager.get_freshness(),
    }


# ---------- Static / React ----------

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)