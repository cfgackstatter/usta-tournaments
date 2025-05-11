import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# Data storage configuration
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
TOURNAMENTS_FILE = os.path.join(DATA_DIR, "tournaments.parquet")

# Create directories if they don't exist
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# API configuration
API_ENDPOINT = "https://prd-usta-kube.clubspark.pro/unified-search-api/api/Search/tournaments/Query?indexSchema=tournament"
DEFAULT_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}

# Default search parameters
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