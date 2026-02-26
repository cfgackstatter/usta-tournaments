# Tennis Tournament Map

An interactive map for discovering USTA and ITF Masters Tour tennis tournaments.

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![React](https://img.shields.io/badge/React-18+-blue.svg)

## Features

### Interactive Map
- **Color-coded markers** showing tournament status:
  - 🔵 Blue: USTA — registration open
  - 🟢 Dark green: ITF Masters Tour - registration open
  - 🟠 Orange: Registration closed
  - 🔴 Red: Tournament started
- **Clustered markers** for dense areas
- **Detailed popups** with direct links to tournament pages

### Filtering
- **Date range**
- **Category**: Adult, Junior, Wheelchair
- **Level**: USTA Level 1–7, ITF MT100–MT1000
- **Surface**: Hard, Clay, Grass
- **Court location**: Indoor / Outdoor
- **Gender**, **Event type**, **Age group**

### Data Sources
- **USTA**: scraped daily from the USTA TournamentDesk API
- **ITF Masters Tour**: scraped weekly from the ITF calendar API + detail pages

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
| make data         | Fetch USTA (10 pages) + ITF (2 months)  |
| make data-usta    | Fetch USTA only                         |
| make data-itf     | Fetch ITF only                          |
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
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── App.css
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── usta_tournaments.parquet
│   └── itf_tournaments.parquet
├── .ebextensions/
│   ├── 01_setup.config         # Uvicorn + ASGI
│   ├── 02_cron.config          # Cron daemon + update scripts
│   ├── 03_post_deploy.config   # Post-deploy data fetch
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
- **ITF**: weekly on Mondays at 1am UTC (`make update-itf` to run manually)
- **Post-deploy**: both run automatically after each deployment

## Tech Stack

| Layer      | Technology                            |
| ---------- | ------------------------------------- |
| API        | FastAPI + Uvicorn                     |
| Data       | Pandas + PyArrow (Parquet)            |
| Scraping   | Requests + Playwright + BeautifulSoup |
| Frontend   | React 18 + Vite                       |
| Map        | React Leaflet + MarkerCluster         |
| Deployment | AWS Elastic Beanstalk + Nginx         |

## License

MIT License