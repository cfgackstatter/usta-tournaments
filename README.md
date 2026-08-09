# Tennis Tournament Map

An interactive map for discovering USTA, ITF Masters Tour, and UTR Sports tennis tournaments.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141+-green.svg)
![React](https://img.shields.io/badge/React-19+-blue.svg)

## Features

### Interactive Map
- **Color-coded markers** showing tournament status:
  - 🔵 Blue: USTA — registration open
  - 🟢 Dark green: ITF Masters Tour — registration open
  - 🩵 Baby blue: UTR — registration open
  - 🟠 Orange: Registration closed
  - 🔴 Red: Tournament started
- **Clustered markers** for dense areas
- **Detailed popups** with direct links to tournament pages

### Filtering
- **Date range**
- **Category**: USTA Adult / Junior / Wheelchair / Wtnplay, ITF, UTR (defaults: USTA Adult + ITF + UTR)
- **Level**: Grouped by source — USTA levels, ITF grades, UTR ranges
- **Surface**: Hard, Clay, Grass
- **Court location**: Indoor / Outdoor
- **Gender**, **Event type**, **Age group**

### Data Sources
- **USTA**: scraped daily from the USTA TournamentDesk API
- **ITF Masters Tour**: scraped weekly from the ITF calendar API + detail pages
- **UTR**: scraped daily from the UTR Sports events search API (`eventTypes=tournament`)

## Quick Start

```bash
# Install all dependencies
make install

# Fetch initial data
make data

# Run both servers (backend :8000, frontend :5173)
make dev
```

## All Commands

```bash
make help
```

| Command           | Description                             |
| ----------------- | --------------------------------------- |
| make install      | Install backend + frontend dependencies |
| make dev          | Run both dev servers concurrently       |
| make dev-backend  | FastAPI on port 8000 only               |
| make dev-frontend | Vite on port 5173 only                  |
| make data         | Fetch USTA + ITF + UTR                  |
| make data-usta    | Fetch USTA only                         |
| make data-itf     | Fetch ITF only                          |
| make data-utr     | Fetch UTR tournaments only              |
| make build        | Build frontend dist                     |
| make deploy       | Build frontend + eb deploy              |
| make status       | eb status                               |
| make health       | eb health                               |
| make logs         | eb logs                                 |
| make ssh          | eb ssh                                  |
| make update       | Run both update scripts on server       |
| make clean        | Remove build artifacts + __pycache__    |

## Project Structure

```text
tennis-tournament-map/
├── backend/
│   ├── __init__.py
│   ├── server.py               # FastAPI app + serializers
│   ├── main.py                 # CLI data updater
│   ├── usta_scraper.py         # USTA API scraper
│   ├── usta_data_manager.py    # USTA Parquet storage
│   ├── itf_scraper.py          # ITF calendar + detail scraper
│   ├── itf_data_manager.py     # ITF Parquet storage
│   ├── utr_scraper.py          # UTR events API scraper
│   ├── utr_data_manager.py     # UTR Parquet storage
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── App.css
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── usta_tournaments.parquet
│   ├── itf_tournaments.parquet
│   └── utr_tournaments.parquet
├── .ebextensions/
│   ├── 01_setup.config         # Uvicorn + ASGI
│   ├── 02_cron.config          # Cron daemon + update scripts
│   ├── 04_post_deploy_update.config  # Chromium/Playwright install
│   └── 04_logrotate.config     # Log rotation
├── Makefile
├── Procfile
└── README.md
```

## API Endpoints

| Endpoint                       | Description                 |
| ------------------------------ | --------------------------- |
| GET /api/usta-tournaments      | All active USTA tournaments |
| GET /api/usta-tournaments/{id} | Raw USTA tournament detail  |
| GET /api/itf-tournaments       | All active ITF tournaments  |
| GET /api/itf-tournaments/{id}  | Raw ITF tournament detail   |
| GET /api/utr-tournaments       | All active UTR tournaments  |
| GET /api/utr-tournaments/{id}  | Raw UTR tournament detail   |
| GET /api/freshness             | Data scrape age             |
| GET /api/health                | Health check                |

## Deployment (AWS Elastic Beanstalk)

### First time setup

```bash
eb init
eb create tennis-tournament-map-env
make deploy
```

### Deploy updates

```bash
make deploy
```

### Check status

```bash
make status
make health
make logs
```

### Data update schedule (on server)

- **USTA**: daily at midnight UTC (`make update-usta` to run manually)
- **ITF**: weekly on Mondays at 1am UTC, 12 months ahead (`make update-itf` to run manually)
- **Deploy**: installs Chromium system libs only — does **not** scrape or download Playwright browsers (run `make update` after deploy; first ITF update installs browsers)

## Tech Stack

| Layer      | Technology                            |
| ---------- | ------------------------------------- |
| API        | FastAPI + Uvicorn                     |
| Data       | Pandas + PyArrow (Parquet)            |
| Scraping   | Requests + Playwright + BeautifulSoup |
| Frontend   | React 19 + Vite 7                     |
| Map        | React Leaflet 5 + MarkerCluster       |
| Deployment | AWS Elastic Beanstalk + Nginx         |

## License

MIT License