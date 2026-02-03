"""
FastAPI server for tournament data.
"""

import logging
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from data_manager import DataManager

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

data_manager = DataManager()


# ---------- Helpers ----------

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
            "surface": (event.get("surface") or "").strip() or None,
            "courtLocation": (event.get("courtLocation") or "").strip() or None,
            "gender": (division.get("gender") or "").strip() or None,
            "eventType": (division.get("eventType") or "").strip() or None,
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


def build_tournament_url(tournament: Dict[str, Any]) -> str | None:
    """Construct full USTA competition URL from org slug + path."""
    url_path = (tournament.get("url") or "").strip()
    org = tournament.get("organization", {}) or {}
    org_slug = (org.get("urlSegment") or "").strip()

    if not (url_path and org_slug):
        return None

    return f"https://playtennis.usta.com/Competitions/{org_slug}{url_path}"


def serialize_tournament_for_map(t: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw tournament dict into the minimal map payload."""
    geo = (t.get("location") or {}).get("geo", {}) or {}
    lat = geo.get("latitude")
    lng = geo.get("longitude")

    if lat is None or lng is None:
        # Caller should skip tournaments with missing geo
        return {}

    location_info = get_location_details(t)
    categories = get_tournament_categories(t)
    events = extract_event_details(t)
    registration = t.get("registrationRestrictions", {}) or {}

    return {
        "id": t.get("id"),
        "name": t.get("name"),
        "latitude": lat,
        "longitude": lng,
        "startDate": t.get("timeZoneStartDateTime"),
        "endDate": t.get("timeZoneEndDateTime"),
        "entriesCloseDateTime": registration.get("entriesCloseDateTime"),
        "location": location_info["full"],
        "categories": categories,
        "url": build_tournament_url(t),
        "level": (t.get("level") or {}).get("name", ""),
        "events": events,  # New: list of event details
    }


# ---------- Routes ----------

@app.get("/api/tournaments")
async def get_tournaments() -> List[Dict[str, Any]]:
    """Get all tournaments with location data for map display."""
    try:
        tournaments = data_manager.get_tournaments()
        map_data: List[Dict[str, Any]] = []

        for t in tournaments:
            serialized = serialize_tournament_for_map(t)
            # Skip tournaments with missing geo
            if serialized:
                map_data.append(serialized)

        logger.info("Returning %d tournaments", len(map_data))
        return map_data

    except Exception as exc:
        logger.error("Error fetching tournaments: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/tournaments/{tournament_id}")
async def get_tournament_detail(tournament_id: str) -> Dict[str, Any]:
    """
    Get full tournament data for a specific tournament ID (debug/testing).
    Returns the complete unprocessed tournament dict.
    """
    try:
        tournaments = data_manager.get_tournaments()
        tournament = next((t for t in tournaments if t.get("id") == tournament_id), None)

        if not tournament:
            raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")

        logger.info("Returning full data for tournament: %s", tournament.get("name"))
        return tournament

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching tournament detail: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Serve React static files
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.exists(frontend_dist):
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    # Serve index.html for all other routes (React Router)
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        # If it's an API route, let FastAPI handle it (already handled above)
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        
        # Check if file exists in dist
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Otherwise serve index.html (for React Router)
        return FileResponse(os.path.join(frontend_dist, "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)