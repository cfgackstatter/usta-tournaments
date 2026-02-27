.PHONY: install install-backend install-frontend \
        dev dev-backend dev-frontend \
        build deploy \
        update update-usta update-itf \
        data data-usta data-itf \
        logs ssh status health \
        clean clean-remote-data \
        help

PYTHON := python3
VENV := backend/venv
PIP := $(VENV)/bin/pip
PYTHON_VENV := $(VENV)/bin/python3

# ─── Setup ────────────────────────────────────────────────────────────────────

install: install-backend install-frontend

install-backend:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt

install-frontend:
	cd frontend && npm install

# ─── Development ──────────────────────────────────────────────────────────────

dev-backend:
	cd backend && ../$(VENV)/bin/uvicorn server:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) -j2 dev-backend dev-frontend

# ─── Data ─────────────────────────────────────────────────────────────────────

data-usta:
	$(PYTHON_VENV) -m backend.main --update-usta --max-pages 10

data-itf:
	$(PYTHON_VENV) -m backend.main --update-itf --months-back 0 --months-ahead 2

data: data-usta data-itf

# ─── Build & Deploy ───────────────────────────────────────────────────────────

build:
	cd frontend && npm run build

deploy: clean build
	eb deploy

# ─── AWS EB ───────────────────────────────────────────────────────────────────

status:
	eb status

health:
	eb health

logs:
	eb logs

ssh:
	eb ssh

# ─── Manual update on server ──────────────────────────────────────────────────

update-usta:
	eb ssh --command "sudo bash /usr/local/bin/update_usta.sh"

update-itf:
	eb ssh --command "sudo bash /usr/local/bin/update_itf.sh"

update: update-usta update-itf

# ─── Clean ────────────────────────────────────────────────────────────────────

clean:
	rm -rf frontend/dist
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-remote-data:
	eb ssh --command "sudo rm -f /var/app/shared/data/itf_tournaments.parquet /var/app/shared/data/usta_tournaments.parquet && ls -l /var/app/shared/data || true"

# ─── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  Setup"
	@echo "    make install          Install all backend + frontend dependencies"
	@echo "    make install-backend  Install Python dependencies only"
	@echo "    make install-frontend Install Node dependencies only"
	@echo ""
	@echo "  Development"
	@echo "    make dev              Run backend + frontend dev servers concurrently"
	@echo "    make dev-backend      Run FastAPI dev server only (port 8000)"
	@echo "    make dev-frontend     Run Vite dev server only (port 5173)"
	@echo ""
	@echo "  Data"
	@echo "    make data             Fetch USTA (10 pages) + ITF (2 months)"
	@echo "    make data-usta        Fetch USTA only"
	@echo "    make data-itf         Fetch ITF only"
	@echo ""
	@echo "  Deploy"
	@echo "    make build            Build frontend (npm run build)"
	@echo "    make deploy           Build frontend + eb deploy"
	@echo ""
	@echo "  AWS"
	@echo "    make status           eb status"
	@echo "    make health           eb health"
	@echo "    make logs             eb logs"
	@echo "    make ssh              eb ssh"
	@echo "    make update           Run both update scripts on server"
	@echo "    make update-usta      Run USTA update script on server"
	@echo "    make update-itf       Run ITF update script on server"
	@echo ""
	@echo "  Clean"
	@echo "    make clean             Remove build artifacts and __pycache__"
	@echo "    make clean-remote-data Remove Parquet data on server (/var/app/shared/data)"
	@echo ""