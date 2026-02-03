# USTA Tournament Map

An interactive web application for discovering and filtering USTA tennis tournaments across the United States.

![USTA Tournament Map](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![React](https://img.shields.io/badge/React-18+-blue.svg)

## Features

### Interactive Map
- **Real-time filtering** with advanced multi-criteria search
- **Color-coded markers** showing tournament status:
  - 🔵 Blue: Registration open
  - 🟠 Orange: Registration closed
  - 🔴 Red: Tournament started
- **Clustered markers** for better visualization of dense tournament areas
- **Detailed popups** with tournament information and direct links

### Advanced Filtering
Filter tournaments by:
- **Date range**: From/To dates
- **Category**: Adult, Junior, Wheelchair
- **Level**: Level 1-4, Unsanctioned, etc.
- **Surface**: Hard, Clay, Grass
- **Court Location**: Indoor, Outdoor
- **Gender**: Men, Women, Mixed
- **Event Type**: Singles, Doubles
- **Age Group**: TODS codes (10U, 12U, 14U, etc.)

### Auto-Updates
- Daily automatic data refresh at midnight (UTC)
- Fetches all upcoming tournaments from USTA API
- Removes tournaments older than 7 days

## Architecture

### Backend (FastAPI + Python)
- **FastAPI** REST API serving tournament data
- **Pandas + PyArrow** for efficient Parquet data storage
- **Tournament Scraper** for USTA API integration
- **Modular design** with separated concerns

### Frontend (React + Leaflet)
- **React 18** with modern hooks
- **React Leaflet** for interactive mapping
- **Marker clustering** for performance
- **Responsive design** with scrollable filter panel

## Local Development

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm or yarn

### Backend Setup

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Fetch initial tournament data:
```bash
python -m backend.main --update --max-pages 10
```

4. Start the API server:
```bash
python server.py
# API will be available at http://localhost:8000
```

### Frontend Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start development server:
```bash
npm run dev
# Frontend will be available at http://localhost:3000
```

## Project Structure

```text
usta-tournament-map/
├── backend/
│   ├── server.py              # FastAPI application
│   ├── main.py                # CLI for data updates
│   ├── data_manager.py        # Parquet data management
│   ├── tournament_scraper.py  # USTA API scraper
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main React component
│   │   └── App.css           # Styles
│   ├── package.json
│   └── vite.config.js
├── data/
│   └── tournaments.parquet    # Tournament data store
├── .ebextensions/            # AWS Elastic Beanstalk config
│   ├── 01_setup.config       # Uvicorn + ASGI setup
│   ├── cron-jobs.config      # Daily data updates
│   ├── cron-setup.config     # Cron daemon setup
│   └── logrotate.config      # Log rotation
└── Procfile                  # EB process configuration
```

## API Endpoints

```GET /api/tournaments```

Returns all active tournaments with full details including events.

**Response:**
```json
[
  {
    "id": "...",
    "name": "Tournament Name",
    "latitude": 34.0522,
    "longitude": -118.2437,
    "startDate": "2026-02-15T00:00:00Z",
    "endDate": "2026-02-17T00:00:00Z",
    "entriesCloseDateTime": "2026-02-10T04:59:59Z",
    "location": "Venue Name, City, State",
    "categories": ["Adult"],
    "level": "Level 3",
    "url": "https://playtennis.usta.com/...",
    "events": [
      {
        "surface": "Hard",
        "courtLocation": "Indoor",
        "gender": "Boys",
        "eventType": "Singles",
        "todsCode": "12U"
      }
    ]
  }
]
```

```GET /api/tournaments/{tournament_id}```

Returns full raw data for a specific tournament (debug endpoint).

```GET /api/health```

Health check endpoint.

## Deployment (AWS Elastic Beanstalk)

### Prerequisites

- AWS CLI configured
- EB CLI installed (```pip install awsebcli```)

### Deploy

1. Initialize EB (first time only):
```bash
eb init
```

2. Create environment (first time only):
```bash
eb create usta-tournament-map-env
```

3. Deploy updates:
```bash
eb deploy
```

4. Check status:
```bash
eb status
eb health
```

5. View logs:
```bash
eb logs
```

## Environment Configuration

The application uses:
- **Nginx** as reverse proxy
- **Uvicorn** as ASGI server
- **Gunicorn** as process manager
- **Cron** for daily data updates at midnight

## Technologies

### Backend

- **FastAPI** - Modern async API framework
- **Uvicorn** - ASGI server
- **Pandas** - Data manipulation
- **PyArrow** - Parquet file format
- **Requests** - HTTP client for USTA API

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool
- **React Leaflet** - Map component
- **Leaflet MarkerCluster** - Marker clustering

## Data Management

### Storage

- **Format:** Parquet (efficient columnar storage)
- **Location:** data/tournaments.parquet

### Update Schedule

- **Frequency:** Daily at midnight UTC
- **Source:** USTA TournamentDesk API
- **Pages fetched:** 100 (configurable)

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Acknowledgments

- Tournament data provided by USTA TournamentDesk
- Map tiles by [OpenStreetMap](https://www.openstreetmap.org/)